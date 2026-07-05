"""English display strings for Studio-facing audit payloads.

Translates French checkpoint ids, element types, condition values, and room
names from the ARIA pipeline into user-readable English. Internal ids are
unchanged; only labels and prose shown in the graph / evidence panel are
localized.
"""

from __future__ import annotations

# Full checkpoint id -> English label (vehicle + common property elements).
CHECKPOINT_LABELS: dict[str, str] = {
    "pare_choc_avant": "Front Bumper",
    "pare_choc_arriere": "Rear Bumper",
    "portiere_avant_gauche": "Front Left Door",
    "portiere_avant_droite": "Front Right Door",
    "portiere_arriere_gauche": "Rear Left Door",
    "portiere_arriere_droite": "Rear Right Door",
    "aile_avant_gauche": "Front Left Fender",
    "aile_avant_droite": "Front Right Fender",
    "aile_arriere_gauche": "Rear Left Fender",
    "aile_arriere_droite": "Rear Right Fender",
    "jante_avant_gauche": "Front Left Wheel",
    "jante_avant_droite": "Front Right Wheel",
    "jante_arriere_gauche": "Rear Left Wheel",
    "jante_arriere_droite": "Rear Right Wheel",
    "pare_brise": "Windshield",
    "capot": "Hood",
    "hayon": "Tailgate",
    "toit": "Roof",
    "retroviseur_gauche": "Left Mirror",
    "retroviseur_droite": "Right Mirror",
    "siege_conducteur": "Driver Seat",
    "siege_passager": "Passenger Seat",
    "volant": "Steering Wheel",
    "tableau_de_bord": "Dashboard",
    "plancher_conducteur": "Driver Floor",
    "front_bumper": "Front Bumper",
    "door_fl": "Door FL",
    "door_fr": "Door FR",
    "wheel_fl": "Wheel FL",
    "hood": "Hood",
    "windshield": "Windshield",
    "rear": "Rear",
}

WORD_LABELS: dict[str, str] = {
    "pare": "bumper",
    "choc": "",
    "portiere": "door",
    "porte": "door",
    "aile": "fender",
    "jante": "wheel",
    "pare_brise": "windshield",
    "parebrise": "windshield",
    "capot": "hood",
    "hayon": "tailgate",
    "toit": "roof",
    "retroviseur": "mirror",
    "siege": "seat",
    "conducteur": "driver",
    "passager": "passenger",
    "volant": "steering wheel",
    "tableau": "dashboard",
    "bord": "board",
    "plancher": "floor",
    "avant": "front",
    "arriere": "rear",
    "gauche": "left",
    "droite": "right",
    "mur": "wall",
    "sol": "floor",
    "plafond": "ceiling",
    "fenetre": "window",
    "radiateur": "radiator",
    "robinet": "tap",
    "evier": "sink",
    "baignoire": "bathtub",
    "prise": "outlet",
    "electrique": "electrical",
}

ELEMENT_TYPE_LABELS: dict[str, str] = {
    "pare_choc": "bumper",
    "portiere": "door",
    "porte": "door",
    "aile": "fender",
    "jante": "wheel",
    "pare_brise": "windshield",
    "siege": "seat",
    "volant": "steering wheel",
    "tableau_de_bord": "dashboard",
    "plancher": "floor",
    "mur": "wall",
    "sol": "floor",
    "plafond": "ceiling",
    "prise_electrique": "outlet",
    "panel": "panel",
    "wheel": "wheel",
    "glass": "glass",
    "body": "body",
    "vehicle": "vehicle",
    "part": "part",
}

CONDITION_LABELS: dict[str, str] = {
    "intact": "intact",
    "usé": "worn",
    "use": "worn",
    "endommagé": "damaged",
    "endommage": "damaged",
    "unknown": "unknown",
}

ROOM_LABELS: dict[str, str] = {
    "exterieur": "Exterior",
    "interieur": "Interior",
    "salon": "Living room",
    "chambre": "Bedroom",
    "cuisine": "Kitchen",
    "sdb": "Bathroom",
    "salle_de_bain": "Bathroom",
    "entree": "Entry",
    "couloir": "Hallway",
}

DEFECT_LABELS: dict[str, str] = {
    "rayure": "scratch",
    "rayures": "scratches",
    "bosse": "dent",
    "bosses": "dents",
    "trou": "hole",
    "trous": "holes",
    "fissure": "crack",
    "fissures": "cracks",
    "tache": "stain",
    "taches": "stains",
    "éclat": "chip",
    "eclat": "chip",
    "éclats": "chips",
    "eclats": "chips",
}


def checkpoint_label(checkpoint_id: str) -> str:
    key = checkpoint_id.strip().lower()
    if key in CHECKPOINT_LABELS:
        return CHECKPOINT_LABELS[key]
    words = key.split("_")
    translated = [WORD_LABELS.get(word, word) for word in words]
    translated = [word for word in translated if word]
    if not translated:
        return checkpoint_id.replace("_", " ").title()
    return " ".join(translated).title()


def element_type_label(element_type: str | None) -> str:
    if not element_type:
        return "part"
    key = element_type.strip().lower()
    return ELEMENT_TYPE_LABELS.get(key, checkpoint_label(key).lower())


def condition_label(condition: str | None) -> str:
    if not condition:
        return "unknown"
    key = condition.strip().lower()
    return CONDITION_LABELS.get(key, condition)


def defect_label(defect: str) -> str:
    key = defect.strip().lower()
    return DEFECT_LABELS.get(key, defect)


def room_label(room: str | None) -> str:
    if not room:
        return "Exterior"
    key = room.strip().lower()
    return ROOM_LABELS.get(key, checkpoint_label(key))


def condition_summary(condition: str | None, defects: list[str] | None) -> str:
    parts = [condition_label(condition)]
    if defects:
        parts.append(", ".join(defect_label(d) for d in defects))
    return " — ".join(p for p in parts if p)


def legal_reasoning_en(reasoning: str) -> str:
    """Best-effort English summary for legal qualification prose."""
    if not reasoning.strip():
        return "Chargeable under applicable fair wear and rental standards."
    lowered = reasoning.lower()
    french_markers = (
        "décret",
        "decret",
        "vétusté",
        "vetuste",
        "bail",
        "locataire",
        "grille",
        "annexée",
        "annexee",
    )
    if not any(marker in lowered for marker in french_markers):
        return reasoning
    return (
        "Chargeable under applicable fair wear and rental standards "
        "(legal qualification applied)."
    )
