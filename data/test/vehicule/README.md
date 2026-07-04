# Test pipeline véhicule (Module A -> B -> D -> C)

Déposez ici vos 4 photos (une par zone x état) :

| Fichier attendu           | Contenu                                                      |
|----------------------------|---------------------------------------------------------------|
| `entry_exterieur.jpg`      | Extérieur du véhicule à l'entrée (pare-choc, portière, aile, jante, pare-brise visibles) |
| `entry_interieur.jpg`      | Intérieur du véhicule à l'entrée (siège conducteur, volant, tableau de bord, plancher) |
| `exit_exterieur.jpg`       | Même cadrage extérieur, à la sortie                            |
| `exit_interieur.jpg`       | Même cadrage intérieur, à la sortie                            |

Chaque photo peut (et doit) montrer **plusieurs checkpoints à la fois** —
contrairement au mode immobilier (1 photo = 1 checkpoint), le Module A
identifie ici tous les éléments listés dans
`config/checkpoints_vehicule.example.json` en un seul appel par photo.

## Lancer le pipeline complet

```bash
export NVIDIA_API_KEY=...   # ou dans un .env à la racine
uv run scripts/run_pipeline_vehicule.py
```

Le script :
1. Construit les graphes d'entrée/sortie (Module A, 2 appels VLM au total).
2. Compare chaque checkpoint commun (Module B).
3. Génère des images annotées (cercle localisé) pour chaque écart, dans `annotated/`.
4. Qualifie légalement chaque écart (Module D).
5. Génère le rapport final dans `rapport_vehicule.pdf` (Module C).

## Vérité terrain de référence (pour évaluer les résultats)

| checkpoint_id            | Défaut injecté                | Classe attendue                   |
|---------------------------|--------------------------------|-------------------------------------|
| `pare_choc_avant`         | micro-rayure vernis            | `damage` (sévérité faible)          |
| `portiere_avant_gauche`   | bosse légère peu visible       | `damage`                            |
| `aile_avant_droite`       | inchangé                       | `unchanged`                         |
| `jante_avant_gauche`      | éraflure bordure               | `damage`                            |
| `pare_brise`              | impact gravillon 3mm           | `damage` (ambigu, cf. Module B — l'antériorité doit être signalée comme incertaine) |
| `siege_conducteur`        | affaissement/décoloration diffuse | `normal_wear`                    |
| `volant`                  | inchangé                       | `unchanged`                         |
| `tableau_de_bord`         | micro-rayure écran             | `damage` (sévérité faible)          |
| `plancher_conducteur`     | tache diffuse                  | `damage` ou usage anormal selon contexte (bon test Module D) |

Note : sur des défauts très subtils, un outil de génération/édition d'image
peut soit les ignorer, soit les exagérer. Si le défaut injecté n'est pas
visible même à l'œil nu sur votre photo, il ne sera pas non plus détectable
par le pipeline — ce n'est pas un bug du pipeline.
