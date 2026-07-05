import type { Classification } from "../types/contract";

/** Map legacy / engine aliases onto schema classifications for display. */
export function normalizeClassification(value: string): Classification {
  switch (value) {
    case "damage":
      return "design_violation";
    case "normal_wear":
      return "technical_noise";
    case "agreed_change":
    case "evolution":
      return "intentional_evolution";
    case "aligned":
    case "design_violation":
    case "technical_noise":
    case "intentional_evolution":
      return value;
    default:
      return "aligned";
  }
}

const CHECKPOINT_LABELS: Record<string, string> = {
  pare_choc_avant: "Front Bumper",
  pare_choc_arriere: "Rear Bumper",
  portiere_avant_gauche: "Front Left Door",
  portiere_avant_droite: "Front Right Door",
  portiere_arriere_gauche: "Rear Left Door",
  portiere_arriere_droite: "Rear Right Door",
  aile_avant_gauche: "Front Left Fender",
  aile_avant_droite: "Front Right Fender",
  jante_avant_gauche: "Front Left Wheel",
  jante_avant_droite: "Front Right Wheel",
  pare_brise: "Windshield",
  capot: "Hood",
  hayon: "Tailgate",
  siege_conducteur: "Driver Seat",
  volant: "Steering Wheel",
  tableau_de_bord: "Dashboard",
  front_bumper: "Front Bumper",
  door_fl: "Door FL",
  door_fr: "Door FR",
  wheel_fl: "Wheel FL",
  hood: "Hood",
  windshield: "Windshield",
  rear: "Rear",
};

const WORD_LABELS: Record<string, string> = {
  pare: "bumper",
  choc: "",
  portiere: "door",
  porte: "door",
  aile: "fender",
  jante: "wheel",
  capot: "hood",
  hayon: "tailgate",
  siege: "seat",
  conducteur: "driver",
  volant: "steering wheel",
  tableau: "dashboard",
  bord: "board",
  plancher: "floor",
  avant: "front",
  arriere: "rear",
  gauche: "left",
  droite: "right",
  mur: "wall",
  sol: "floor",
  plafond: "ceiling",
};

const ELEMENT_TYPE_LABELS: Record<string, string> = {
  pare_choc: "bumper",
  portiere: "door",
  aile: "fender",
  jante: "wheel",
  pare_brise: "windshield",
  siege: "seat",
  volant: "steering wheel",
  tableau_de_bord: "dashboard",
  plancher: "floor",
  mur: "wall",
  sol: "floor",
  panel: "panel",
  wheel: "wheel",
  glass: "glass",
  body: "body",
  vehicle: "vehicle",
  part: "part",
};

function translateCheckpointId(checkpointId: string): string {
  const key = checkpointId.trim().toLowerCase();
  if (CHECKPOINT_LABELS[key]) return CHECKPOINT_LABELS[key];
  const words = key.split("_");
  const translated = words
    .map((word) => WORD_LABELS[word] ?? word)
    .filter(Boolean);
  if (translated.length === 0) return checkpointId.replace(/_/g, " ");
  return translated
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** English label for a tree node (may already be English from the payload). */
export function displayNodeLabel(label: string, rawId?: string): string {
  const fromId = rawId ? translateCheckpointId(rawId.split(":").pop() ?? rawId) : null;
  const trimmed = label.trim();
  const looksFrench =
    /portiere|pare.choc|aile|jante|exterieur|interieur|mur_|sol_|siege_/i.test(trimmed) ||
    /portiere|pare.choc|aile|jante|exterieur|interieur|mur_|sol_|siege_/i.test(rawId ?? "");
  if (looksFrench && fromId) return fromId;
  return trimmed;
}

/** English element type shown under each graph node. */
export function displayElementType(type: string): string {
  const key = type.trim().toLowerCase();
  return ELEMENT_TYPE_LABELS[key] ?? type.replace(/_/g, " ");
}

/** English heading for the evidence panel node id. */
export function displayNodeId(nodeId: string): string {
  const checkpoint = nodeId.includes(":") ? nodeId.split(":").pop()! : nodeId;
  return translateCheckpointId(checkpoint);
}
