/* Browser smoke test for the frontend. Drives a real Chrome against the running server and
 * checks the behaviours that matter. Exits non-zero if any check fails.
 *
 *   python -m api.server &                           # in the repo root
 *   PUPPETEER_DIR=/path/containing/node_modules node frontend/tests/smoke.mjs [baseUrl]
 *
 * Needs puppeteer-core (npm i puppeteer-core in PUPPETEER_DIR) and Google Chrome. */
import { createRequire } from 'node:module';
const require = createRequire((process.env.PUPPETEER_DIR || process.cwd()) + '/');
const puppeteer = require('puppeteer-core');

const base = process.argv[2] || 'http://127.0.0.1:8000';
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const results = [];
const check = (id, name, ok, detail = '') => { results.push({ id, name, ok }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${id}  ${name}${detail ? '  (' + detail + ')' : ''}`); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: true });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
const errors = [], apiCalls = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('request', (r) => { if (r.url().includes('/api/')) apiCalls.push(r.url().replace(base, '')); });
await page.evaluateOnNewDocument(() => { window.__csv = null; const real = URL.createObjectURL; URL.createObjectURL = (b) => { b.text().then((t) => (window.__csv = t)); return real.call(URL, b); }; });

await page.goto(`${base}/?t=150`, { waitUntil: 'networkidle0' });
check('ST-01', 'page loads and shows a live run', (await page.$eval('#status', (e) => e.textContent)).startsWith('Live run'));
check('ST-02', 'four control modes are offered', (await page.$$('#modes .mode')).length === 4);
check('ST-03', 'the readout states a transit time', /\d+\s?s door to door/.test(await page.$eval('#readout-head', (e) => e.textContent)));

const clock0 = await page.$eval('#clock', (e) => e.textContent);
await page.click('#play'); await wait(1500); await page.click('#play');
check('ST-04', 'Play advances the replay clock', (await page.$eval('#clock', (e) => e.textContent)) !== clock0);

await page.click('.mode[data-mode="no_preemption"]');
check('ST-05', 'switching mode updates the readout and URL', (await page.$eval('#readout-head', (e) => e.textContent)).startsWith('No preemption') && (await page.evaluate(() => location.search)).includes('mode=no_preemption'));

await page.click('.jn[data-id="J2_4"]');
check('ST-06', 'clicking a junction opens its detail panel', !(await page.$eval('#detail', (e) => e.hidden)));
await page.keyboard.press('Escape');
check('ST-07', 'Escape closes the panel and returns focus to the junction', (await page.$eval('#detail', (e) => e.hidden)) && (await page.evaluate(() => document.activeElement?.getAttribute('data-id'))) === 'J2_4');

await page.$eval('input[name="vehicles"]', (el) => { el.value = '200'; el.dispatchEvent(new Event('input', { bubbles: true })); });
check('ST-08', 'unrun edits are flagged', (await page.$eval('#run-hint', (e) => e.textContent)).startsWith('Changed, not run'));
await page.click('#seeds-run'); await page.waitForFunction(() => document.querySelector('#seeds table'), { timeout: 90000 });
check('ST-09', 'compare uses the scenario on screen (80 vehicles), not the unrun edit', apiCalls.some((u) => u.startsWith('/api/compare') && u.includes('vehicles=80')));
check('ST-10a', 'with No preemption selected, the seeds area explains how to see the bars', !!(await page.$('#seeds .strips-hint')));
await page.click('.mode[data-mode="corridor_recovery"]');
check('ST-10', 'per-seed bars are drawn (12 seeds x 2 measures)', (await page.$$('#seeds .sbar')).length === 24);
await page.click('#run'); await wait(5000);
check('ST-11', 'running the edited scenario applies it and clears the flag', (await page.evaluate(() => location.search)).includes('vehicles=200') && (await page.$eval('#run-hint', (e) => e.textContent)) === '');

await page.click('#export'); await wait(500);
const csv = await page.evaluate(() => window.__csv);
check('ST-12', 'Export CSV produces the four-mode table', !!csv && csv.includes('mode,transit_s') && csv.includes('corridor_recovery'));

await page.click('#appearance [data-pref="dark"]');
check('ST-13', 'dark appearance applies', (await page.evaluate(() => document.documentElement.dataset.mode)) === 'dark');
await page.click('#appearance [data-pref="light"]');
check('ST-14', 'light appearance applies', (await page.evaluate(() => document.documentElement.dataset.mode)) === 'light');
check('ST-15', 'no console errors during the whole run', errors.length === 0, errors.join('; '));

// A deliberately bad parameter: the server answers 400 and the page must say so, not show stand-in data.
await page.goto(`${base}/?slew=nan`, { waitUntil: 'networkidle0' });
check('ST-16', 'a rejected parameter shows the server\'s reason', (await page.$eval('#map', (e) => e.dataset.state)) === 'error' && /slew must be a finite number/.test(await page.$eval('#map-error', (e) => e.textContent)));

// Markup in a URL parameter must be shown or ignored, never executed.
await page.goto(`${base}/?seed=%3Cimg%20src%3Dx%20onerror%3Dwindow.__pwn%3D1%3E&mode=%3Cscript%3Ewindow.__pwn%3D1%3C%2Fscript%3E`, { waitUntil: 'networkidle0' });
check('ST-18', 'markup in URL parameters is not executed', (await page.evaluate(() => window.__pwn)) === undefined && !(await page.$('#map-error img, #status img')));

await page.setViewport({ width: 390, height: 844 }); await page.goto(`${base}/`, { waitUntil: 'networkidle0' });
check('ST-17', 'no horizontal scrolling at phone width', (await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 0);

await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} checks pass`);
process.exit(failed ? 1 : 0);
