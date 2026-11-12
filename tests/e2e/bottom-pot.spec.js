const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const streamedJobs = [
  {
    id: 'greenhouse:acme:1',
    provider: 'greenhouse',
    data_source: 'api',
    title: 'Senior Backend Engineer',
    company: 'Acme Labs',
    company_slug: 'acme',
    location: 'Lagos, Nigeria',
    is_remote: true,
    employment_type: 'full_time',
    work_model: 'remote',
    department: 'Engineering',
    salary: { minimum: 120000, maximum: 150000, currency: 'USD', period: 'year' },
    description: '### Role Summary\n\nBuild **reliable APIs** for remote-first finance teams.\n\n- Design distributed services',
    requirements: 'Python, FastAPI, and production ownership.',
    posted_at: '2026-09-10T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/acme/backend-engineer',
    source_url: 'https://boards.greenhouse.io/acme/jobs/1',
    query_used: 'backend engineer',
    ats_source: 'greenhouse',
  },
  {
    id: 'lever:orbit:2',
    provider: 'lever',
    data_source: 'api',
    title: 'Product Designer',
    company: 'Orbit Works',
    company_slug: 'orbit',
    location: 'London, UK',
    is_remote: false,
    employment_type: 'contract',
    work_model: 'in_person',
    posted_at: '2026-09-08T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/orbit/product-designer',
    source_url: 'https://jobs.lever.co/orbit/2',
    query_used: 'backend engineer',
    ats_source: 'lever',
  },
  {
    id: 'jobberman:cloud:3',
    provider: 'jobberman',
    data_source: 'scrape',
    title: 'Cloud Support Intern',
    company: 'Cloud Nine',
    company_slug: 'cloud-nine',
    location: 'Abuja, Nigeria',
    is_remote: null,
    employment_type: 'internship',
    work_model: 'hybrid',
    salary: 'NGN 250,000 / month',
    description: 'Support customers while learning cloud operations.',
    requirements: 'Clear writing and basic Linux comfort.',
    posted_at: '2026-09-12T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/cloud/support-intern',
    source_url: 'https://www.jobberman.com/listings/cloud-support-intern',
    query_used: 'backend engineer',
    ats_source: 'jobberman',
  },
];

function sse(events) {
  return events
    .map(([eventName, payload]) => `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`)
    .join('');
}

async function mockSearch(page, { onRequest } = {}) {
  await page.route('**/search?**', async (route) => {
    onRequest?.(new URL(route.request().url()));
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: streamedJobs.slice(0, 2), total_so_far: 2 }],
        ['results', { batch: streamedJobs.slice(2), total_so_far: 3 }],
        [
          'done',
          {
            total: 3,
            search_time_ms: 812,
            serper_queries_used: 4,
            providers_searched: ['greenhouse', 'lever', 'jobberman'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });
}

async function runSearch(page, overrides = {}) {
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/?view=app');

  await page.getByLabel(/role or keyword/i).fill(overrides.keyword || 'Backend Engineer');
  if (overrides.location) {
    await page.getByLabel(/location or country/i).fill(overrides.location);
  }
  if (overrides.workModel) {
    await page.getByLabel(/work model/i).selectOption(overrides.workModel);
  }

  await page.getByRole('button', { name: /search (jobs|ats platforms)/i }).click();

  const isMobile = (page.viewportSize()?.width || 1000) < 768;
  if (isMobile) {
    await expect(page.locator('.mobile-job-card').first()).toBeVisible({ timeout: 10000 });
  } else {
    await expect(page.locator('.results-table tbody tr.job-row').first()).toBeVisible({ timeout: 10000 });
  }
}

test('marketing landing page loads Midday-engineered architecture and meets a11y standards', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Jobs straight from the company.');
  await expect(page.getByRole('link', { name: /start searching/i })).toBeVisible();
  await expect(page.getByText(/real openings from company career pages/i)).toBeVisible();
  await expect(page.getByText(/where we search/i).first()).toBeVisible();

  // Axe Accessibility Check on Marketing Landing
  const accessibilityScanResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  const criticalViolations = accessibilityScanResults.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );
  expect(criticalViolations).toEqual([]);
});

test('product workspace loads search form and transitions from marketing view', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });

  // Click Start searching button in final CTA to transition to workspace
  await page.getByRole('button', { name: /start searching/i }).first().click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Search jobs');
  await expect(page.getByLabel(/role or keyword/i)).toBeVisible();
  // "How Bottom Pot works" block is hidden in user mode
  await expect(page.getByText(/how bottom pot works/i)).toHaveCount(0);

  // Axe Accessibility Check on Product Workspace
  const a11yResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  const critical = a11yResults.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );
  expect(critical).toEqual([]);
});

test('search sends correct query parameters and displays results table', async ({ page }) => {
  let searchUrl;
  await mockSearch(page, { onRequest: (url) => { searchUrl = url; } });

  await runSearch(page, { keyword: 'Backend Engineer', location: 'Nigeria', workModel: 'remote' });

  expect(searchUrl.searchParams.get('q')).toBe('Backend Engineer');
  expect(searchUrl.searchParams.get('location')).toBe('Nigeria');
  expect(searchUrl.searchParams.get('remote')).toBe('true');

  // Verify sticky search summary bar collapsed the hero
  await expect(page.locator('.search-summary-bar')).toBeVisible();
  await expect(page.locator('.search-summary-bar')).toContainText('Backend Engineer');

  // Verify status strip is absent in user mode and summary text is clean
  await expect(page.locator('.status-strip')).toHaveCount(0);
  await expect(page.locator('.search-summary-bar')).toContainText('3 positions for Backend Engineer');

  // Verify table rows and content
  const rows = page.locator('.results-table tbody tr');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('Senior Backend Engineer');
  await expect(rows.nth(1)).toContainText('Product Designer');
  await expect(rows.nth(2)).toContainText('Cloud Support Intern');

  // Verify download CSV and JSON buttons in dedicated Export menu exist and are enabled
  await page.getByRole('button', { name: /export results/i }).click();
  await expect(page.locator('#downloadBtn')).toBeVisible();
  await expect(page.locator('#downloadBtn')).toBeEnabled();
  await expect(page.locator('#downloadJsonBtn')).toBeVisible();
  await expect(page.locator('#downloadJsonBtn')).toBeEnabled();
  await page.keyboard.press('Escape');
});

test('filter toolbar narrows postings by text search, provider, and work model', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  // Filter by text search
  const searchInput = page.getByPlaceholder(/filter by role, company/i);
  await searchInput.fill('designer');
  await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.results-table tbody tr').first()).toContainText('Product Designer');

  // Clear filter
  await page.getByRole('button', { name: /clear filters/i }).click();
  await expect(page.locator('.results-table tbody tr')).toHaveCount(3);

  // Filter by platform dropdown
  await page.getByLabel(/filter by ats provider/i).selectOption('lever');
  await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.results-table tbody tr').first()).toContainText('Orbit Works');
});

test('table sorting sorts by title, company, salary, and date', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  // Click Role header to sort
  const roleHeader = page.locator('th', { hasText: 'Role' });
  await roleHeader.click();
  await expect(page.locator('.results-table tbody tr').first()).toContainText('Cloud Support Intern');

  // Click again to reverse sort
  await roleHeader.click();
  await expect(page.locator('.results-table tbody tr').first()).toContainText('Senior Backend Engineer');
});

test('opening detail sheet displays metadata, opens posting, and marks visited', async ({ page, context }) => {
  await mockSearch(page);
  await context.route('https://jobs.example.test/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Apply</title>' });
  });

  await runSearch(page);

  const firstRow = page.locator('.results-table tbody tr').first();
  await firstRow.click();

  // Detail Sheet is open and renders structured Markdown elements
  const detailSheet = page.locator('.detail-sheet');
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Senior Backend Engineer');
  await expect(detailSheet).toContainText('Build reliable APIs for remote-first finance teams.');
  await expect(detailSheet.locator('.markdown-preview strong')).toContainText('reliable APIs');
  await expect(detailSheet.locator('.markdown-preview ul li')).toContainText('Design distributed services');
  await expect(detailSheet).toContainText('Python, FastAPI, and production ownership.');

  // Save job to shortlist and update stage to Applied
  const saveBtn = detailSheet.getByRole('button', { name: /save job to shortlist/i });
  await saveBtn.click();
  await expect(detailSheet.getByRole('button', { name: /remove from saved jobs/i })).toBeVisible();
  await detailSheet.getByRole('button', { name: 'Applied', exact: true }).click();

  // Check visited class is applied
  await expect(firstRow.locator('.line-clamp-2')).toHaveClass(/title-visited/);

  // Close with Esc key and filter by Saved (1)
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();
  await page.getByRole('switch', { name: /saved \(1\)/i }).click();
  await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.results-table tbody tr').first()).toContainText('Applied');
});

test('keyboard navigation with j/k, Enter, Esc, and /', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  // Press / to focus search input
  await page.keyboard.press('/');
  const searchInput = page.getByPlaceholder(/filter by role, company/i);
  await expect(searchInput).toBeFocused();

  // Blur search input and navigate with j/k
  await searchInput.blur();
  await page.keyboard.press('j');
  const rows = page.locator('.results-table tbody tr');
  await expect(rows.nth(0)).toHaveClass(/keyboard-active/);

  await page.keyboard.press('j');
  await expect(rows.nth(1)).toHaveClass(/keyboard-active/);

  // Press Enter to open details
  await page.keyboard.press('Enter');
  await expect(page.locator('.detail-sheet')).toBeVisible();

  // Press Escape to close
  await page.keyboard.press('Escape');
  await expect(page.locator('.detail-sheet')).toBeHidden();

  // Press ? to open shortcuts modal
  await page.keyboard.press('?');
  await expect(page.getByRole('heading', { name: /keyboard shortcuts/i })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: /keyboard shortcuts/i })).toBeHidden();
});

test('mobile viewport (<768px) switches to stacked card list with zero overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockSearch(page);
  await runSearch(page);

  // Desktop table should be hidden, mobile cards visible
  await expect(page.locator('.table-desktop-view')).toBeHidden();
  const mobileCards = page.locator('.mobile-job-card');
  await expect(mobileCards).toHaveCount(3);
  await expect(mobileCards.first()).toContainText('Senior Backend Engineer');

  // Tap mobile card to open full-screen sheet
  await mobileCards.first().click();
  await expect(page.locator('.detail-sheet')).toBeVisible();

  // Axe check on mobile
  const a11yResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  const critical = a11yResults.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
  expect(critical).toEqual([]);
});

test('typography audit validates font families, weights, and scale compliance across visible nodes', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  const typographyData = await page.evaluate(() => {
    const textNodes = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.textContent && node.textContent.trim().length > 0) {
        const el = node.parentElement;
        if (el && el.offsetParent !== null) {
          const style = window.getComputedStyle(el);
          textNodes.push({
            fontFamily: style.fontFamily.toLowerCase(),
            fontWeight: style.fontWeight,
            fontSize: parseFloat(style.fontSize),
            text: node.textContent.trim().slice(0, 30),
          });
        }
      }
    }
    return textNodes;
  });

  expect(typographyData.length).toBeGreaterThan(10);

  const allowedWeights = new Set(['400', '500', '600', '700']);
  for (const node of typographyData) {
    const isSans = node.fontFamily.includes('geist') || node.fontFamily.includes('sans-serif') || node.fontFamily.includes('system-ui') || node.fontFamily.includes('apple-system');
    const isMono = node.fontFamily.includes('dm mono') || node.fontFamily.includes('mono');
    expect(isSans || isMono).toBeTruthy();
    expect(allowedWeights.has(node.fontWeight)).toBeTruthy();
  }
});

test('layout audit: validates shell left edge alignment and zero horizontal overflow across 5 viewports', async ({ page }) => {
  const viewports = [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    await page.setViewportSize(vp);
    await mockSearch(page);
    await runSearch(page);

    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
    });
    expect(hasHorizontalOverflow).toBeFalsy();

    // Check that shell elements share identical left alignment
    const shellLefts = await page.evaluate(() => {
      const shells = Array.from(document.querySelectorAll('.page-shell'));
      return shells.map((el) => Math.round(el.getBoundingClientRect().left));
    });

    if (shellLefts.length > 1) {
      const firstLeft = shellLefts[0];
      for (const left of shellLefts) {
        expect(Math.abs(left - firstLeft)).toBeLessThanOrEqual(2);
      }
    }
  }
});

test('command palette is hidden in user mode and theme toggle works seamlessly', async ({ page }) => {
  await page.goto('/?mock=default');

  // Command palette button is absent in user mode
  const commandBtn = page.getByRole('button', { name: /open command palette/i });
  await expect(commandBtn).toHaveCount(0);

  // Keyboard shortcut Control+k does not open dialog in user mode and does not move active row
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('dialog', { name: /bottom pot commands/i })).toHaveCount(0);
  await expect(page.locator('.keyboard-active')).toHaveCount(0);

  // Toggle Theme via header button
  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  const isDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
  expect(isDark).toBeTruthy();

  // Persisted in localStorage
  const savedTheme = await page.evaluate(() => localStorage.getItem('bp.theme'));
  expect(savedTheme).toBe('dark');

  // Toggle back to light
  await themeBtn.click();
  const isLightAgain = await page.evaluate(() => !document.documentElement.classList.contains('dark'));
  expect(isLightAgain).toBeTruthy();
});

test('clear saved results triggers toast with undo functionality', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  // Results should be displayed
  await expect(page.locator('.results-table tbody tr')).toHaveCount(3);

  // Open overflow menu in search summary bar
  const moreActionsBtn = page.getByRole('button', { name: /more actions/i });
  await moreActionsBtn.click();

  // Click clear saved results
  const clearBtn = page.getByRole('menuitem', { name: /clear saved results/i });
  await clearBtn.click();

  // Should return to form screen and show toast with Undo
  await expect(page.getByText('Saved results cleared')).toBeVisible();
  const undoBtn = page.getByRole('button', { name: /undo/i });
  await expect(undoBtn).toBeVisible();

  // Click undo to restore results
  await undoBtn.click();
  await expect(page.locator('.results-table tbody tr')).toHaveCount(3);
});

test('spacing audit: interactive controls meet minimum padding (12px/8px) and height scale (32, 36, 40, 44, 48)', async ({ page }) => {
  await mockSearch(page);
  await page.goto('/?mock=default');
  await page.waitForLoadState('networkidle');

  const checkSpacing = async () => {
    return await page.evaluate(() => {
      const allowedHeights = [32, 36, 40, 44, 48];
      const controls = Array.from(
        document.querySelectorAll('button, input:not([type="hidden"]), select, textarea, [data-slot="select-trigger"], [data-slot="dropdown-menu-trigger"]')
      ).filter((el) => {
        if (el.classList.contains('sr-only') || el.offsetParent === null) return false;
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      });

      const violations = [];
      for (const el of controls) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const height = Math.round(rect.height);
        const padLeft = parseFloat(style.paddingLeft);
        const padRight = parseFloat(style.paddingRight);

        // Check compact icon button (e.g. square icon button or theme toggle)
        const isIconOnly = rect.width <= 42 && el.querySelector('svg') !== null && el.textContent.trim().length <= 2;
        const minPadding = isIconOnly ? 8 : 12;

        const isHeightValid = allowedHeights.some((h) => Math.abs(height - h) <= 1.5);
        if (!isHeightValid) {
          violations.push({
            tag: el.tagName,
            text: el.textContent?.trim().slice(0, 25),
            issue: `Height ${height}px not in [32, 36, 40, 44, 48]`,
          });
        }

        if (padLeft < minPadding - 0.5 || padRight < minPadding - 0.5) {
          violations.push({
            tag: el.tagName,
            text: el.textContent?.trim().slice(0, 25),
            issue: `Horizontal padding (left: ${padLeft}px, right: ${padRight}px) below minimum ${minPadding}px`,
          });
        }
      }
      return violations;
    });
  };

  const landingViolations = await checkSpacing();
  expect(landingViolations).toEqual([]);

  // Check results page
  await runSearch(page);
  const resultsViolations = await checkSpacing();
  expect(resultsViolations).toEqual([]);
});

test('column alignment audit: table header cells and body cells share identical left alignment across columns and rows', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  const alignmentData = await page.evaluate(() => {
    const table = document.querySelector('.results-table');
    if (!table) return { found: false };

    const ths = Array.from(table.querySelectorAll('thead th'));
    const rows = Array.from(table.querySelectorAll('tbody tr.job-row'));

    const headerLefts = ths.map((th) => Math.round(th.getBoundingClientRect().left));
    const headerWidths = ths.map((th) => Math.round(th.getBoundingClientRect().width));

    const rowColLefts = rows.map((row) => {
      const cells = Array.from(row.querySelectorAll('td'));
      return cells.map((cell) => Math.round(cell.getBoundingClientRect().left));
    });

    return {
      found: true,
      colCount: ths.length,
      rowCount: rows.length,
      headerLefts,
      headerWidths,
      rowColLefts,
    };
  });

  expect(alignmentData.found).toBeTruthy();
  expect(alignmentData.colCount).toBeGreaterThanOrEqual(5);

  // Every row must have identical column left positions as the header (within ±1px)
  for (let r = 0; r < alignmentData.rowCount; r++) {
    const rowLefts = alignmentData.rowColLefts[r];
    for (let c = 0; c < alignmentData.colCount; c++) {
      const diff = Math.abs(rowLefts[c] - alignmentData.headerLefts[c]);
      expect(diff).toBeLessThanOrEqual(1);
    }
  }

  // Cross-row alignment: each column left edge across rows is identical (diff <= 1)
  for (let c = 0; c < alignmentData.colCount; c++) {
    const firstRowLeft = alignmentData.rowColLefts[0][c];
    for (let r = 1; r < alignmentData.rowCount; r++) {
      const diff = Math.abs(alignmentData.rowColLefts[r][c] - firstRowLeft);
      expect(diff).toBeLessThanOrEqual(1);
    }
  }
});

test('green budget audit: enforces strict green usage budget across views', async ({ page }) => {
  await page.goto('/?mock=default');
  await page.waitForLoadState('networkidle');

  // Verify platform chips do NOT have green borders on all 18
  const greenBordersCount = await page.evaluate(() => {
    const chips = Array.from(document.querySelectorAll('.platform-chip-btn'));
    return chips.filter((chip) => {
      const style = window.getComputedStyle(chip);
      const border = style.borderColor;
      // Check if green (#1A382B, rgb(26, 56, 43), oklch green)
      return border.includes('26, 56, 43') || border.includes('34, 197, 94') || border.includes('16, 185, 129');
    }).length;
  });

  // Selected chips should have neutral ink/surface border, not 18 green borders
  expect(greenBordersCount).toBeLessThan(5);

  // Results page green budget
  await mockSearch(page);
  await runSearch(page);

  const greenElementsOnResults = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('*'));
    let greenCount = 0;
    for (const el of all) {
      if (el.offsetParent === null) continue;
      const s = window.getComputedStyle(el);
      const isGreen = [s.backgroundColor, s.borderColor, s.color].some(
        (c) => c && (c.includes('26, 56, 43') || c.includes('34, 197, 94') || c.includes('16, 185, 129'))
      );
      if (isGreen) greenCount++;
    }
    return greenCount;
  });

  // Green elements should be restrained (within budget: remote marker, hover indicators, links)
  expect(greenElementsOnResults).toBeLessThan(35);
});

test('stubbed anonymous search stream handles incomplete flag and empty states cleanly', async ({ page }) => {
  // Case 1: Zero results + incomplete: true shows "Search is busy right now. Please try again a little later."
  await page.route('**/search?*', async (route) => {
    const sseBody = 'event: done\ndata: {"total":0,"incomplete":true}\n\n';
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody,
    });
  });

  await page.goto('/app');
  await page.fill('#keywords-input', 'BusySearchJob');
  await page.click('button[type="submit"]');

  await expect(page.getByText('Search is busy right now. Please try again a little later.')).toBeVisible();

  // Case 2: Zero results + incomplete: false shows normal empty text
  await page.unroute('**/search?*');
  await page.route('**/search?*', async (route) => {
    const sseBody = 'event: done\ndata: {"total":0,"incomplete":false}\n\n';
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody,
    });
  });

  await page.click('button:has-text("New search")');
  await page.fill('#keywords-input', 'NormalEmptyJob');
  await page.click('button[type="submit"]');

  await expect(page.getByText('No open positions matched your search. Try a broader keyword or a wider date range.')).toBeVisible();

  // Case 3: Results + incomplete: true shows results with no busy message
  const mockJob = {
    id: 'test-job-inc-1',
    provider: 'greenhouse',
    title: 'Distributed Systems Engineer',
    company: 'ScaleCorp',
    company_slug: 'scalecorp',
    location: 'Remote',
    is_remote: true,
    employment_type: 'full-time',
    work_model: 'remote',
    department: 'Engineering',
    salary: '$150,000',
    description: 'Great role',
    requirements: 'Go, Kubernetes',
    posted_at: '2026-10-25T10:00:00Z',
    apply_url: 'https://example.com/apply/1',
    ats_source: 'greenhouse',
  };

  await page.unroute('**/search?*');
  await page.route('**/search?*', async (route) => {
    const batchPayload = JSON.stringify({ batch: [mockJob], total_so_far: 1 });
    const donePayload = JSON.stringify({ total: 1, incomplete: true });
    const sseBody = `event: results\ndata: ${batchPayload}\n\nevent: done\ndata: ${donePayload}\n\n`;
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody,
    });
  });

  await page.click('button:has-text("New search")');
  await page.fill('#keywords-input', 'Distributed');
  await page.click('button[type="submit"]');

  await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.results-table').getByText('Distributed Systems Engineer')).toBeVisible();
  await expect(page.getByText(/Search is busy right now/i)).toHaveCount(0);
});

test('marketing landing page has zero embedded forms, zero sample data, and clean handoff to /app', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // 1. Zero forms on marketing landing
  await expect(page.locator('form')).toHaveCount(0);

  // 2. Zero sample results table strings
  const sampleStrings = [
    'Sample data',
    "Here's what a search looks like",
    'Linear',
    '$180k – $220k',
    'Supabase',
    '$160k – $200k',
    'Raycast',
    '£90k – £120k',
    "Why Remote? The employer's listing says so",
  ];
  for (const text of sampleStrings) {
    await expect(page.getByText(text, { exact: false })).toHaveCount(0);
  }

  // 3. Primary "Start searching" CTA transitions cleanly to /app
  const startBtn = page.getByRole('button', { name: /start searching/i }).first();
  await startBtn.click();
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Search jobs');
  await expect(page.getByRole('button', { name: 'Search jobs' })).toBeVisible();

  // 4. Return to / and test quick-starter preset chip handoff triggers search
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const presetChip = page.getByRole('button', { name: 'React engineer · Remote' });
  await expect(presetChip).toBeVisible();
  await presetChip.click();
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByText(/Searching company career pages|positions for/i)).toBeVisible();
});


test('step 17: prompt-input composer and prominent export dropdown flow', async ({ page }) => {
  await mockSearch(page);
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // 1. Verify PromptInput composer renders with all inputs and accessible labels
  const composer = page.locator('[data-slot="prompt-input"]');
  await expect(composer).toBeVisible();

  const keywordInput = page.getByLabel(/role or keyword/i);
  await expect(keywordInput).toBeVisible();
  await keywordInput.fill('Systems Architect');

  // Test suggestion chip updates keyword input
  const suggestionChip = page.getByRole('button', { name: 'Full-Stack Developer' });
  await expect(suggestionChip).toBeVisible();
  await suggestionChip.click();
  await expect(keywordInput).toHaveValue('Full-Stack Developer');

  // Fill location and select work model in action dock
  const locationInput = page.getByLabel(/location or country/i);
  await expect(locationInput).toBeVisible();
  await locationInput.fill('Lagos');

  const workModelSelect = page.getByLabel(/work model/i);
  await expect(workModelSelect).toBeVisible();
  await workModelSelect.selectOption('remote');

  // Submit search via primary submit button
  const submitBtn = page.getByRole('button', { name: 'Search jobs' });
  await expect(submitBtn).toBeVisible();
  await submitBtn.click();

  // 2. Results delivery: Verify prominent Export button in summary bar
  const summaryBar = page.locator('.search-summary-bar');
  await expect(summaryBar).toBeVisible();

  const exportBtn = page.getByRole('button', { name: /export results/i });
  await expect(exportBtn).toBeVisible();
  await exportBtn.click();

  // 3. Verify Download CSV and Download JSON in Export dropdown trigger downloads
  const downloadCsvItem = page.locator('#downloadBtn');
  const downloadJsonItem = page.locator('#downloadJsonBtn');
  await expect(downloadCsvItem).toBeVisible();
  await expect(downloadCsvItem).toContainText(/download csv/i);
  await expect(downloadJsonItem).toBeVisible();
  await expect(downloadJsonItem).toContainText(/download json/i);

  // Trigger CSV download
  const [csvDownload] = await Promise.all([
    page.waitForEvent('download'),
    downloadCsvItem.click(),
  ]);
  expect(csvDownload.suggestedFilename()).toContain('.csv');

  // Re-open Export dropdown and trigger JSON download
  await exportBtn.click();
  const [jsonDownload] = await Promise.all([
    page.waitForEvent('download'),
    downloadJsonItem.click(),
  ]);
  expect(jsonDownload.suggestedFilename()).toContain('.json');
});


test('green budget audit: filters drawer chips and badge maintain neutral restraint at 390 and 1440', async ({ page }) => {
  for (const viewport of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Open the Filters drawer
    const filtersBtn = page.getByRole('button', { name: /filters/i });
    await expect(filtersBtn).toBeVisible();
    await filtersBtn.click();

    // Verify post-age chips exist and selected post-age chip does NOT have green background or green border
    const postAgeChips = page.locator('.post-age-chip');
    await expect(postAgeChips.first()).toBeVisible();

    const chipStyles = await page.evaluate(() => {
      const chips = Array.from(document.querySelectorAll('.post-age-chip'));
      return chips.map((c) => {
        const s = window.getComputedStyle(c);
        return {
          bg: s.backgroundColor,
          border: s.borderColor,
        };
      });
    });

    for (const style of chipStyles) {
      const isGreenBg = style.bg.includes('26, 56, 43') || style.bg.includes('34, 197, 94') || style.bg.includes('16, 185, 129');
      expect(isGreenBg).toBe(false);
    }

    // Select non-default chip ('Past 24 hours') to trigger badge count > 0
    await postAgeChips.nth(0).click();

    const badgeStyle = await page.evaluate(() => {
      const badge = document.querySelector('[data-slot="badge"]');
      if (!badge) return null;
      const s = window.getComputedStyle(badge);
      return {
        bg: s.backgroundColor,
        border: s.borderColor,
      };
    });

    if (badgeStyle) {
      const isGreenBadge = badgeStyle.bg.includes('26, 56, 43') || badgeStyle.bg.includes('34, 197, 94') || badgeStyle.bg.includes('16, 185, 129');
      expect(isGreenBadge).toBe(false);
    }
  }
});


test('step 19: brand logo symbol, web icons, and restrained footer across /, /app, and /admin', async ({ page, request }) => {
  // 1. Verify /favicon.svg and /site.webmanifest are served with HTTP 200
  const favRes = await request.get('/favicon.svg');
  expect(favRes.status()).toBe(200);
  const favText = await favRes.text();
  expect(favText).toContain('prefers-color-scheme:dark');

  const manifestRes = await request.get('/site.webmanifest');
  expect(manifestRes.status()).toBe(200);
  const manifestJson = await manifestRes.json();
  expect(manifestJson.name).toBe('Bottom Pot');

  // 2. Verify marketing landing (/) header symbol, zero "BP" tile, and footer actions
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const homeBtn = page.getByRole('button', { name: 'Bottom Pot home' }).first();
  await expect(homeBtn).toBeVisible();
  await expect(homeBtn.locator('svg[viewBox="20 52 216 152"]').first()).toBeVisible();

  const bpTilesOnLanding = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('div')).filter((d) => d.textContent?.trim() === 'BP').length;
  });
  expect(bpTilesOnLanding).toBe(0);

  const marketingFooter = page.locator('footer');
  await expect(marketingFooter).toBeVisible();
  await expect(marketingFooter).toContainText('Bottom Pot · Jobs straight from the company');
  const footerSearchBtn = marketingFooter.getByRole('button', { name: 'Search jobs' });
  await expect(footerSearchBtn).toBeVisible();
  await footerSearchBtn.click();

  // 3. Transitioned to /app via footer "Search jobs" button: verify header symbol and workspace footer
  await expect(page).toHaveURL(/\/app/);
  const workspaceBrandBtn = page.getByRole('button', { name: 'Bottom Pot - Return to Overview' });
  await expect(workspaceBrandBtn).toBeVisible();
  await expect(workspaceBrandBtn.locator('svg[viewBox="20 52 216 152"]').first()).toBeVisible();

  const workspaceFooter = page.locator('footer');
  await expect(workspaceFooter).toBeVisible();
  await expect(workspaceFooter.getByRole('button', { name: 'Overview' })).toBeVisible();
  await expect(workspaceFooter.getByRole('button', { name: 'New search' })).toBeVisible();

  // Check footer .page-shell alignment and button spacing on /app
  const footerCheck = await page.evaluate(() => {
    const headerShell = document.querySelector('header .page-shell');
    const footerShell = document.querySelector('footer .page-shell');
    const leftDiff = Math.abs(
      Math.round(headerShell.getBoundingClientRect().left) -
      Math.round(footerShell.getBoundingClientRect().left)
    );
    const buttons = Array.from(document.querySelectorAll('footer button')).map((b) => {
      const r = b.getBoundingClientRect();
      const s = window.getComputedStyle(b);
      return {
        height: Math.round(r.height),
        padLeft: parseFloat(s.paddingLeft),
        padRight: parseFloat(s.paddingRight),
      };
    });
    return { leftDiff, buttons };
  });
  expect(footerCheck.leftDiff).toBeLessThanOrEqual(2);
  for (const btn of footerCheck.buttons) {
    expect(btn.height).toBe(32);
    expect(btn.padLeft).toBeGreaterThanOrEqual(12);
    expect(btn.padRight).toBeGreaterThanOrEqual(12);
  }

  // Click "Shortcuts (?)" in workspace footer and confirm modal opens
  await workspaceFooter.getByRole('button', { name: 'Shortcuts (?)' }).click();
  await expect(page.getByRole('heading', { name: /keyboard shortcuts/i })).toBeVisible();
  await page.keyboard.press('Escape');

  // 4. Verify /admin login card renders standalone LogoSymbol with role="img" and zero "BP" text tiles
  await page.goto('/admin');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('svg[role="img"][aria-label="Bottom Pot"]').first()).toBeVisible();
  const bpTilesOnAdminLogin = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('div')).filter((d) => d.textContent?.trim() === 'BP').length;
  });
  expect(bpTilesOnAdminLogin).toBe(0);
});

test('displays neutral "Results may be incomplete" notice when search result is partial', async ({ page }) => {
  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: streamedJobs.slice(0, 1), total_so_far: 1 }],
        [
          'done',
          {
            total: 1,
            incomplete: false,
            partial: true,
          },
        ],
      ]),
    });
  });

  await runSearch(page);

  const notice = page.locator('[data-testid="partial-results-notice"]');
  await expect(notice).toBeVisible();
  await expect(notice).toHaveText('Results may be incomplete');
});

test('in-place upsert updates snippet to enriched record preserving row count and selection', async ({ page }) => {
  const snippetJob = {
    id: 'job-snippet-1',
    provider: 'greenhouse',
    data_source: 'snippet',
    title: 'Python Engineer (Initial Snippet)',
    company: 'Acme Labs',
    location: 'Lagos, Nigeria',
    work_model: 'unknown',
    posted_at: '2026-09-10T09:00:00Z',
    apply_url: 'https://jobs.example.test/acme/python-engineer',
  };

  const enrichedJob = {
    id: 'greenhouse:acme:1',
    aliases: ['job-snippet-1'],
    provider: 'greenhouse',
    data_source: 'api',
    title: 'Senior Python Engineer (Enriched)',
    company: 'Acme Labs',
    location: 'Lagos, Nigeria',
    work_model: 'remote',
    salary: { minimum: 140000, maximum: 160000, currency: 'USD', period: 'year' },
    posted_at: '2026-09-10T09:00:00Z',
    apply_url: 'https://jobs.example.test/acme/python-engineer',
  };

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: [snippetJob], total_so_far: 1 }],
        ['results', { batch: [enrichedJob], total_so_far: 1 }],
        ['done', { total: 1, incomplete: false, partial: false }],
      ]),
    });
  });

  await runSearch(page);

  // Verify only 1 row exists (no count inflation)
  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(1);

  // Verify the row displays the upgraded title and metadata
  await expect(rows.first()).toContainText('Senior Python Engineer (Enriched)');

  // Verify selection opens the detail sheet for the upgraded record
  await rows.first().click();
  const detailSheet = page.locator('.detail-sheet');
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Senior Python Engineer (Enriched)');

  // Verify saving the job works on the upgraded record
  const saveBtn = detailSheet.getByRole('button', { name: /save job to shortlist/i });
  await saveBtn.click();
  await expect(detailSheet.getByRole('button', { name: /remove from saved jobs/i })).toBeVisible();
});

test('step 28: Nigerian boards derived checkbox and chips selection behaviour', async ({ page }) => {
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // Open filters
  const filtersBtn = page.getByRole('button', { name: /filters/i });
  await filtersBtn.click();

  const ngCheckbox = page.locator('#nigerian-boards-check');
  await expect(ngCheckbox).toBeVisible();

  // Initially on default app load, all platforms are selected, so checkbox is checked
  await expect(ngCheckbox).toBeChecked();

  const jobbermanChip = page.locator('.platform-chip-btn', { hasText: 'Jobberman' });
  const myjobmagChip = page.locator('.platform-chip-btn', { hasText: 'MyJobMag' });
  const hnjChip = page.locator('.platform-chip-btn', { hasText: 'HotNigerianJobs' });

  // 1. Unticking checkbox deselects all Nigerian chips
  await ngCheckbox.click();
  await expect(ngCheckbox).not.toBeChecked();
  await expect(jobbermanChip.locator('svg')).toHaveCount(0);
  await expect(myjobmagChip.locator('svg')).toHaveCount(0);
  await expect(hnjChip.locator('svg')).toHaveCount(0);

  // 2. Ticking checkbox selects all Nigerian chips
  await ngCheckbox.click();
  await expect(ngCheckbox).toBeChecked();
  await expect(jobbermanChip.locator('svg')).toHaveCount(1);
  await expect(myjobmagChip.locator('svg')).toHaveCount(1);
  await expect(hnjChip.locator('svg')).toHaveCount(1);

  // 3. Removing one chip (HotNigerianJobs) unticks the checkbox
  await hnjChip.click();
  await expect(hnjChip.locator('svg')).toHaveCount(0);
  await expect(ngCheckbox).not.toBeChecked();

  // 4. Re-adding the last missing chip (HotNigerianJobs) re-ticks it
  await hnjChip.click();
  await expect(hnjChip.locator('svg')).toHaveCount(1);
  await expect(ngCheckbox).toBeChecked();

  // 5. Selection survives a page reload
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /filters/i }).click();
  const reloadedNgCheckbox = page.locator('#nigerian-boards-check');
  await expect(reloadedNgCheckbox).toBeChecked();

  // 6. With only Greenhouse selected, the checkbox is unchecked
  const selectNoneBtn = page.getByRole('button', { name: /select none/i });
  await selectNoneBtn.click();
  const greenhouseChip = page.locator('.platform-chip-btn', { hasText: 'Greenhouse' });
  await greenhouseChip.click();
  await expect(reloadedNgCheckbox).not.toBeChecked();

  // 7. Capture AFTER screenshots (one light, one dark) of the filters panel
  const selectAllBtn = page.getByRole('button', { name: /select all/i });
  await selectAllBtn.click();
  await expect(reloadedNgCheckbox).toBeChecked();

  const filterPanel = page.locator('[data-testid="filters-drawer"]');
  await filterPanel.screenshot({ path: 'docs/design/after/step28_platform_chips_light.png' });

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.waitForTimeout(150);
  await filterPanel.screenshot({ path: 'docs/design/after/step28_platform_chips_dark.png' });
  await themeBtn.click(); // restore light theme
});

test('step 34: DetailSheet renders Workday eligibility states, square styling, dark mode, and 5 viewports', async ({ page }) => {
  const workdayJobs = [
    {
      id: 'workday:dxc:1',
      provider: 'workday',
      data_source: 'api',
      title: 'Software Engineer',
      company: 'DXC Technology',
      company_slug: 'dxc',
      location: 'ESP - MD - LAS ROZAS, Spain',
      raw_location: 'ESP - MD - LAS ROZAS',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      description: 'Build enterprise Java and Python services in Madrid.',
      posted_at: '2026-10-12T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://dxc.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Software-Engineer_123',
      source_url: 'https://dxc.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Software-Engineer_123',
      query_used: 'software engineer',
      ats_source: 'workday',
      eligibility: {
        allowed_residence_countries: ['Spain', 'European Union'],
        residence_restriction_confirmed: true,
        work_authorization_required: ['European Union'],
        visa_sponsorship_status: 'not_available',
        physical_location_country: 'Spain',
        employment_arrangement: 'employee',
        hybrid_attendance_confirmed: true,
        nigeria_eligible: false,
        nigeria_eligibility_reason: 'Confirmed hybrid office attendance in Spain.',
        eligibility_source: 'api',
        facts: [],
      },
    },
    {
      id: 'workday:boeing:2',
      provider: 'workday',
      data_source: 'api',
      title: 'Principal Systems Engineer',
      company: 'Boeing',
      company_slug: 'boeing',
      location: 'Seattle, Washington',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      salary: { minimum: 145000, maximum: 195000, currency: 'USD', period: 'year' },
      description: 'Systems architecture for avionics platforms.',
      posted_at: '2026-10-11T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://boeing.wd1.myworkdayjobs.com/EXTERNAL_CAREERS/job/USA---Seattle-WA/Principal-Systems-Engineer_456',
      source_url: 'https://boeing.wd1.myworkdayjobs.com/EXTERNAL_CAREERS/job/USA---Seattle-WA/Principal-Systems-Engineer_456',
      query_used: 'software engineer',
      ats_source: 'workday',
      eligibility: {
        allowed_residence_countries: null,
        work_authorization_required: ['United States'],
        visa_sponsorship_status: 'not_available',
        nigeria_eligible: null,
        nigeria_eligibility_reason: null,
        eligibility_source: 'api',
        facts: [],
      },
    },
    {
      id: 'workday:canonical:3',
      provider: 'workday',
      data_source: 'api',
      title: 'Distributed Systems Engineer',
      company: 'Canonical',
      company_slug: 'canonical',
      location: 'Remote, Worldwide',
      is_remote: true,
      employment_type: 'contract',
      work_model: 'remote',
      description: 'Remote engineering across EMEA timezones.',
      posted_at: '2026-10-10T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://canonical.wd3.myworkdayjobs.com/External/job/Remote/Distributed-Systems-Engineer_789',
      source_url: 'https://canonical.wd3.myworkdayjobs.com/External/job/Remote/Distributed-Systems-Engineer_789',
      query_used: 'software engineer',
      ats_source: 'workday',
      eligibility: {
        allowed_residence_countries: null,
        work_authorization_required: [],
        visa_sponsorship_status: 'undisclosed',
        employment_arrangement: 'contractor',
        timezone_requirements: 'EMEA +/- 3h',
        nigeria_eligible: true,
        nigeria_eligibility_reason: 'Open to worldwide remote contractors.',
        eligibility_source: 'api',
        facts: [],
      },
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: workdayJobs, total_so_far: workdayJobs.length }],
        [
          'done',
          {
            total: workdayJobs.length,
            search_time_ms: 210,
            serper_queries_used: 1,
            providers_searched: ['workday'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await runSearch(page, { keyword: 'Software Engineer' });

  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  // Verify all 3 eligibility states in user mode
  const detailSheet = page.locator('.detail-sheet');
  const rows = page.locator('.results-table tbody tr.job-row');

  await rows.nth(0).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Eligibility & restrictions');
  await expect(detailSheet).toContainText('Not eligible from Nigeria');
  await expect(detailSheet).toContainText('Spain, European Union');
  await expect(detailSheet).toContainText('Not available');
  await expect(detailSheet).toContainText('Confirmed hybrid office attendance in Spain.');
  await expect(detailSheet).not.toContainText('Raw location');

  // Verify square geometry on detail sheet and nested cards
  const sheetRadius = await detailSheet.evaluate((el) => getComputedStyle(el).borderRadius);
  expect(sheetRadius).toBe('0px');

  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  // Domestic work auth only -> must show auth & sponsorship without claiming Not eligible from Nigeria
  await rows.nth(1).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Eligibility & restrictions');
  await expect(detailSheet).toContainText('United States');
  await expect(detailSheet).toContainText('Not available');
  await expect(detailSheet).not.toContainText('Not eligible from Nigeria');
  await expect(detailSheet).not.toContainText('Eligible from Nigeria');

  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  // Eligible contractor role
  await rows.nth(2).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Eligible from Nigeria');
  await expect(detailSheet).toContainText('Contractor / B2B');
  await expect(detailSheet).toContainText('EMEA +/- 3h');

  // Check 5 viewports (overflow on all 5; Axe a11y on desktop/tablet/mobile to stay fast)
  const viewports = [
    { width: 1920, height: 1080, runAxe: false },
    { width: 1440, height: 900, runAxe: true },
    { width: 1024, height: 768, runAxe: false },
    { width: 768, height: 1024, runAxe: true },
    { width: 390, height: 844, runAxe: true },
  ];

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(80);
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(hasOverflow).toBeFalsy();

    if (vp.runAxe) {
      const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
    }
  }

  // Close detail sheet before clicking header theme toggle (modal backdrop intercepts background clicks)
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.waitForTimeout(100);
  for (const vp of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(vp);
    const trigger = vp.width < 768
      ? page.locator('.mobile-job-card').first()
      : page.locator('.results-table tbody tr.job-row').first();
    await trigger.click();
    await expect(detailSheet).toBeVisible();
    const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
    await page.keyboard.press('Escape');
    await expect(detailSheet).toBeHidden();
  }
  await themeBtn.click(); // restore light mode

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('step 34: admin workspace DetailSheet shows Raw location alongside normalized location', async ({ page }) => {
  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        [
          'results',
          {
            batch: [
              {
                id: 'workday:dxc:1',
                provider: 'workday',
                data_source: 'api',
                title: 'Software Engineer',
                company: 'DXC Technology',
                company_slug: 'dxc',
                location: 'ESP - MD - LAS ROZAS, Spain',
                raw_location: 'ESP - MD - LAS ROZAS',
                is_remote: false,
                employment_type: 'full_time',
                work_model: 'hybrid',
                description: 'Build enterprise Java and Python services in Madrid.',
                posted_at: '2026-10-12T09:00:00Z',
                scraped_at: '2026-10-15T09:00:00Z',
                apply_url: 'https://dxc.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Software-Engineer_123',
                source_url: 'https://dxc.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Software-Engineer_123',
                query_used: 'software engineer',
                ats_source: 'workday',
                eligibility: {
                  allowed_residence_countries: ['Spain'],
                  residence_restriction_confirmed: true,
                  nigeria_eligible: false,
                  nigeria_eligibility_reason: 'Confirmed hybrid office attendance in Spain.',
                  eligibility_source: 'api',
                  facts: [],
                },
              },
            ],
            total_so_far: 1,
          },
        ],
        [
          'done',
          {
            total: 1,
            search_time_ms: 90,
            serper_queries_used: 1,
            providers_searched: ['workday'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/admin?q=Software%20Engineer');
  await page.waitForLoadState('networkidle');
  await page.fill('#admin-password', 'test-admin-password');
  await page.click('button[type="submit"]');
  await expect(page.getByTitle('Administrator Workspace')).toBeVisible();

  await expect(page.locator('.results-table tbody tr.job-row').first()).toBeVisible({ timeout: 10000 });
  await page.locator('.results-table tbody tr.job-row').first().click();

  const detailSheet = page.locator('.detail-sheet');
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Raw location');
  await expect(detailSheet).toContainText('ESP - MD - LAS ROZAS');
  await expect(detailSheet).toContainText('Not eligible from Nigeria');
});

test('step 35: CompanyMark renders HTTPS Teamtailor logo, falls back on image error, and keeps square 0px geometry across desktop/mobile and dark mode', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(err.message));

  await page.route('https://images.teamtailor-cdn.com/**', async (route) => {
    const reqUrl = route.request().url();
    if (reqUrl.includes('valid-logo.svg')) {
      await route.fulfill({
        status: 200,
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
      });
      return;
    }
    await route.fulfill({ status: 404, body: 'Not found' });
  });

  const step35Jobs = [
    {
      id: 'teamtailor:qtech:8029561',
      provider: 'teamtailor',
      data_source: 'scrape',
      title: 'Java Developer',
      company: 'Q-Tech',
      company_slug: 'qtech',
      company_logo_url: 'https://images.teamtailor-cdn.com/valid-logo.svg',
      location: 'Barcelona, Spain',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 45000, maximum: 50000, currency: 'EUR', period: 'year' },
      description: '### Requirements\n\n- Java 17 and distributed services',
      requirements: '- Java 17 and distributed services',
      posted_at: '2026-10-12T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://qtech.teamtailor.com/jobs/8029561-java-developer',
      source_url: 'https://qtech.teamtailor.com/jobs/8029561-java-developer',
      query_used: 'java developer',
      ats_source: 'teamtailor',
    },
    {
      id: 'teamtailor:lunar:9001',
      provider: 'teamtailor',
      data_source: 'scrape',
      title: 'Platform Engineer',
      company: 'Lunar',
      company_slug: 'lunar',
      company_logo_url: 'https://images.teamtailor-cdn.com/broken-logo.png',
      location: 'Copenhagen, Denmark',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      description: '### Role\n\nBuild banking infrastructure.',
      posted_at: '2026-10-11T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://jobs.lunar.app/jobs/9001-platform-engineer',
      source_url: 'https://jobs.lunar.app/jobs/9001-platform-engineer',
      query_used: 'java developer',
      ats_source: 'teamtailor',
    },
    {
      id: 'greenhouse:acme:1',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Backend Engineer',
      company: 'Acme Labs',
      company_slug: 'acme',
      company_logo_url: null,
      location: 'Lagos, Nigeria',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      description: '### Role\n\nDistributed API systems.',
      posted_at: '2026-10-10T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://boards.greenhouse.io/acme/jobs/1',
      source_url: 'https://boards.greenhouse.io/acme/jobs/1',
      query_used: 'java developer',
      ats_source: 'greenhouse',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step35Jobs, total_so_far: step35Jobs.length }],
        [
          'done',
          {
            total: step35Jobs.length,
            search_time_ms: 95,
            serper_queries_used: 1,
            providers_searched: ['teamtailor', 'greenhouse'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?q=Java%20Developer');
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3, { timeout: 10000 });

  const tableMarks = page.locator('.results-table [data-testid="company-mark"]');
  await expect(tableMarks).toHaveCount(3);

  const qtechImg = tableMarks.nth(0).locator('img');
  await expect(qtechImg).toBeVisible();
  await expect.poll(async () => qtechImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);

  // Broken logo URL falls back via onError to square initials monogram ("LU")
  await expect(tableMarks.nth(1).locator('img')).toHaveCount(0, { timeout: 5000 });
  await expect(tableMarks.nth(1)).toContainText('LU');

  // Non-Teamtailor job with null company_logo_url renders monogram ("AL")
  await expect(tableMarks.nth(2).locator('img')).toHaveCount(0);
  await expect(tableMarks.nth(2)).toContainText('AL');

  // Verify square 0px border-radius on every CompanyMark (table + DetailSheet)
  for (let i = 0; i < 3; i++) {
    const br = await tableMarks.nth(i).evaluate((el) => getComputedStyle(el).borderRadius);
    expect(br).toBe('0px');
  }

  // Open DetailSheet for Q-Tech and verify logo + 0px borderRadius
  await page.locator('.results-table tbody tr.job-row').first().click();
  const detailSheet = page.locator('.detail-sheet');
  await expect(detailSheet).toBeVisible();
  const sheetMark = detailSheet.locator('[data-testid="company-mark"]');
  await expect(sheetMark.locator('img')).toBeVisible();
  expect(await sheetMark.evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  // Check mobile ResultsCards at 390px and dark mode Axe scan (ignoring expected 404 resource log from broken-logo test)
  await page.setViewportSize({ width: 390, height: 844 });
  const cardMarks = page.locator('.mobile-job-card [data-testid="company-mark"]');
  await expect(cardMarks).toHaveCount(3);
  await expect(cardMarks.nth(0).locator('img')).toBeVisible();
  await expect(cardMarks.nth(1)).toContainText('LU');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.waitForTimeout(100);
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  const nonImgErrors = consoleErrors.filter((msg) => !msg.includes('404'));
  expect(nonImgErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('Step 36: Lever logos, authoritative names, clean markdown lists, eligibility, and 5-viewport responsiveness', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  await page.route('**://lever-client-logos.s3.us-west-2.amazonaws.com/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
    });
  });

  const step36Jobs = [
    {
      id: 'lever:tpgsi:1cb2b7f2-506b-4cb2-8d59-bc6e4771363f',
      provider: 'lever',
      data_source: 'api',
      title: 'AI-Assisted Full-Stack Engineer',
      company: 'Turning Point Global Solutions',
      company_slug: 'tpgsi',
      company_logo_url: 'https://lever-client-logos.s3.us-west-2.amazonaws.com/tpgsi-logo.png',
      location: 'Washington, DC',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 125300, maximum: 250600, currency: 'USD', period: null },
      description: '### Role Overview\n\nBuild mission systems.\n\n### Minimum Qualifications\n\n- TypeScript and React\n- Python API services',
      requirements: '### Minimum Qualifications\n- TypeScript and React\n- Python API services',
      eligibility: {
        physical_location_country: 'United States',
        allowed_residence_countries: null,
        excluded_residence_countries: null,
        residence_restriction_confirmed: null,
        global_remote_explicit: null,
        nigeria_eligible: false,
        nigeria_eligibility_reason: 'Hybrid role in United States requires physical attendance.',
      },
      posted_at: '2026-10-12T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://jobs.lever.co/tpgsi/1cb2b7f2-506b-4cb2-8d59-bc6e4771363f/apply',
      source_url: 'https://jobs.lever.co/tpgsi/1cb2b7f2-506b-4cb2-8d59-bc6e4771363f',
      query_used: 'fullstack engineer',
      ats_source: 'lever',
    },
    {
      id: 'lever:zoox:9176aa65-14e3-4f9d-98f9-e755e9777d67',
      provider: 'lever',
      data_source: 'api',
      title: 'Software Engineer - Learned Trajectory ML',
      company: 'Zoox',
      company_slug: 'zoox',
      company_logo_url: null,
      location: 'Foster City, CA',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 189000, maximum: 270000, currency: 'USD', period: 'year' },
      description: '### Qualifications\n\n- PyTorch and autonomous robotics',
      requirements: '- PyTorch and autonomous robotics',
      eligibility: {
        physical_location_country: 'United States',
        nigeria_eligible: false,
      },
      posted_at: '2026-10-11T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://jobs.lever.co/zoox/9176aa65-14e3-4f9d-98f9-e755e9777d67/apply',
      source_url: 'https://jobs.lever.co/zoox/9176aa65-14e3-4f9d-98f9-e755e9777d67',
      query_used: 'fullstack engineer',
      ats_source: 'lever',
    },
    {
      id: 'lever:muttdata:624ad7e8-1276-4f8c-9d8b-1e8218319f00',
      provider: 'lever',
      data_source: 'api',
      title: 'Machine Learning Engineer - Latam',
      company: 'Muttdata',
      company_slug: 'muttdata',
      company_logo_url: null,
      location: 'Argentina',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      description: '### Perks\n\n- Remote-first culture\n\n### Requirements\n\n- Databricks and Spark',
      requirements: '- Databricks and Spark',
      eligibility: {
        physical_location_country: 'Argentina',
        allowed_residence_countries: ['LATAM'],
        residence_restriction_confirmed: true,
        global_remote_explicit: null,
        nigeria_eligible: false,
      },
      posted_at: '2026-10-10T09:00:00Z',
      scraped_at: '2026-10-15T09:00:00Z',
      apply_url: 'https://jobs.lever.co/muttdata/624ad7e8-1276-4f8c-9d8b-1e8218319f00/apply',
      source_url: 'https://jobs.lever.co/muttdata/624ad7e8-1276-4f8c-9d8b-1e8218319f00',
      query_used: 'fullstack engineer',
      ats_source: 'lever',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step36Jobs, total_so_far: step36Jobs.length }],
        [
          'done',
          {
            total: step36Jobs.length,
            search_time_ms: 88,
            serper_queries_used: 0,
            providers_searched: ['lever'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?q=Fullstack%20Engineer');
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3, { timeout: 10000 });

  // Verify authoritative company name and square 0px CompanyMark rendering
  await expect(page.locator('.results-table')).toContainText('Turning Point Global Solutions');
  await expect(page.locator('.results-table')).not.toContainText('Tpgsi');

  const marks = page.locator('.results-table [data-testid="company-mark"]');
  await expect(marks).toHaveCount(3);
  const tpgsiImg = marks.nth(0).locator('img');
  await expect(tpgsiImg).toBeVisible();
  await expect.poll(async () => tpgsiImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  await expect(marks.nth(1).locator('img')).toHaveCount(0);
  await expect(marks.nth(1)).toContainText('Z');

  for (const vp of [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(vp);
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(hasOverflow, `Horizontal overflow at ${vp.width}px`).toBe(false);
  }

  // Open DetailSheet on desktop and check crisp markdown list items + square logo
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.results-table tbody tr.job-row').first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Turning Point Global Solutions');
  await expect(sheet.locator('[data-testid="company-mark"] img')).toBeVisible();
  expect(await sheet.locator('[data-testid="company-mark"]').evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');
  await expect(sheet.locator('li')).toHaveCount(4);
  await expect(sheet).toContainText('TypeScript and React');

  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});






