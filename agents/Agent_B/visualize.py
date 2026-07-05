"""
Agent B — Visualization of detected divergence (debug / demo).

Overlays a small very transparent circle EXACTLY where divergence was detected:
  - GREEN on the ENTRY image (the "before" reference state).
  - RED on the EXIT image (the "after" state where the problem appears).

Position is NOT taken directly from VLM `bbox_pct` (generalist VLMs are notoriously
unreliable for precise pointing — cf. `[0.1, 0.4, 0.9, 0.9]` covering almost
the whole image). We instead compute a centroid by classic IMAGE DIFFERENCE
between the two photos (deterministic, zero LLM, pixel-accurate):
  1. `bbox_pct` serves as a coarse search zone when credible.
  2. On the most divergent pixels (high percentile), we isolate CONNECTED
     COMPONENTS (flood-fill) rather than a simple global mean: a real defect
     (scratch, hole, stain) forms a compact blob, while ambient noise (window
     reflections, distant foliage, changing brightness) fragments into small
     scattered patches. We keep the largest blob, effectively filtering that noise.

Zero LLM calls here — pure image render/processing function, like Module C.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from agents.common.schemas import AlignmentEdge, Node

GREEN = (34, 197, 94)
RED = (220, 38, 38)
WATERMARK_ALPHA = 90  # out of 255 — "very transparent"
OUTLINE_ALPHA = 220
# Circle radius as a fraction of the shorter image side — deliberately small and
# fixed, independent of (often too large) bbox_pct size.
CIRCLE_RADIUS_RATIO = 0.035
CIRCLE_MIN_RADIUS_PX = 14

# Working resolution for difference computation (independent of actual photo
# resolution — sufficient to localize a centroid).
DIFF_WORK_SIZE = 300
DIFF_BLUR_RADIUS = 1
# bbox_pct zone considered "credible" to restrict search (beyond that, the VLM
# probably localized nothing precise -> ignore).
BBOX_MAX_CREDIBLE_AREA = 0.5
# Module A hint (per-checkpoint localization) is tolerated wider: even if imprecise,
# it beats unrestricted search in multi-entity mode (several checkpoints per photo).
NODE_HINT_CREDIBLE_AREA = 0.85
# Margin added around the Module A hint before restricting search (proportional
# to bbox size) to absorb slight framing offset between the two photos.
NODE_HINT_PADDING = 0.12
# Keep only the most divergent pixels (top percentile) to isolate the real
# defect from background noise (JPEG compression, grain, etc.).
TOP_PERCENTILE = 0.985
MIN_ABS_THRESHOLD = 10
# A connected component smaller than this is considered isolated noise, not a
# real defect.
MIN_COMPONENT_SIZE = 8


def _load_font(size: int = 22) -> ImageFont.FreeTypeFont:
    for candidate in ("Arial.ttf", "Helvetica.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _connected_components(mask: List[int], width: int, height: int) -> List[List[int]]:
    """4-connected flood-fill on a flat binary mask. Returns the list of
    components, each a list of pixel indices."""
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
    """Locate the largest divergence blob between two photos by classic image
    difference (zero LLM).

    Works on the max of 3 color channels (more sensitive to stains/discoloration
    than simple grayscale), isolates the most divergent pixels (`TOP_PERCENTILE`),
    then groups them into connected components: a real defect forms a compact blob,
    while ambient noise fragments into small scattered patches we discard by keeping
    only the largest blob.

    Returns normalized coordinates (x_pct, y_pct), or None if images are unavailable
    or no significant blob emerges ("unchanged" or non-comparable photos).
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
    """Slightly expand a bbox (margin proportional to its size) to tolerate
    slight offset between the two photos without losing per-checkpoint restriction."""
    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * margin_ratio
    pad_y = (y1 - y0) * margin_ratio
    return [
        max(0.0, x0 - pad_x), max(0.0, y0 - pad_y),
        min(1.0, x1 + pad_x), min(1.0, y1 + pad_y),
    ]


def _merge_bbox(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[List[float]]:
    """Union of two bboxes (useful when entry and exit each have their own
    Module A localization): expand rather than arbitrarily pick one."""
    if a and b:
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
    return a or b


def _pick_search_bbox(
    node_bbox_hint: Optional[List[float]],
    edge_bbox_pct: Optional[List[float]],
) -> Optional[List[float]]:
    """Search zone for image difference.

    Prefer bbox from Module A (`node_bbox_hint`): it localizes THIS checkpoint
    independently of comparison, essential when several checkpoints share one
    photo (e.g. bumper + door + wheel on the same exterior image) — without it,
    global difference may latch onto a neighbor's defect or unrelated render noise.

    Module A hint is tolerated with a wider margin (`NODE_HINT_CREDIBLE_AREA`)
    than comparison bbox: it comes from dedicated per-checkpoint localization.
    Small padding (`_pad_bbox`) absorbs slight framing offset between photos.
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
    """Point (x_pct, y_pct) where to place the circle, or None if nothing to localize."""
    status_value = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
    if status_value == "unchanged":
        return None

    search_bbox = _pick_search_bbox(node_bbox_hint, edge.bbox_pct)
    hotspot = _difference_hotspot(entry_image_path, exit_image_path, search_bbox=search_bbox)
    if hotspot is not None:
        return hotspot

    # Fallback: center of best known bbox is still better than no indication.
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
        # No localization possible (status="unchanged" or undetectable difference):
        # simple colored border around the image, no filled zone.
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
    """Write two annotated images in `output_dir`:
    `{checkpoint_id}_avant.jpg` (green) and `{checkpoint_id}_apres.jpg` (red).

    Circle position is computed by image difference between the two photos (see
    `_resolve_location`), not taken directly from the VLM.

    Optional `entry_node`/`exit_node` provide Module A `bbox_pct`: essential in
    multi-entity mode (several checkpoints sharing one photo) to target the right
    element among several visible on the image.

    Returns (entry_path, exit_path).
    """
    status_label = edge.status.value if hasattr(edge.status, "value") else str(edge.status)
    node_bbox_hint = _merge_bbox(
        entry_node.bbox_pct if entry_node else None,
        exit_node.bbox_pct if exit_node else None,
    )
    location = _resolve_location(entry_image_path, exit_image_path, edge, node_bbox_hint=node_bbox_hint)

    entry_out = os.path.join(output_dir, f"{edge.checkpoint_id}_avant.jpg")
    exit_out = os.path.join(output_dir, f"{edge.checkpoint_id}_apres.jpg")

    _draw_watermark(entry_image_path, entry_out, location, GREEN, "BEFORE (reference)")
    _draw_watermark(exit_image_path, exit_out, location, RED, f"AFTER — {status_label}")

    return entry_out, exit_out
