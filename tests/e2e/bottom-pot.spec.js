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

  // Verify download CSV and JSON buttons in overflow menu exist and are enabled
  await page.getByRole('button', { name: /more actions/i }).click();
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



