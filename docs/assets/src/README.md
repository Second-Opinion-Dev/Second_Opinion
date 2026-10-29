# README graphics

`banner.html`, `pipeline.html` and `detector.html` are the sources of the PNGs in `docs/assets/`. They share the presentation's palette and type (Inter, Instrument Serif, JetBrains Mono). `banner.html` reuses the presentation's water shader, and `detector.html` draws a seeded **synthetic** series, not real data.

Re-render at 2× with headless Chrome (needs network access for Google Fonts). The window heights are 440, 490 and 520:

```bash
chrome --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1280,440 --virtual-time-budget=8000 \
  --screenshot=docs/assets/banner.png "file://$PWD/docs/assets/src/banner.html"
```
