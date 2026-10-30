// Render the video frames with headless Chrome.
//   node render.mjs <timing.json> <outDir> frames [fps]      every frame -> frame_000001.jpg ...
//   node render.mjs <timing.json> <outDir> at 4.5,20,60       specific seconds -> at_<t>.png
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

// puppeteer-core is installed in a separate tooling folder (TOOLS), not in the project.
const puppeteer = createRequire(path.resolve(process.env.TOOLS, 'package.json'))('puppeteer-core');

const [, , timingPath, outDir, mode, arg] = process.argv;
const here = path.dirname(fileURLToPath(import.meta.url));
const html = pathToFileURL(path.resolve(here, '../src/video.html')).href;
const timing = JSON.parse(fs.readFileSync(timingPath, 'utf8'));
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p => fs.existsSync(p));
fs.mkdirSync(outDir, { recursive: true });

const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--hide-scrollbars', '--force-device-scale-factor=1', '--disable-gpu-vsync'], defaultViewport: { width: 1920, height: 1080, deviceScaleFactor: 1 } });

async function openPage() {
  const page = await browser.newPage();
  await page.goto(html, { waitUntil: 'networkidle0' });
  await page.evaluate(t => window.setTiming(t), timing);
  await page.evaluate(() => window.loadFonts());
  return page;
}

if (mode === 'at') {
  const page = await openPage();
  for (const s of arg.split(',')) {
    await page.evaluate(t => window.renderFrame(t), Number(s));
    await page.screenshot({ path: path.join(outDir, `at_${s}.png`), type: 'png' });
  }
} else {
  const fps = Number(arg || 30), total = Math.round(timing.total * fps), workers = 4;
  const pages = await Promise.all(Array.from({ length: workers }, openPage));
  let next = 0;
  await Promise.all(pages.map(async page => {
    for (;;) {
      const i = next++; if (i >= total) return;
      await page.evaluate(t => window.renderFrame(t), i / fps);
      // read the canvas directly: tabs that are not in front cannot take screenshots
      const data = await page.evaluate(() => document.getElementById('c').toDataURL('image/jpeg', 0.94).split(',')[1]);
      fs.writeFileSync(path.join(outDir, `frame_${String(i + 1).padStart(6, '0')}.jpg`), Buffer.from(data, 'base64'));
      if (i % 150 === 0) console.log(`frame ${i}/${total}`);
    }
  }));
}
await browser.close();
