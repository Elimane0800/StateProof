# Dossier de test — Module A + B + visualisation

Déposez ici vos deux photos du même checkpoint :

```
data/test/entry.jpg   # photo "avant" (entrée)
data/test/exit.jpg    # photo "après" (sortie)
```

(n'importe quelle extension image standard convient : .jpg, .jpeg, .png)

Puis lancez :

```bash
uv run scripts/run_visual_test.py --entry-image data/test/entry.jpg --exit-image data/test/exit.jpg
```

Résultat écrit dans `data/test/annotated/` :

- `{checkpoint_id}_avant.jpg` — photo d'entrée avec un watermark **vert**
  semi-transparent sur la zone de divergence détectée.
- `{checkpoint_id}_apres.jpg` — photo de sortie avec un watermark **rouge**
  semi-transparent sur la même zone.

Si le modèle ne peut pas localiser précisément l'anomalie (changement
diffus, ou `status="unchanged"`), un simple liseré coloré encadre l'image
entière plutôt qu'une zone remplie.
