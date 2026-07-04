"""
Agent B — Visualisation de la divergence détectée (debug / démo).

Superpose un petit cercle très transparent EXACTEMENT là où la divergence a
été détectée :
  - VERT sur l'image d'ENTRÉE (l'état "avant", référence).
  - ROUGE sur l'image de SORTIE (l'état "après", là où le problème apparaît).

La position n'est PAS prise telle quelle depuis `bbox_pct` du VLM (les VLM
généralistes sont notoirement peu fiables pour pointer précisément — cf.
`[0.1, 0.4, 0.9, 0.9]` qui couvre quasiment toute l'image). On calcule à la
place un centroïde par DIFFÉRENCE D'IMAGE classique entre les deux photos
(déterministe, zéro LLM, exact au pixel près) :
  1. `bbox_pct` sert de zone de recherche grossière quand elle est crédible.
  2. Sur les pixels les plus divergents (percentile élevé), on isole les
     COMPOSANTES CONNEXES (flood-fill) plutôt qu'une simple moyenne globale :
     un vrai défaut (rayure, trou, tache) forme un blob compact, alors que le
     bruit ambiant (reflets de fenêtre, feuillage au loin, luminosité
     changeante) se fragmente en petites taches éparses. On garde le plus
     gros blob, ce qui écarte efficacement ce bruit.

Zéro appel LLM ici — fonction pure de rendu/traitement d'image, à l'image du
Module C.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from agents.common.schemas import AlignmentEdge, Node

GREEN = (34, 197, 94)
RED = (220, 38, 38)
WATERMARK_ALPHA = 90  # sur 255 — "très transparent"
OUTLINE_ALPHA = 220
# Rayon du cercle en fraction du plus petit côté de l'image — volontairement
# petit et fixe, indépendant de la taille (souvent trop large) de bbox_pct.
CIRCLE_RADIUS_RATIO = 0.035
CIRCLE_MIN_RADIUS_PX = 14

# Résolution de travail pour le calcul de différence (indépendante de la
# résolution réelle des photos — suffisant pour localiser un centroïde).
DIFF_WORK_SIZE = 300
DIFF_BLUR_RADIUS = 1
# Zone bbox_pct considérée comme "crédible" pour restreindre la recherche
# (au-delà, le VLM n'a probablement rien localisé de précis -> on ignore).
BBOX_MAX_CREDIBLE_AREA = 0.5
# Le hint du Module A (localisation dédiée par checkpoint) est toléré plus
# large : même imprécis, il reste préférable à une recherche sans restriction
# en mode multi-entités (plusieurs checkpoints par photo).
NODE_HINT_CREDIBLE_AREA = 0.85
# Marge ajoutée autour du hint du Module A avant de restreindre la recherche
# (proportionnelle à la taille de la bbox), pour absorber un léger décalage
# de cadrage entre les deux photos (angle, ou deux rendus générés séparément).
NODE_HINT_PADDING = 0.12
# On ne garde que les pixels les plus divergents (haut du percentile) pour
# isoler le vrai défaut du bruit de fond (compression JPEG, grain, etc.).
TOP_PERCENTILE = 0.985
MIN_ABS_THRESHOLD = 10
# Une composante connexe plus petite que ça est considérée comme du bruit
# isolé, pas un défaut réel.
MIN_COMPONENT_SIZE = 8


def _load_font(size: int = 22) -> ImageFont.FreeTypeFont:
    for candidate in ("Arial.ttf", "Helvetica.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _connected_components(mask: List[int], width: int, height: int) -> List[List[int]]:
    """Flood-fill 4-connexe sur un masque binaire aplati. Retourne la liste
    des composantes, chacune étant une liste d'indices de pixels."""
    visited = [False] * len(mask)
    components: List[List[int]] = []
    for start in range(len(mask)):
        if mask[start] and not visited[start]:
            stack = [start]
            visited[start] = True
            comp = []
            while stack:
                idx = stack.pop()
                comp.append(idx)
                x, y = idx % width, idx // width
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        nidx = ny * width + nx
                        if mask[nidx] and not visited[nidx]:
                            visited[nidx] = True
                            stack.append(nidx)
            components.append(comp)
    return components


def _difference_hotspot(
    entry_image_path: str,
    exit_image_path: str,
    search_bbox: Optional[List[float]] = None,
) -> Optional[Tuple[float, float]]:
    """Localise le plus gros blob de divergence entre les deux photos, par
    différence d'image classique (zéro LLM).

    On travaille sur le maximum des 3 canaux couleur (plus sensible aux
    taches/décolorations qu'un simple niveau de gris), on isole les pixels
    les plus divergents (`TOP_PERCENTILE`), puis on regroupe ces pixels en
    composantes connexes : un vrai défaut forme un blob compact, alors que
    le bruit ambiant (reflets, luminosité changeante) se fragmente en petites
    taches éparses qu'on écarte en gardant uniquement le plus gros blob.

    Retourne des coordonnées normalisées (x_pct, y_pct), ou None si les
    images sont indisponibles ou si aucun blob significatif n'émerge
    (cas "unchanged" ou photos non comparables).
    """
    try:
        entry_img = Image.open(entry_image_path).convert("RGB")
        exit_img = Image.open(exit_image_path).convert("RGB")
    except (FileNotFoundError, OSError):
        return None

    size = (DIFF_WORK_SIZE, DIFF_WORK_SIZE)
    entry_resized = entry_img.resize(size)
    exit_resized = exit_img.resize(size)

    diff = ImageChops.difference(entry_resized, exit_resized)
    r, g, b = diff.split()
    magnitude = ImageChops.lighter(ImageChops.lighter(r, g), b)
    magnitude = magnitude.filter(ImageFilter.GaussianBlur(radius=DIFF_BLUR_RADIUS))

    x0, y0, x1, y1 = 0, 0, DIFF_WORK_SIZE, DIFF_WORK_SIZE
    if search_bbox:
        bx0, by0, bx1, by1 = search_bbox
        if 0 < (bx1 - bx0) * (by1 - by0) <= BBOX_MAX_CREDIBLE_AREA:
            x0 = max(0, int(bx0 * DIFF_WORK_SIZE))
            y0 = max(0, int(by0 * DIFF_WORK_SIZE))
            x1 = min(DIFF_WORK_SIZE, int(bx1 * DIFF_WORK_SIZE))
            y1 = min(DIFF_WORK_SIZE, int(by1 * DIFF_WORK_SIZE))
            if x1 - x0 < 6 or y1 - y0 < 6:
                x0, y0, x1, y1 = 0, 0, DIFF_WORK_SIZE, DIFF_WORK_SIZE

    region = magnitude.crop((x0, y0, x1, y1))
    w, h = region.size
    values = list(region.getdata())
    if not values:
        return None

    sorted_vals = sorted(values)
    threshold = max(MIN_ABS_THRESHOLD, sorted_vals[int(len(sorted_vals) * TOP_PERCENTILE)])
    mask = [1 if v >= threshold else 0 for v in values]

    components = [c for c in _connected_components(mask, w, h) if len(c) >= MIN_COMPONENT_SIZE]
    if not components:
        return None

    best = max(components, key=len)

    total_weight = 0.0
    weighted_x = 0.0
    weighted_y = 0.0
    for idx in best:
        v = values[idx]
        xx, yy = idx % w, idx // w
        weighted_x += xx * v
        weighted_y += yy * v
        total_weight += v

    if total_weight == 0:
        return None

    cx = (x0 + weighted_x / total_weight) / DIFF_WORK_SIZE
    cy = (y0 + weighted_y / total_weight) / DIFF_WORK_SIZE
    return (cx, cy)


def _is_credible_bbox(bbox: Optional[List[float]], max_area: float = BBOX_MAX_CREDIBLE_AREA) -> bool:
    if not bbox:
        return False
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0)
    return 0 < area <= max_area


def _pad_bbox(bbox: List[float], margin_ratio: float = NODE_HINT_PADDING) -> List[float]:
    """Élargit légèrement une bbox (marge proportionnelle à sa propre taille),
    pour tolérer un léger décalage entre les deux photos (angle, cadrage,
    ou deux rendus générés séparément et pas parfaitement superposables) sans
    perdre le bénéfice de la restriction par checkpoint."""
    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * margin_ratio
    pad_y = (y1 - y0) * margin_ratio
    return [
        max(0.0, x0 - pad_x), max(0.0, y0 - pad_y),
        min(1.0, x1 + pad_x), min(1.0, y1 + pad_y),
    ]


def _merge_bbox(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[List[float]]:
    """Union de deux bbox (utile quand l'entrée et la sortie ont chacune leur
    propre localisation du Module A) : on élargit plutôt que de choisir
    arbitrairement l'une des deux."""
    if a and b:
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
    return a or b


def _pick_search_bbox(
    node_bbox_hint: Optional[List[float]],
    edge_bbox_pct: Optional[List[float]],
) -> Optional[List[float]]:
    """Zone de recherche à utiliser pour la différence d'image.

    Priorité au bbox établi par le Module A (`node_bbox_hint`) : il localise
    CE checkpoint précis indépendamment de la comparaison, ce qui est
    indispensable quand plusieurs checkpoints partagent la même photo (ex :
    pare-choc + portière + jante sur une même image d'extérieur de
    véhicule) — sans ça, la différence globale peut accrocher le défaut d'un
    élément voisin, voire du bruit de rendu sans rapport (ombre, reflet).

    Le hint du Module A est toléré avec une marge plus large
    (`NODE_HINT_CREDIBLE_AREA`) que le bbox de comparaison : il vient d'une
    localisation dédiée par checkpoint (donc plus fiable a priori), et une
    zone connue même imparfaite reste toujours préférable à une recherche
    sur l'image entière en mode multi-entités. Une petite marge de tolérance
    (`_pad_bbox`) absorbe un léger décalage de cadrage entre les deux photos.
    """
    if _is_credible_bbox(node_bbox_hint, max_area=NODE_HINT_CREDIBLE_AREA):
        return _pad_bbox(node_bbox_hint)
    if _is_credible_bbox(edge_bbox_pct):
        return edge_bbox_pct
    return None


def _resolve_location(
    entry_image_path: str,
    exit_image_path: str,
    edge: AlignmentEdge,
    node_bbox_hint: Optional[List[float]] = None,
) -> Optional[Tuple[float, float]]:
    """Point (x_pct, y_pct) où placer le cercle, ou None si rien à localiser."""
    status_value = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
    if status_value == "unchanged":
        return None

    search_bbox = _pick_search_bbox(node_bbox_hint, edge.bbox_pct)
    hotspot = _difference_hotspot(entry_image_path, exit_image_path, search_bbox=search_bbox)
    if hotspot is not None:
        return hotspot

    # Repli : le centre de la meilleure bbox connue reste mieux qu'aucune
    # indication, si l'une d'elles est disponible.
    fallback_bbox = search_bbox or edge.bbox_pct
    if fallback_bbox:
        x_min, y_min, x_max, y_max = fallback_bbox
        return ((x_min + x_max) / 2, (y_min + y_max) / 2)

    return None


def _draw_watermark(
    image_path: str,
    output_path: str,
    location_pct: Optional[Tuple[float, float]],
    color: Tuple[int, int, int],
    label: str,
) -> str:
    base = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(16, base.width // 40))

    if location_pct:
        center_x = location_pct[0] * base.width
        center_y = location_pct[1] * base.height
        radius = max(CIRCLE_MIN_RADIUS_PX, min(base.width, base.height) * CIRCLE_RADIUS_RATIO)

        circle_box = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
        draw.ellipse(
            circle_box,
            fill=color + (WATERMARK_ALPHA,),
            outline=color + (OUTLINE_ALPHA,),
            width=max(2, int(radius * 0.18)),
        )
        text_pos = (max(0, center_x - radius), max(0, center_y - radius - font.size - 10))
    else:
        # Pas de localisation possible (status="unchanged" ou différence non
        # détectable) : simple liseré coloré autour de l'image, pas de zone remplie.
        draw.rectangle([0, 0, base.width - 1, base.height - 1],
                        outline=color + (OUTLINE_ALPHA,), width=max(4, base.width // 150))
        text_pos = (12, 12)

    draw.rectangle(
        [text_pos[0], text_pos[1], text_pos[0] + font.size * len(label) * 0.6 + 12, text_pos[1] + font.size + 8],
        fill=(0, 0, 0, 180),
    )
    draw.text((text_pos[0] + 6, text_pos[1] + 4), label, fill=color + (255,), font=font)

    combined = Image.alpha_composite(base, overlay).convert("RGB")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    combined.save(output_path, quality=92)
    return output_path


def annotate_divergence(
    entry_image_path: str,
    exit_image_path: str,
    edge: AlignmentEdge,
    output_dir: str,
    entry_node: Optional[Node] = None,
    exit_node: Optional[Node] = None,
) -> Tuple[str, str]:
    """Écrit deux images annotées dans `output_dir` :
    `{checkpoint_id}_avant.jpg` (vert) et `{checkpoint_id}_apres.jpg` (rouge).

    La position du cercle est calculée par différence d'image entre les deux
    photos (voir `_resolve_location`), pas prise telle quelle depuis le VLM.

    `entry_node`/`exit_node` (optionnels) fournissent le `bbox_pct` établi
    par le Module A : indispensable en mode multi-entités (plusieurs
    checkpoints partageant la même photo) pour cibler le bon élément parmi
    plusieurs visibles sur l'image, plutôt que de risquer d'accrocher le
    défaut d'un checkpoint voisin.

    Retourne (chemin_avant, chemin_apres).
    """
    status_label = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
    node_bbox_hint = _merge_bbox(
        entry_node.bbox_pct if entry_node else None,
        exit_node.bbox_pct if exit_node else None,
    )
    location = _resolve_location(entry_image_path, exit_image_path, edge, node_bbox_hint=node_bbox_hint)

    entry_out = os.path.join(output_dir, f"{edge.checkpoint_id}_avant.jpg")
    exit_out = os.path.join(output_dir, f"{edge.checkpoint_id}_apres.jpg")

    _draw_watermark(entry_image_path, entry_out, location, GREEN, "AVANT (référence)")
    _draw_watermark(exit_image_path, exit_out, location, RED, f"APRÈS — {status_label}")

    return entry_out, exit_out
