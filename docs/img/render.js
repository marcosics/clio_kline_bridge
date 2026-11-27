// Pasa los SVG de docs/img a PNG (para ver) y a un PDF A4 apaisado (para imprimir).
// node docs/img/render.js
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const dir = __dirname;
const files = ['protoboard_esp01_lm339.svg', 'perfboard_arriba.svg', 'perfboard_abajo.svg', 'obd_pines.svg', 'pinout_lm339_esp01.svg'];
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ deviceScaleFactor: 2 });
  for (const f of files) {
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    const [, w, h] = svg.match(/width="(\d+)" height="(\d+)"/);
    await pg.setViewportSize({ width: +w, height: +h });
    await pg.setContent(`<body style="margin:0">${svg}</body>`);
    await pg.screenshot({ path: path.join(dir, f.replace('.svg', '.png')) });
  }
  const pages = files.map(f => `<div class="p">${fs.readFileSync(path.join(dir, f), 'utf8')}</div>`).join('');
  await pg.setContent(`<style>@page{size:A4 landscape;margin:8mm}body{margin:0}.p{page-break-after:always;height:190mm;display:flex;align-items:center;justify-content:center}.p svg{max-width:100%;max-height:100%;height:auto}</style>${pages}`);
  await pg.pdf({ path: path.join(dir, 'esquemas_imprimir.pdf'), format: 'A4', landscape: true, printBackground: true });
  await b.close();
  console.log('PNG y PDF listos');
})();
