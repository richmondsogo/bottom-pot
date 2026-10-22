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

async function captureState(targetDir, stateName, setupPage, theme = 'light') {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
        colorScheme: theme === 'dark' ? 'dark' : 'light',
      });
      const page = await context.newPage();
      await page.addInitScript((t) => {
        localStorage.setItem('bp.theme', t);
      }, theme);
      try {
        await setupPage(page, vp, theme);
        await page.waitForTimeout(400);
        const filename = theme === 'dark' ? `${stateName}_dark_${vp.width}x${vp.height}.png` : `${stateName}_${vp.width}x${vp.height}.png`;
        const filePath = path.join(targetDir, filename);
        await page.screenshot({ path: filePath, fullPage: false });
        console.log(`Saved: ${filename}`);
      } catch (err) {
        console.error(`Error capturing ${stateName} (${theme}) at ${vp.width}x${vp.height}:`, err.message);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}

async function run(targetDir = path.resolve(__dirname, '../docs/design/before-restore')) {
  fs.mkdirSync(targetDir, { recursive: true });

  const themes = ['light', 'dark'];

  for (const theme of themes) {
    console.log(`\n=== Capturing Theme: ${theme.toUpperCase()} ===\n`);

    console.log(`Capturing: landing (${theme})...`);
    await captureState(targetDir, 'landing', async (page) => {
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.evaluate((t) => {
        localStorage.removeItem('bp.savedResults');
        localStorage.removeItem('bp.visitedUrls');
        localStorage.setItem('bp.theme', t);
      }, theme);
      await page.reload({ waitUntil: 'networkidle' });
    }, theme);

    console.log(`Capturing: landing-more-filters (${theme})...`);
    await captureState(targetDir, 'landing-more-filters', async (page) => {
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.evaluate((t) => {
        localStorage.removeItem('bp.savedResults');
        localStorage.removeItem('bp.visitedUrls');
        localStorage.setItem('bp.theme', t);
      }, theme);
      await page.reload({ waitUntil: 'networkidle' });
      const moreBtn = page.getByRole('button', { name: /more filters/i });
      if (await moreBtn.isVisible()) {
        await moreBtn.click();
        await page.waitForTimeout(200);
      }
    }, theme);

    console.log(`Capturing: loading (${theme})...`);
    await captureState(targetDir, 'loading', async (page) => {
      await page.route('**/search?**', () => {});
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.getByLabel(/role or keyword/i).fill('Backend Engineer');
      await page.getByRole('button', { name: /search ats platforms/i }).click();
      await page.waitForSelector('text=Searching ATS platforms', { timeout: 10000 });
    }, theme);

    console.log(`Capturing: results (${theme})...`);
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
                providers_searched: ['greenhouse', 'lever', 'ashby', 'workable', 'recruitee', 'jobberman'],
                providers_skipped: [],
                cached: false,
              },
            ],
          ]),
        });
      });
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.getByLabel(/role or keyword/i).fill('Full Stack Developer');
      await page.getByRole('button', { name: /search ats platforms/i }).click();
      if (vp.width < 768) {
        await page.waitForSelector('.mobile-job-card', { timeout: 10000 });
      } else {
        await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
      }
    }, theme);

    console.log(`Capturing: results-filters-active (${theme})...`);
    await captureState(targetDir, 'results-filters-active', async (page, vp) => {
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
                providers_searched: ['greenhouse', 'lever', 'ashby'],
                providers_skipped: [],
                cached: false,
              },
            ],
          ]),
        });
      });
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.getByLabel(/role or keyword/i).fill('Full Stack Developer');
      await page.getByRole('button', { name: /search ats platforms/i }).click();
      if (vp.width < 768) {
        await page.waitForSelector('.mobile-job-card', { timeout: 10000 });
      } else {
        await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
      }
      const filterInput = page.getByPlaceholder(/filter by role, company/i);
      if (await filterInput.isVisible()) {
        await filterInput.fill('Engineer');
      }
    }, theme);

    console.log(`Capturing: saved-results (${theme})...`);
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
      await page.waitForSelector('text=Edit search', { timeout: 10000 });
      if (vp.width < 768) {
        await page.waitForSelector('.mobile-job-card', { timeout: 10000 });
      } else {
        await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
      }
    }, theme);

    console.log(`Capturing: no-results (${theme})...`);
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
      await page.getByLabel(/role or keyword/i).fill('NonExistentJobXYZ');
      await page.getByRole('button', { name: /search ats platforms/i }).click();
      await page.waitForSelector('text=No job postings matched your criteria', { timeout: 10000 });
    }, theme);

    console.log(`Capturing: error (${theme})...`);
    await captureState(targetDir, 'error', async (page) => {
      await page.route('**/search?**', async (route) => {
        await route.fulfill({
          status: 500,
          body: 'Internal Server Error',
        });
      });
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.getByLabel(/role or keyword/i).fill('ErrorTrigger');
      await page.getByRole('button', { name: /search ats platforms/i }).click();
      await page.waitForSelector('text=Search request could not be completed', { timeout: 10000 });
    }, theme);

    console.log(`Capturing: command-palette (${theme})...`);
    await captureState(targetDir, 'command-palette', async (page) => {
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.keyboard.press('Control+k');
      await page.waitForSelector('input[placeholder*="Type a command or search"]', { timeout: 5000 });
      await page.waitForTimeout(200);
    }, theme);

    console.log(`Capturing: help-modal (${theme})...`);
    await captureState(targetDir, 'help-modal', async (page) => {
      await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
      await page.keyboard.press('?');
      await page.waitForSelector('text=Keyboard shortcuts', { timeout: 5000 });
    }, theme);
  }

  // Capture component crops on 1440x900 viewport
  console.log('\n=== Capturing Component-Level 2x Crops ===\n');
  const cropsDir = path.join(targetDir, 'crops');
  fs.mkdirSync(cropsDir, { recursive: true });

  const cropBrowser = await chromium.launch({ channel: 'chrome' });
  const cropContext = await cropBrowser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: 'light',
  });
  const cropPage = await cropContext.newPage();

  // Landing page crops
  await cropPage.goto('http://127.0.0.1:8000/?mock=default', { waitUntil: 'networkidle' });
  await cropPage.evaluate(() => {
    localStorage.removeItem('bp.savedResults');
    localStorage.removeItem('bp.visitedUrls');
    localStorage.setItem('bp.theme', 'light');
  });
  await cropPage.reload({ waitUntil: 'networkidle' });

  // 1. Header crop
  const header = cropPage.locator('header');
  if (await header.isVisible()) {
    await header.screenshot({ path: path.join(cropsDir, 'crop_header.png') });
  }

  // 2. Hero region crop
  const hero = cropPage.locator('.hero-region');
  if (await hero.isVisible()) {
    await hero.screenshot({ path: path.join(cropsDir, 'crop_hero.png') });
  }

  // 3. Form card crop
  const formCard = cropPage.locator('.search-form-card');
  if (await formCard.isVisible()) {
    await formCard.screenshot({ path: path.join(cropsDir, 'crop_form_panel.png') });
  }

  // 4. Role input crop
  const roleInput = cropPage.locator('#keywords-input');
  if (await roleInput.isVisible()) {
    await roleInput.screenshot({ path: path.join(cropsDir, 'crop_role_input.png') });
  }

  // 5. Suggestion chips crop
  const suggestions = cropPage.locator('button:has-text("Backend Engineer")').first().locator('xpath=..');
  if (await suggestions.isVisible()) {
    await suggestions.screenshot({ path: path.join(cropsDir, 'crop_suggestions.png') });
  }

  // 6. Platform chips grid crop
  const platformGrid = cropPage.locator('button:has-text("Greenhouse")').first().locator('xpath=ancestor::div[contains(@class, "grid")]');
  if (await platformGrid.isVisible()) {
    await platformGrid.screenshot({ path: path.join(cropsDir, 'crop_platform_chips.png') });
  }

  // 7. More filters panel crop
  const moreFiltersBtn = cropPage.getByRole('button', { name: /more filters/i });
  if (await moreFiltersBtn.isVisible()) {
    await moreFiltersBtn.click();
    await cropPage.waitForTimeout(200);
    const filtersPanel = cropPage.locator('[data-slot="collapsible-content"]');
    if (await filtersPanel.isVisible()) {
      await filtersPanel.screenshot({ path: path.join(cropsDir, 'crop_more_filters_panel.png') });
    }
  }

  // Results page crops (mocked route)
  await cropPage.route('**/search?**', async (route) => {
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
            providers_searched: ['greenhouse', 'lever', 'ashby', 'workable', 'recruitee', 'jobberman'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await cropPage.getByLabel(/role or keyword/i).fill('Full Stack Developer');
  const searchBtn = cropPage.getByRole('button', { name: /search ats platforms/i });
  await searchBtn.click();
  await cropPage.waitForSelector('.results-table tbody tr', { timeout: 10000 });
  await cropPage.waitForTimeout(300);

  // 8. Search summary row crop
  const summaryRow = cropPage.locator('.search-summary-bar');
  if (await summaryRow.isVisible()) {
    await summaryRow.screenshot({ path: path.join(cropsDir, 'crop_summary_row.png') });
  }

  // 9. Toolbar crop
  const toolbar = cropPage.locator('#table-search-input').locator('xpath=ancestor::div[contains(@class, "border-b")]');
  if (await toolbar.isVisible()) {
    await toolbar.screenshot({ path: path.join(cropsDir, 'crop_toolbar.png') });
  }

  // 10. Results table header + rows crop
  const table = cropPage.locator('.results-table');
  if (await table.isVisible()) {
    await table.screenshot({ path: path.join(cropsDir, 'crop_results_table.png') });
  }

  // 11. Command palette crop
  await cropPage.keyboard.press('Control+k');
  await cropPage.waitForTimeout(200);
  const cmdDialog = cropPage.getByRole('dialog');
  if (await cmdDialog.isVisible()) {
    await cmdDialog.screenshot({ path: path.join(cropsDir, 'crop_command_palette.png') });
    await cropPage.keyboard.press('Escape');
    await cropPage.waitForTimeout(200);
  }

  await cropPage.close();

  // 12. Loading skeleton crop
  const loadPage = await cropBrowser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await loadPage.route('**/search?**', () => {}); // stays pending
  await loadPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
  await loadPage.getByLabel(/role or keyword/i).fill('Backend Engineer');
  await loadPage.getByRole('button', { name: /search ats platforms/i }).click();
  await loadPage.waitForSelector('.results-table', { timeout: 10000 });
  await loadPage.waitForTimeout(200);
  const loadingTable = loadPage.locator('.results-table');
  if (await loadingTable.isVisible()) {
    await loadingTable.screenshot({ path: path.join(cropsDir, 'crop_loading_skeleton.png') });
  }
  await loadPage.close();

  // 13. Empty state crop
  const emptyPage = await cropBrowser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await emptyPage.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['done', { total: 0, search_time_ms: 450, providers_searched: ['greenhouse'], providers_skipped: [] }]
      ])
    });
  });
  await emptyPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
  await emptyPage.getByLabel(/role or keyword/i).fill('Nonexistent Role');
  await emptyPage.getByRole('button', { name: /search ats platforms/i }).click();
  await emptyPage.waitForSelector('text=No job postings matched', { timeout: 10000 });
  const emptyCard = emptyPage.locator('[data-slot="empty"]');
  if (await emptyCard.isVisible()) {
    await emptyCard.screenshot({ path: path.join(cropsDir, 'crop_empty_state.png') });
  }
  await emptyPage.close();

  // 14. Error state crop
  const errorPage = await cropBrowser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await errorPage.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 500,
      body: 'Internal Server Error',
    });
  });
  await errorPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
  await errorPage.getByLabel(/role or keyword/i).fill('ErrorTrigger');
  await errorPage.getByRole('button', { name: /search ats platforms/i }).click();
  await errorPage.waitForSelector('text=Search request could not be completed', { timeout: 10000 });
  const errorCard = errorPage.locator('[data-slot="empty"]');
  if (await errorCard.isVisible()) {
    await errorCard.screenshot({ path: path.join(cropsDir, 'crop_error_state.png') });
  }
  await errorPage.close();

  await cropContext.close();
  await cropBrowser.close();
  console.log('✓ Component-level crops captured into ' + cropsDir);

  console.log('Finished capturing all states into ' + targetDir);
}

const args = process.argv.slice(2);
const cropsOnly = args.includes('--crops-only');
const nonFlagArgs = args.filter(a => !a.startsWith('--'));
const targetArg = nonFlagArgs[0] ? path.resolve(process.cwd(), nonFlagArgs[0]) : undefined;

if (cropsOnly) {
  (async () => {
    const targetDir = targetArg || path.resolve(process.cwd(), 'docs/design/before-restore');
    const cropsDir = path.join(targetDir, 'crops');
    if (!fs.existsSync(cropsDir)) fs.mkdirSync(cropsDir, { recursive: true });
    const browser = await chromium.launch({ channel: 'chrome' });
    const context = await browser.newContext({ deviceScaleFactor: 2 });
    const page = await context.newPage();
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('http://127.0.0.1:8000/?mock=default', { waitUntil: 'networkidle' });
    await page.evaluate(() => {
      localStorage.removeItem('bp.savedResults');
      localStorage.removeItem('bp.visitedUrls');
      localStorage.setItem('bp.theme', 'light');
    });
    await page.reload({ waitUntil: 'networkidle' });

    // Header
    const header = page.locator('header');
    if (await header.isVisible()) await header.screenshot({ path: path.join(cropsDir, 'crop_header.png') });

    // Hero
    const hero = page.locator('.hero-region');
    if (await hero.isVisible()) await hero.screenshot({ path: path.join(cropsDir, 'crop_hero.png') });

    // Form
    const formCard = page.locator('.search-form-card');
    if (await formCard.isVisible()) await formCard.screenshot({ path: path.join(cropsDir, 'crop_form_panel.png') });

    // Role input
    const roleInput = page.locator('#keywords-input');
    if (await roleInput.isVisible()) await roleInput.screenshot({ path: path.join(cropsDir, 'crop_role_input.png') });

    // Suggestions
    const suggestions = page.locator('button:has-text("Backend Engineer")').first().locator('xpath=..');
    if (await suggestions.isVisible()) await suggestions.screenshot({ path: path.join(cropsDir, 'crop_suggestions.png') });

    // More filters & Platform chips
    const moreFiltersBtn = page.getByRole('button', { name: /more filters/i });
    if (await moreFiltersBtn.isVisible()) {
      await moreFiltersBtn.click();
      await page.waitForTimeout(200);
      const filtersPanel = page.locator('[data-slot="collapsible-content"]');
      if (await filtersPanel.isVisible()) await filtersPanel.screenshot({ path: path.join(cropsDir, 'crop_more_filters_panel.png') });
      const platformGrid = page.locator('.platform-chips-grid');
      if (await platformGrid.isVisible()) await platformGrid.screenshot({ path: path.join(cropsDir, 'crop_platform_chips.png') });
    }

    // Results crops
    await page.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([
          ['results', { batch: resultsData.slice(0, 20), total_so_far: 20 }],
          ['results', { batch: resultsData.slice(20), total_so_far: resultsData.length }],
          ['done', { total: resultsData.length, search_time_ms: 1420, providers_searched: ['greenhouse', 'lever'], providers_skipped: [] }]
        ])
      });
    });

    await page.getByLabel(/role or keyword/i).fill('Full Stack Developer');
    await page.getByRole('button', { name: /search ats platforms/i }).click();
    await page.waitForSelector('.results-table tbody tr', { timeout: 10000 });
    await page.waitForTimeout(300);

    const summaryRow = page.locator('.search-summary-bar');
    if (await summaryRow.isVisible()) await summaryRow.screenshot({ path: path.join(cropsDir, 'crop_summary_row.png') });

    const toolbar = page.locator('#table-search-input').locator('xpath=ancestor::div[contains(@class, "border-b")]');
    if (await toolbar.isVisible()) await toolbar.screenshot({ path: path.join(cropsDir, 'crop_toolbar.png') });

    await page.evaluate(() => {
      const thead = document.querySelector('.results-table thead');
      if (thead) {
        const headerHeight = document.querySelector('header')?.getBoundingClientRect().height || 56;
        const summaryHeight = document.querySelector('.search-summary-bar')?.getBoundingClientRect().height || 56;
        const topOffset = headerHeight + summaryHeight;
        const theadY = thead.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({ top: theadY - topOffset, behavior: 'instant' });
      }
    });
    await page.waitForTimeout(200);

    const thead = page.locator('.results-table thead');
    const row3 = page.locator('.results-table tbody tr').nth(2);
    const theadBox = await thead.boundingBox();
    const row3Box = await row3.boundingBox();
    if (theadBox && row3Box) {
      await page.screenshot({
        path: path.join(cropsDir, 'crop_table_header_and_three_rows.png'),
        clip: {
          x: theadBox.x,
          y: theadBox.y,
          width: theadBox.width,
          height: (row3Box.y + row3Box.height) - theadBox.y,
        },
      });
    }

    const table = page.locator('.results-table');
    if (await table.isVisible()) await table.screenshot({ path: path.join(cropsDir, 'crop_results_table.png') });

    // Tags crop (work model badge in row 1)
    const tagLocator = page.locator('.results-table tbody tr').first().locator('span.inline-flex, [data-slot="badge"]').first();
    if (await tagLocator.isVisible()) {
      await tagLocator.screenshot({ path: path.join(cropsDir, 'crop_tags.png') });
    }

    // Command palette
    await page.keyboard.press('Control+k');
    await page.waitForTimeout(200);
    const cmdDialog = page.getByRole('dialog');
    if (await cmdDialog.isVisible()) {
      await cmdDialog.screenshot({ path: path.join(cropsDir, 'crop_command_palette.png') });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(200);
    }

    await page.close();

    // Loading skeleton
    const loadPage = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await loadPage.route('**/search?**', () => {});
    await loadPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await loadPage.getByLabel(/role or keyword/i).fill('Backend Engineer');
    await loadPage.getByRole('button', { name: /search ats platforms/i }).click();
    await loadPage.waitForSelector('.results-table', { timeout: 10000 });
    const loadingTable = loadPage.locator('.results-table');
    if (await loadingTable.isVisible()) await loadingTable.screenshot({ path: path.join(cropsDir, 'crop_loading_skeleton.png') });
    await loadPage.close();

    // Empty state
    const emptyPage = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await emptyPage.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([['done', { total: 0, search_time_ms: 450, providers_searched: ['greenhouse'], providers_skipped: [] }]])
      });
    });
    await emptyPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await emptyPage.getByLabel(/role or keyword/i).fill('Nonexistent Role');
    await emptyPage.getByRole('button', { name: /search ats platforms/i }).click();
    await emptyPage.waitForSelector('text=No job postings matched', { timeout: 10000 });
    const emptyCard = emptyPage.locator('[data-slot="empty"]');
    if (await emptyCard.isVisible()) await emptyCard.screenshot({ path: path.join(cropsDir, 'crop_empty_state.png') });
    await emptyPage.close();

    // Error state
    const errorPage = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await errorPage.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 500,
        body: 'Internal Server Error',
      });
    });
    await errorPage.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await errorPage.getByLabel(/role or keyword/i).fill('ErrorTrigger');
    await errorPage.getByRole('button', { name: /search ats platforms/i }).click();
    await errorPage.waitForSelector('text=Search request could not be completed', { timeout: 10000 });
    const errorCard = errorPage.locator('[data-slot="empty"]');
    if (await errorCard.isVisible()) await errorCard.screenshot({ path: path.join(cropsDir, 'crop_error_state.png') });
    await errorPage.close();

    await context.close();
    await browser.close();
    console.log('✓ Successfully captured all component crops into ' + cropsDir);
  })().catch(err => {
    console.error(err);
    process.exit(1);
  });
} else {
  run(targetArg).catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
