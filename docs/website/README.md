# Website

The public project site. It holds no measurement data or results.

| Path | Page |
| --- | --- |
| `index.html` | Landing page |
| `pipeline/index.html` | Interactive walk-through of each pipeline stage, on seeded synthetic data (`assets/pipeline.js`) |
| `docs/` (generated) | The guides, rendered from `docs/*.md` and `dashboard/README.md` |
| `assets/` | Shared styles, scripts and icon; the README graphics from `docs/assets/` are copied in at build time |

The markdown stays the single source for the documentation: edit it in `docs/` as before, and `build.py` renders it. Relative links between guides point to their site pages; links to code, tests or the README point to GitHub. To add a guide, add it to `GUIDES` in `build.py`.

## Build and preview

```bash
python -m pip install -r docs/website/requirements.txt
python docs/website/build.py
python -m http.server 8000 --directory _site
```

The build writes to `_site/` (git-ignored), replacing it each time.

## Publish

`.github/workflows/pages.yml` builds and deploys the site on every push to `main` that touches the site or the guides, and can be run by hand from the **Actions** tab. Enable it once under **Settings → Pages → Build and deployment → Source: GitHub Actions**. The site is then served at https://sunilparameswaran.github.io/Second_Opinion/.

Keep claims in line with the [methodology](../methodology.md): no accuracy, false-alarm or time-saving claims without labelled or expert-reviewed evidence. The pipeline illustrations must stay synthetic and labelled as such.
