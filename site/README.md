# Website

The public project page, a single self-contained `index.html` (fonts load from Google Fonts). It summarises the method and links back to the repository; it contains no measurement data or results.

## Preview

Open `index.html` in a browser, or serve the folder:

```bash
python -m http.server 8000 --directory site
```

## Publish

`.github/workflows/pages.yml` deploys this folder to GitHub Pages on every push to `main` that touches `site/`, and can be run by hand from the **Actions** tab. Enable it once under **Settings → Pages → Build and deployment → Source: GitHub Actions**. The page is then served at https://sunilparameswaran.github.io/Second_Opinion/.

Keep claims on the page in line with the [methodology](../docs/methodology.md): no accuracy, false-alarm or time-saving claims without labelled or expert-reviewed evidence.
