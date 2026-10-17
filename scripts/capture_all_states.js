const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const resultsJsonPath = path.resolve(__dirname, '../results.json');
const resultsData = JSON.parse(fs.readFileSync(resultsJsonPath, 'utf-8'));

function sse(events) {
  return events
    .map(([eventName, payload]) => `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`)
    .join('');
}

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];

async function captureState(targetDir, stateName, setupPage) {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
      });
      const page = await context.newPage();
      try {
        await setupPage(page, vp);
        // Wait briefly for fonts, layout, and any animations to settle
        await page.waitForTimeout(300);
        const filename = `${stateName}_${vp.width}x${vp.height}.png`;
        const filePath = path.join(targetDir, filename);
        await page.screenshot({ path: filePath, fullPage: false });
        console.log(`Saved: ${filePath}`);
      } catch (err) {
        console.error(`Error capturing ${stateName} at ${vp.width}x${vp.height}:`, err);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}

async function run(targetDir = path.resolve(__dirname, '../docs/design/before')) {
  fs.mkdirSync(targetDir, { recursive: true });

  console.log('Capturing: landing...');
  await captureState(targetDir, 'landing', async (page) => {
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    // Clear any leftover saved results in localStorage
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: 'networkidle' });
  });

  console.log('Capturing: loading...');
  await captureState(targetDir, 'loading', async (page) => {
    // Intercept search and keep it hanging
    await page.route('**/search?**', () => {
      // Intentionally do not fulfill immediately
    });
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.getByLabel('Role or keyword *').fill('Backend Engineer');
    await page.getByRole('button', { name: /search ats platforms/i }).click();
    await page.waitForSelector('text=Searching ATS platforms directly', { timeout: 10000 });
  });

  console.log('Capturing: results...');
  await captureState(targetDir, 'results', async (page, vp) => {
    await page.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([
          ['results', { batch: resultsData.slice(0, 20), total_so_far: 20 }],
          ['results', { batch: resultsData.slice(20), total_so_far: resultsData.length }],
          [
            'done',
            {
              total: resultsData.length,
              search_time_ms: 1420,
              serper_queries_used: 18,
              serper_calls: 18,
              serper_cache_hits: 4,
              pages_fetched: 25,
              providers_searched: [
                'greenhouse',
                'lever',
                'ashby',
                'workable',
                'recruitee',
                'jobberman',
              ],
              providers_skipped: [],
              cached: false,
            },
          ],
        ]),
      });
    });
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.getByLabel('Role or keyword *').fill('Full Stack Developer');
    await page.getByRole('button', { name: /search ats platforms/i }).click();
    if (vp.width < 768) {
      await page.waitForSelector('.mobile-job-card', { timeout: 10000 });
    } else {
      await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
    }
  });

  console.log('Capturing: saved-results...');
  await captureState(targetDir, 'saved-results', async (page, vp) => {
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
    await page.addInitScript(
      ({ jobs, timestamp }) => {
        const payload = {
          rawResults: jobs,
          metrics: {
            total: jobs.length,
            search_time_ms: 1250,
            serper_queries_used: 12,
            serper_calls: 12,
            serper_cache_hits: 2,
            pages_fetched: 18,
            providers_searched: ['greenhouse', 'lever', 'ashby'],
            providers_skipped: [],
            cached: false,
          },
          savedAt: timestamp,
        };
        localStorage.setItem('bp.savedResults', JSON.stringify(payload));
      },
      { jobs: resultsData.slice(0, 15), timestamp: oneDayAgo }
    );
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.waitForSelector('text=Run again', { timeout: 10000 });
    if (vp.width < 768) {
      await page.waitForSelector('.mobile-job-card', { timeout: 10000 });
    } else {
      await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
    }
  });

  console.log('Capturing: no-results...');
  await captureState(targetDir, 'no-results', async (page) => {
    await page.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([
          ['results', { batch: [], total_so_far: 0 }],
          [
            'done',
            {
              total: 0,
              search_time_ms: 850,
              serper_queries_used: 6,
              serper_calls: 6,
              serper_cache_hits: 0,
              pages_fetched: 0,
              providers_searched: ['greenhouse', 'lever'],
              providers_skipped: [],
              cached: false,
            },
          ],
        ]),
      });
    });
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.getByLabel('Role or keyword *').fill('NonExistentJobXYZ');
    await page.getByRole('button', { name: /search ats platforms/i }).click();
    await page.waitForSelector('text=No job postings matched your criteria', { timeout: 10000 });
  });

  console.log('Capturing: error...');
  await captureState(targetDir, 'error', async (page) => {
    await page.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 500,
        body: 'Internal Server Error',
      });
    });
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.getByLabel('Role or keyword *').fill('ErrorTrigger');
    await page.getByRole('button', { name: /search ats platforms/i }).click();
    await page.waitForSelector('text=Search request could not be completed', { timeout: 10000 });
  });

  console.log('Finished capturing all states!');
}

const targetArg = process.argv[2] ? path.resolve(process.cwd(), process.argv[2]) : undefined;
run(targetArg).catch((err) => {
  console.error(err);
  process.exit(1);
});
