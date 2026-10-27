// Puppeteer browser service. The Python agent calls these endpoints over HTTP.
// One browser, one page per run: login state persists across tool calls.
//
// Env: PORT (4000), PUPPETEER_EXECUTABLE_PATH (use a system Chrome), PUPPETEER_HEADLESS (true|shell),
//      BROWSER_ARGS (comma-separated extra Chrome flags, e.g. --no-sandbox inside containers)
const express = require('express');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

// Runs inside the page. Gives every visible interactive element a numeric id so the model never
// writes selectors. Ids are reassigned on every snapshot.
const SNAPSHOT = () => {
  document.querySelectorAll('[data-aid]').forEach(e => e.removeAttribute('data-aid'));
  const sel = 'a,button,input,select,textarea,[role=button]';
  let i = 0;
  const els = [];
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.type === 'hidden') return;
    el.setAttribute('data-aid', String(++i));
    const tag = el.tagName.toLowerCase();
    const isField = ['input', 'select', 'textarea'].includes(tag) && !['submit', 'button'].includes(el.type);
    const lab = el.labels && el.labels[0] ? el.labels[0].innerText : '';
    els.push({
      id: i, tag, type: el.type || '',
      label: isField
        ? (lab || el.getAttribute('aria-label') || el.placeholder || el.name || '').trim().slice(0, 60)
        : (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 80),
      value: isField && el.type !== 'password' ? String(el.value || '').slice(0, 60) : '',
      options: tag === 'select' ? [...el.options].map(o => o.text.trim()).slice(0, 12) : undefined,
      href: el.getAttribute('href') || '',
      disabled: !!el.disabled
    });
  });
  return { title: document.title, url: location.href,
           text: document.body.innerText.slice(0, 2500), elements: els };
};

let browser, page, runDir = '.', shotN = 0;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const byId = id => `[data-aid='${Number(id)}']`;

async function snapshot() {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await sleep(300);
      await page.waitForNetworkIdle({ idleTime: 300, timeout: 8000 }).catch(() => {});
      const snap = await page.evaluate(SNAPSHOT);
      shotN += 1;
      snap.screenshot = path.join(runDir, `shot_${String(shotN).padStart(3, '0')}.png`);
      await page.screenshot({ path: snap.screenshot });
      return snap;
    } catch (e) {
      if (attempt === 2) throw e;   // a navigation may have destroyed the page context: retry
    }
  }
}

async function launch() {
  const headless = process.env.PUPPETEER_HEADLESS === 'shell' ? 'shell' : true;
  const args = (process.env.BROWSER_ARGS || '').split(',').map(s => s.trim()).filter(Boolean);
  return puppeteer.launch({ headless, args });
}

const app = express();
app.use(express.json());

const route = (name, fn) => app.post('/' + name, async (req, res) => {
  try {
    res.json(await fn(req.body || {}));
  } catch (e) {
    const cls = e.name !== 'TimeoutError' ? 'unknown'
      : /selector/i.test(e.message) ? 'element_not_found' : 'timeout';
    res.status(422).json({ error_class: cls, error: String(e.message).slice(0, 300) });
  }
});

route('start', async ({ run_dir }) => {
  runDir = run_dir || '.';
  fs.mkdirSync(runDir, { recursive: true });
  browser = browser || await launch();
  if (page) await page.close().catch(() => {});
  page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  page.setDefaultTimeout(8000);
  page.on('dialog', d => d.dismiss().catch(() => {}));
  shotN = 0;
  return { ok: true };
});

route('goto', async ({ url }) => {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  return snapshot();
});

route('read', () => snapshot());

route('click', async ({ id }) => {
  const h = await page.waitForSelector(byId(id), { visible: true });
  await h.click();
  return snapshot();
});

route('type', async ({ id, text }) => {
  const h = await page.waitForSelector(byId(id), { visible: true });
  await h.click({ clickCount: 3 });   // select existing text so typing replaces it
  await h.type(String(text));
  return snapshot();
});

route('select', async ({ id, value }) => {
  await page.waitForSelector(byId(id), { visible: true });
  await page.evaluate((q, v) => {
    const s = document.querySelector(q);
    const o = [...s.options].find(o => o.text.trim() === v || o.value === v);
    if (!o) throw new Error('option not found: ' + v);
    s.value = o.value;
    s.dispatchEvent(new Event('change', { bubbles: true }));
  }, byId(id), value);
  return snapshot();
});

route('download', async ({ id }) => {
  const h = await page.waitForSelector(byId(id), { visible: true });
  const href = await h.evaluate(a => a.href);
  const cookies = await page.cookies();
  const r = await fetch(href, { headers: { cookie: cookies.map(c => `${c.name}=${c.value}`).join('; ') } });
  if (!r.ok) throw new Error('download failed: HTTP ' + r.status);
  const file = path.join(runDir, path.basename(new URL(href).pathname));
  fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()));
  return { path: file };
});

route('close', async () => {
  if (page) await page.close().catch(() => {});
  page = null;
  return { ok: true };
});

app.get('/health', (req, res) => res.json({ ok: true }));

const server = app.listen(process.env.PORT || 4000, () =>
  console.log(`browser service on :${server.address().port}`));
process.on('SIGINT', async () => { if (browser) await browser.close(); process.exit(0); });
process.on('SIGTERM', async () => { if (browser) await browser.close(); process.exit(0); });
