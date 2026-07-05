# Test folder — Module A + B + visualization

Drop your two photos of the same checkpoint here:

```
data/test/entry.jpg   # "before" photo (entry)
data/test/exit.jpg    # "after" photo (exit)
```

(Any standard image extension works: `.jpg`, `.jpeg`, `.png`)

Then run:

```bash
uv run scripts/run_visual_test.py --entry-image data/test/entry.jpg --exit-image data/test/exit.jpg
```

Output is written to `data/test/annotated/`:

- `{checkpoint_id}_avant.jpg` — entry photo with a semi-transparent **green** watermark on the detected divergence zone.
- `{checkpoint_id}_apres.jpg` — exit photo with a semi-transparent **red** watermark on the same zone.

If the model cannot localize the anomaly precisely (diffuse change, or `status="unchanged"`), a simple colored border frames the entire image instead of a filled zone.
