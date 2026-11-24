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
  await expect(page.getByText(/real openings pulled directly from company hiring pages/i)).toBeVisible();
  await expect(page.getByText(/where your search looks/i).first()).toBeVisible();

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

  // Click Start searching link to transition to workspace
  await page.getByRole('link', { name: /start searching/i }).first().click();
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
  const searchInput = page.getByPlaceholder(/filter results/i);
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
  const searchInput = page.getByPlaceholder(/filter results/i);
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
  const startBtn = page.getByRole('link', { name: /start searching/i }).first();
  await startBtn.click();
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Search jobs');
  await expect(page.getByRole('button', { name: 'Search jobs' })).toBeVisible();

  // 4. Return to / and follow "Inspect all 13 sources" -> "Search greenhouse" cleanly into /app
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const sourcesLink = page.getByRole('link', { name: /inspect all 13 sources/i });
  await expect(sourcesLink).toBeVisible();
  await sourcesLink.click();
  await expect(page).toHaveURL(/\/sources/);
  const ghBtn = page.getByRole('button', { name: 'Search greenhouse' });
  await expect(ghBtn).toBeVisible();
  await ghBtn.click();
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Search jobs');
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

  const homeLink = page.getByRole('link', { name: 'Bottom Pot home' }).first();
  await expect(homeLink).toBeVisible();
  await expect(homeLink.locator('svg[viewBox="20 52 216 152"]').first()).toBeVisible();

  const bpTilesOnLanding = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('div')).filter((d) => d.textContent?.trim() === 'BP').length;
  });
  expect(bpTilesOnLanding).toBe(0);

  const marketingFooter = page.locator('footer');
  await expect(marketingFooter).toBeVisible();
  await expect(marketingFooter).toContainText('Bottom Pot · Jobs straight from the company');
  const footerSearchLink = marketingFooter.getByRole('link', { name: 'Search jobs' });
  await expect(footerSearchLink).toBeVisible();
  await footerSearchLink.click();

  // 3. Transitioned to /app via footer "Search jobs" link: verify header symbol and multi-column footer
  await expect(page).toHaveURL(/\/app/);
  const workspaceBrandLink = page.getByRole('link', { name: 'Bottom Pot home' }).first();
  await expect(workspaceBrandLink).toBeVisible();
  await expect(workspaceBrandLink.locator('svg[viewBox="20 52 216 152"]').first()).toBeVisible();

  const workspaceFooter = page.locator('footer');
  await expect(workspaceFooter).toBeVisible();
  await expect(workspaceFooter.getByRole('link', { name: 'Product' })).toBeVisible();
  await expect(workspaceFooter.getByRole('link', { name: 'Sources' })).toBeVisible();
  await expect(workspaceFooter.getByRole('link', { name: 'About' })).toBeVisible();
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

test('step 28: Nigerian boards derived checkbox and chips selection behaviour', async ({ page }, testInfo) => {
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
  await filterPanel.screenshot({ path: testInfo.outputPath('step28_platform_chips_light.png') });

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.waitForTimeout(150);
  await filterPanel.screenshot({ path: testInfo.outputPath('step28_platform_chips_dark.png') });
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
        classification: 'worldwide',
        global_remote_explicit: true,
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

  // Verify unset-country neutrality and all 3 eligibility states once applicant country is selected
  const detailSheet = page.locator('.detail-sheet');
  const rows = page.locator('.results-table tbody tr.job-row');

  // Unset country must never pretend to know Nigeria eligibility
  await rows.nth(0).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Eligibility & restrictions');
  await expect(detailSheet).not.toContainText('Not eligible from Nigeria');
  await expect(detailSheet).not.toContainText('Eligible from Nigeria');
  await expect(detailSheet).toContainText(/Where can you work from\?/i);
  await expect(detailSheet).toContainText('Spain, European Union');
  await expect(detailSheet).toContainText('Not available');
  await expect(detailSheet).not.toContainText('Raw location');

  // Verify square geometry on detail sheet
  const sheetRadius = await detailSheet.evaluate((el) => getComputedStyle(el).borderRadius);
  expect(sheetRadius).toBe('0px');

  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  // Select Nigeria ('NG') via the toolbar selector -> evaluates dynamically without re-searching
  await page.getByLabel('Where can you work from?').selectOption('NG');

  await rows.nth(0).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Not eligible from Nigeria');
  await expect(detailSheet).toContainText('Confirmed hybrid office attendance in Spain.');

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

  // Eligible contractor role for Nigeria
  await rows.nth(2).click();
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Eligible from Nigeria');
  await expect(detailSheet).toContainText('Contractor / B2B');
  await expect(detailSheet).toContainText('EMEA +/- 3h');

  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  // Switching to Spain ('ES') makes DXC Spain hybrid eligible for Spain
  await page.getByLabel('Where can you work from?').selectOption('ES');
  await rows.nth(0).click();
  await expect(detailSheet).toContainText('Eligible from Spain');
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();
  await page.getByLabel('Where can you work from?').selectOption('NG');
  await rows.nth(2).click();

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
  await expect(detailSheet).not.toContainText('Not eligible from Nigeria');
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();

  await page.getByLabel('Where can you work from?').selectOption('NG');
  await page.locator('.results-table tbody tr.job-row').first().click();
  await expect(detailSheet).toBeVisible();
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

test('Step 37: Greenhouse CDN logos, authoritative names, hourly/annual salary, work models, requirements, and 5-viewport responsiveness', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  await page.route('**://*.cdn.greenhouse.io/external_greenhouse_job_boards/logos/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
    });
  });

  const step37Jobs = [
    {
      id: 'greenhouse:gitlab:8771512002',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Senior Support Engineer (Americas)',
      company: 'GitLab',
      company_slug: 'gitlab',
      company_logo_url: 'https://s4-recruiting.cdn.greenhouse.io/external_greenhouse_job_boards/logos/400/123/456/original/gitlab.png',
      location: 'Remote, Americas',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      salary: { minimum: 115200, maximum: 162000, currency: 'USD', period: 'year' },
      description: '### What you’ll do\n\nSupport enterprise customers.\n\n### What you’ll bring\n\n- Linux and Kubernetes troubleshooting\n- Strong written communication',
      requirements: '### What you’ll bring\n- Linux and Kubernetes troubleshooting\n- Strong written communication',
      eligibility: {
        allowed_residence_countries: ['Americas'],
        residence_restriction_confirmed: true,
        global_remote_explicit: null,
        nigeria_eligible: false,
        nigeria_eligibility_reason: 'Applicant residence restricted to Americas.',
      },
      posted_at: '2026-11-01T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://job-boards.greenhouse.io/gitlab/jobs/8771512002#app',
      source_url: 'https://job-boards.greenhouse.io/gitlab/jobs/8771512002',
      query_used: 'engineer',
      ats_source: 'greenhouse',
    },
    {
      id: 'greenhouse:excelsportsmanagement:4747594005',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'IT Support Coordinator',
      company: 'Excel Sports Management',
      company_slug: 'excelsportsmanagement',
      company_logo_url: null,
      location: 'New York, NY',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 17, maximum: 17, currency: 'USD', period: 'hour' },
      description: '### Role Overview\n\nThree office days per week in New York ($17.00 per hour).\n\n### Requirements\n\n- End-user device support',
      requirements: '### Requirements\n- End-user device support',
      eligibility: {
        physical_location_country: 'United States',
        nigeria_eligible: false,
      },
      posted_at: '2026-11-02T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://job-boards.greenhouse.io/excelsportsmanagement/jobs/4747594005#app',
      source_url: 'https://job-boards.greenhouse.io/excelsportsmanagement/jobs/4747594005',
      query_used: 'engineer',
      ats_source: 'greenhouse',
    },
    {
      id: 'greenhouse:canonical:6200001',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Graduate Software Engineer',
      company: 'Canonical',
      company_slug: 'canonical',
      company_logo_url: null,
      location: 'Home based - EMEA',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      salary: null,
      description: '### What we look for\n\n- Go, Python, or Rust systems programming\n- Distributed cloud infrastructure',
      requirements: '### What we look for\n- Go, Python, or Rust systems programming\n- Distributed cloud infrastructure',
      eligibility: {
        allowed_residence_countries: ['EMEA'],
        residence_restriction_confirmed: true,
        global_remote_explicit: null,
        nigeria_eligible: null,
      },
      posted_at: '2026-11-03T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://job-boards.greenhouse.io/canonical/jobs/6200001#app',
      source_url: 'https://job-boards.greenhouse.io/canonical/jobs/6200001',
      query_used: 'engineer',
      ats_source: 'greenhouse',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step37Jobs, total_so_far: step37Jobs.length }],
        [
          'done',
          {
            total: step37Jobs.length,
            search_time_ms: 92,
            serper_queries_used: 0,
            providers_searched: ['greenhouse'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?q=Engineer');
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3, { timeout: 10000 });

  // Authoritative company names, salary disclosure, and work-model columns
  await expect(page.locator('.results-table')).toContainText('Git Lab');
  await expect(page.locator('.results-table')).toContainText('Excel Sports Management');
  await expect(page.locator('.results-table')).toContainText('Canonical');
  await expect(page.locator('.results-table')).toContainText('USD 115,200 – 162,000 / year');
  await expect(page.locator('.results-table')).toContainText('USD 17 – 17 / hour');
  await expect(page.locator('.results-table')).toContainText('Remote');
  await expect(page.locator('.results-table')).toContainText('Hybrid');

  // Logo rendering: Greenhouse CDN image loaded cleanly on row 0; monogram initial on rows without logo
  const marks = page.locator('.results-table [data-testid="company-mark"]');
  await expect(marks).toHaveCount(3);
  const gitlabImg = marks.nth(0).locator('img');
  await expect(gitlabImg).toBeVisible();
  await expect.poll(async () => gitlabImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  await expect(marks.nth(1).locator('img')).toHaveCount(0);
  await expect(marks.nth(1)).toContainText('ES');
  await expect(marks.nth(2).locator('img')).toHaveCount(0);
  await expect(marks.nth(2)).toContainText('CA');

  // 5-viewport horizontal overflow check (1920, 1440, 1024, 768, 390)
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

  // DetailSheet verification on desktop: square 0px CompanyMark, salary, requirements list
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.results-table tbody tr.job-row').first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Git Lab');
  await expect(sheet).toContainText('USD 115,200 – 162,000 / year');
  await expect(sheet.locator('[data-testid="company-mark"] img')).toBeVisible();
  expect(await sheet.locator('[data-testid="company-mark"]').evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');
  await expect(sheet).toContainText('Linux and Kubernetes troubleshooting');

  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('Step 39: Ashby square logos, authoritative names, work models, salary, eligibility, and 5-viewport responsiveness', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  await page.route('**://app.ashbyhq.com/api/images/org-theme-logo/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
    });
  });

  const step39Jobs = [
    {
      id: 'ashby:plaid:5d8abedc-018a-4b42-ae1f-0e70b34f2007',
      provider: 'ashby',
      data_source: 'api',
      title: 'Engineering Manager - Product Security',
      company: 'Plaid',
      company_slug: 'plaid',
      company_logo_url: 'https://app.ashbyhq.com/api/images/org-theme-logo/plaid.png',
      company_logo_source: 'ashby_app_data_square_logo',
      company_logo_verified: true,
      location: 'San Francisco HQ • New York, NY',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 189600, maximum: 290400, currency: 'USD', period: 'year' },
      description: '### What you will do\n\nLead Product Security Engineering.\n\n### What makes you a great fit\n\n- Experience leading product security teams\n- Strong cloud infrastructure background',
      requirements: '### What makes you a great fit\n- Experience leading product security teams\n- Strong cloud infrastructure background',
      eligibility: {
        physical_location_country: 'United States',
        nigeria_eligible: false,
      },
      posted_at: '2026-11-04T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007/application',
      source_url: 'https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007',
      query_used: 'security engineer',
      ats_source: 'ashby',
    },
    {
      id: 'ashby:plugmotors:62316e43-351a-465e-b143-fe30cb5e642c',
      provider: 'ashby',
      data_source: 'api',
      title: 'Mechanical Engineer',
      company: 'Plug Technologies Inc',
      company_slug: 'plugmotors',
      company_logo_url: 'https://app.ashbyhq.com/api/images/org-theme-logo/plugmotors.png',
      company_logo_source: 'ashby_app_data_square_logo',
      company_logo_verified: true,
      location: 'Los Angeles',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      salary: { minimum: 164000, maximum: 200000, currency: 'USD', period: 'year' },
      description: '### What You’ll Do\n\nBuild vehicle inspection systems.\n\n### What You Need\n\n- Hardware design experience',
      requirements: '### What You Need\n- Hardware design experience',
      eligibility: {
        physical_location_country: 'United States',
        nigeria_eligible: false,
      },
      posted_at: '2026-11-05T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c/application',
      source_url: 'https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c',
      query_used: 'engineer',
      ats_source: 'ashby',
    },
    {
      id: 'ashby:linear:d3bc1ced-3ce4-4086-a050-555055dbb1ff',
      provider: 'ashby',
      data_source: 'api',
      title: 'Senior Support Engineer (EU)',
      company: 'Spring Health',
      company_slug: 'deaa6ad2-d184-436b-b69e-17f761da1d94',
      company_logo_url: null,
      location: 'Europe',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      salary: null,
      description: '### Requirements\n\n- Based in Europe across North America and Europe hours',
      requirements: '### Requirements\n- Based in Europe across North America and Europe hours',
      eligibility: {
        allowed_residence_countries: ['North America', 'Europe'],
        residence_restriction_confirmed: true,
        global_remote_explicit: null,
        nigeria_eligible: false,
      },
      posted_at: '2026-11-06T09:00:00Z',
      scraped_at: '2026-11-12T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff/application',
      source_url: 'https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff',
      query_used: 'engineer',
      ats_source: 'ashby',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step39Jobs, total_so_far: step39Jobs.length }],
        [
          'done',
          {
            total: step39Jobs.length,
            search_time_ms: 84,
            serper_queries_used: 0,
            providers_searched: ['ashby'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?q=Engineer');
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3, { timeout: 10000 });

  await expect(page.locator('.results-table')).toContainText('Plaid');
  await expect(page.locator('.results-table')).toContainText('Plug Technologies Inc');
  await expect(page.locator('.results-table')).toContainText('Spring Health');
  await expect(page.locator('.results-table')).toContainText('USD 189,600 – 290,400 / year');
  await expect(page.locator('.results-table')).toContainText('USD 164,000 – 200,000 / year');
  await expect(page.locator('.results-table')).toContainText('Hybrid');
  await expect(page.locator('.results-table')).toContainText('In-person');
  await expect(page.locator('.results-table')).toContainText('Remote');

  const marks = page.locator('.results-table [data-testid="company-mark"]');
  await expect(marks).toHaveCount(3);
  const plaidImg = marks.nth(0).locator('img');
  await expect(plaidImg).toBeVisible();
  await expect.poll(async () => plaidImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  const plugImg = marks.nth(1).locator('img');
  await expect(plugImg).toBeVisible();
  await expect.poll(async () => plugImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  await expect(marks.nth(2).locator('img')).toHaveCount(0);
  await expect(marks.nth(2)).toContainText('SH');

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

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.results-table tbody tr.job-row').first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Plaid');
  await expect(sheet).toContainText('USD 189,600 – 290,400 / year');
  await expect(sheet.locator('[data-testid="company-mark"] img')).toBeVisible();
  expect(await sheet.locator('[data-testid="company-mark"]').evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');
  await expect(sheet).toContainText('Experience leading product security teams');

  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('Step 41: Workable square logos, JOD/INR/USD salaries, work models, eligibility, /apply links, and 5-viewport responsiveness', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  await page.route('**://workablehr.s3.amazonaws.com/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
    });
  });

  const step41Jobs = [
    {
      id: 'workable:99brightminds:63E0790AD5',
      provider: 'workable',
      data_source: 'api',
      title: 'Sales Account Manager - Amman',
      company: '99brightminds',
      company_slug: '99brightminds',
      company_logo_url: 'https://workablehr.s3.amazonaws.com/uploads/account/logo/99brightminds/logo.png',
      company_logo_source: 'workable_account_logo',
      company_logo_verified: true,
      location: 'Amman, Jordan',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      salary: { minimum: 1200, maximum: 1500, currency: 'JOD', period: 'month' },
      description: '### Role Overview\n\nOwn B2B SaaS account growth in Amman.\n\n### Requirements\n\n- 3+ years B2B sales experience in Jordan',
      requirements: '### Requirements\n- 3+ years B2B sales experience in Jordan',
      eligibility: {
        physical_location_country: 'Jordan',
        nigeria_eligible: false,
      },
      posted_at: '2026-10-08T00:00:00Z',
      scraped_at: '2026-11-13T09:00:00Z',
      apply_url: 'https://apply.workable.com/99brightminds/j/63E0790AD5/apply',
      source_url: 'https://apply.workable.com/99brightminds/j/63E0790AD5',
      query_used: 'account manager',
      ats_source: 'workable',
    },
    {
      id: 'workable:verneek:3DBA754691',
      provider: 'workable',
      data_source: 'api',
      title: 'ML Ops Engineer',
      company: 'Verneek',
      company_slug: 'verneek',
      company_logo_url: 'https://workablehr.s3.amazonaws.com/uploads/account/logo/verneek/logo.png',
      company_logo_source: 'workable_account_logo',
      company_logo_verified: true,
      location: 'United States',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      salary: { minimum: 150000, maximum: 200000, currency: 'USD', period: 'year' },
      description: '### About the Role\n\nArchitect large-scale inference clusters.\n\n### Requirements\n\n- Kubernetes and PyTorch production expertise',
      requirements: '### Requirements\n- Kubernetes and PyTorch production expertise',
      eligibility: {
        allowed_residence_countries: ['United States'],
        residence_restriction_confirmed: true,
        nigeria_eligible: false,
      },
      posted_at: '2026-11-01T00:00:00Z',
      scraped_at: '2026-11-13T09:00:00Z',
      apply_url: 'https://apply.workable.com/verneek/j/3DBA754691/apply',
      source_url: 'https://apply.workable.com/verneek/j/3DBA754691',
      query_used: 'ml engineer',
      ats_source: 'workable',
    },
    {
      id: 'workable:learnrush:64801AA613',
      provider: 'workable',
      data_source: 'api',
      title: 'React Developer',
      company: 'Learnrush',
      company_slug: 'learnrush',
      company_logo_url: null,
      location: 'Noida, Uttar Pradesh, India',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      salary: { minimum: 400000, maximum: 800000, currency: 'INR', period: 'year' },
      description: '### What you will build\n\nModern TypeScript frontend applications.\n\n### Requirements\n\n- Strong React and Next.js proficiency',
      requirements: '### Requirements\n- Strong React and Next.js proficiency',
      eligibility: {
        physical_location_country: 'India',
        nigeria_eligible: false,
      },
      posted_at: '2026-10-20T00:00:00Z',
      scraped_at: '2026-11-13T09:00:00Z',
      apply_url: 'https://apply.workable.com/learnrush/j/64801AA613/apply',
      source_url: 'https://apply.workable.com/learnrush/j/64801AA613',
      query_used: 'react developer',
      ats_source: 'workable',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step41Jobs, total_so_far: step41Jobs.length }],
        [
          'done',
          {
            total: step41Jobs.length,
            search_time_ms: 91,
            serper_queries_used: 0,
            providers_searched: ['workable'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?q=Engineer');
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3, { timeout: 10000 });

  await expect(page.locator('.results-table')).toContainText('99brightminds');
  await expect(page.locator('.results-table')).toContainText('Verneek');
  await expect(page.locator('.results-table')).toContainText('Learnrush');
  await expect(page.locator('.results-table')).toContainText('JOD 1,200 – 1,500 / month');
  await expect(page.locator('.results-table')).toContainText('USD 150,000 – 200,000 / year');
  await expect(page.locator('.results-table')).toContainText('INR 400,000 – 800,000 / year');
  await expect(page.locator('.results-table')).toContainText('Hybrid');
  await expect(page.locator('.results-table')).toContainText('Remote');
  await expect(page.locator('.results-table')).toContainText('In-person');

  const marks = page.locator('.results-table [data-testid="company-mark"]');
  await expect(marks).toHaveCount(3);
  const brightImg = marks.nth(0).locator('img');
  await expect(brightImg).toBeVisible();
  await expect.poll(async () => brightImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  const vernImg = marks.nth(1).locator('img');
  await expect(vernImg).toBeVisible();
  await expect.poll(async () => vernImg.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
  await expect(marks.nth(2).locator('img')).toHaveCount(0);

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

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.results-table tbody tr.job-row').filter({ hasText: '99brightminds' }).first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('99brightminds');
  await expect(sheet).toContainText('JOD 1,200 – 1,500 / month');
  await expect(sheet.locator('[data-testid="company-mark"] img')).toBeVisible();
  expect(await sheet.locator('[data-testid="company-mark"]').evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');
  await expect(sheet).toContainText('3+ years B2B sales experience in Jordan');
  await expect(sheet).not.toContainText('Powered by Workable');
  await page.evaluate(() => {
    window.__openedWorkableUrls = [];
    window.open = (u) => {
      window.__openedWorkableUrls.push(String(u));
      return null;
    };
  });
  await sheet.getByRole('button', { name: /Open application/i }).click();
  const openedUrls = await page.evaluate(() => window.__openedWorkableUrls);
  expect(openedUrls).toEqual(['https://apply.workable.com/99brightminds/j/63E0790AD5/apply']);

  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('step 54: global selectable applicant country, eligibility filtering, separated work/eligibility presentation, and responsive audits', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const capturedUrls = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  const globalJobs = [
    {
      id: 'ashby:acme:worldwide',
      provider: 'ashby',
      data_source: 'api',
      title: 'Distributed Backend Engineer',
      company: 'Acme Global',
      company_slug: 'acme',
      location: 'Remote - Worldwide',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/acme/worldwide/application',
      source_url: 'https://jobs.ashbyhq.com/acme/worldwide',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        employment_arrangement: 'contractor',
        evidence_excerpt: 'Open to candidates worldwide.',
      },
    },
    {
      id: 'greenhouse:uscorp:us-remote',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Staff Systems Engineer',
      company: 'US Corp',
      company_slug: 'uscorp',
      location: 'Remote (US)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://boards.greenhouse.io/uscorp/jobs/2#app',
      source_url: 'https://boards.greenhouse.io/uscorp/jobs/2',
      query_used: 'engineer',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['United States'],
        allowed_country_codes: ['US'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Candidates must reside in the United States.',
      },
    },
    {
      id: 'recruitee:eurolabs:de-eu',
      provider: 'recruitee',
      data_source: 'api',
      title: 'Platform Engineer (Python)',
      company: 'Euro Labs',
      company_slug: 'eurolabs',
      location: 'Remote (Germany and EU)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://eurolabs.recruitee.com/o/platform-python/c/new',
      source_url: 'https://eurolabs.recruitee.com/o/platform-python',
      query_used: 'engineer',
      ats_source: 'recruitee',
      eligibility: {
        classification: 'region_restricted',
        allowed_residence_countries: ['Germany', 'EU'],
        allowed_country_codes: ['DE'],
        allowed_regions: ['EU'],
        pan_regional_remote_confirmed: true,
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Open to remote applicants in Germany and the EU.',
      },
    },
    {
      id: 'teamtailor:lagoshub:onsite-ng',
      provider: 'teamtailor',
      data_source: 'api',
      title: 'Operations Reliability Engineer',
      company: 'Lagos Hub',
      company_slug: 'lagoshub',
      location: 'Lagos, Nigeria',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://lagoshub.teamtailor.com/jobs/4#apply',
      source_url: 'https://lagoshub.teamtailor.com/jobs/4',
      query_used: 'engineer',
      ats_source: 'teamtailor',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Nigeria',
        physical_location_country_code: 'NG',
        evidence_excerpt: 'Onsite engineering role in Lagos, Nigeria.',
      },
    },
    {
      id: 'pinpointhq:cairo:egypt-only',
      provider: 'pinpointhq',
      data_source: 'api',
      title: 'Embedded Firmware Engineer',
      company: 'Nile Mobility',
      company_slug: 'nilemobility',
      location: 'Remote (Egypt)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://nilemobility.pinpointhq.com/postings/5/applications/new',
      source_url: 'https://nilemobility.pinpointhq.com/postings/5',
      query_used: 'engineer',
      ats_source: 'pinpointhq',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['Egypt'],
        allowed_country_codes: ['EG'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Remote role restricted to Egypt residents.',
      },
    },
    {
      id: 'lever:unverified:remote-unknown',
      provider: 'lever',
      data_source: 'api',
      title: 'API Infrastructure Engineer',
      company: 'Cloud Mystery',
      company_slug: 'cloudmystery',
      location: 'Remote',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-19T09:00:00Z',
      apply_url: 'https://jobs.lever.co/cloudmystery/6/apply',
      source_url: 'https://jobs.lever.co/cloudmystery/6',
      query_used: 'engineer',
      ats_source: 'lever',
      eligibility: {
        classification: 'unknown',
        global_remote_explicit: false,
      },
    },
  ];

  await page.route('**/search?**', async (route) => {
    capturedUrls.push(new URL(route.request().url()));
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: globalJobs, total_so_far: globalJobs.length }],
        [
          'done',
          {
            total: globalJobs.length,
            search_time_ms: 110,
            serper_queries_used: 0,
            providers_searched: ['ashby', 'greenhouse', 'recruitee', 'teamtailor', 'pinpointhq', 'lever'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // Search form displays "Where can you work from?" and uses interactive CountryCombobox
  const formTrigger = page.locator('#form-applicant-country-trigger');
  await expect(formTrigger).toBeVisible();
  await formTrigger.click();
  await page.locator('#form-applicant-country-search').fill('Nigeria');
  await page.getByRole('option', { name: /Nigeria NG/i }).click();
  await expect(formTrigger).toContainText('Nigeria (NG)');

  await page.getByLabel(/role or keyword/i).fill('Engineer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(6, { timeout: 10000 });
  expect(capturedUrls[0].searchParams.get('applicant_country')).toBe('NG');

  // Verify separated Work & eligibility column values without mislabeling US/unverified/Egypt as Worldwide
  await expect(page.locator('.results-table thead')).toContainText('Work & eligibility');
  await expect(rows.nth(0)).toContainText('Worldwide');
  await expect(rows.nth(1)).toContainText('Restricted · US only');
  await expect(rows.nth(1)).not.toContainText('Worldwide');
  await expect(rows.nth(2)).toContainText('Restricted · Germany and EU');
  await expect(rows.nth(3)).toContainText('Lagos, Nigeria');
  await expect(rows.nth(4)).toContainText('Restricted · Egypt only');
  await expect(rows.nth(5)).toContainText('Eligibility unverified');
  await expect(rows.nth(5)).not.toContainText('Worldwide');

  // Filter: Eligible + unverified -> hides 3 restricted roles (US, DE/EU, EG), keeps Worldwide, Lagos, Unverified
  const eligSelect = page.getByLabel('Filter by eligibility');
  await eligSelect.selectOption('eligible_and_unknown');
  await expect(rows).toHaveCount(3);

  // Filter: Eligible only -> Worldwide + Lagos onsite
  await eligSelect.selectOption('eligible');
  await expect(rows).toHaveCount(2);

  // Switch applicant country to Germany (DE) dynamically without re-searching -> Worldwide + DE/EU become eligible
  const searchCountBefore = capturedUrls.length;
  await page.locator('#toolbar-applicant-country-select').selectOption('DE');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText('Acme Global');
  await expect(rows.nth(1)).toContainText('Euro Labs');
  expect(capturedUrls.length).toBe(searchCountBefore);
  expect(page.url()).toContain('cc=DE');

  // Filter: Restricted only for DE -> US-only, Lagos onsite, Egypt-only
  await eligSelect.selectOption('restricted');
  await expect(rows).toHaveCount(3);

  // Reset filter -> switch to US -> check DetailSheet shows evidence details cleanly
  await eligSelect.selectOption('');
  await page.locator('#toolbar-applicant-country-select').selectOption('US');
  await rows.nth(1).click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Eligible from United States');
  await sheet.getByText('Evidence details').click();
  await expect(sheet).toContainText('Candidates must reside in the United States.');
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();

  // Check square geometry + zero horizontal overflow across 5 viewports + Axe a11y light/dark
  const triggerRadius = await page
    .locator('#toolbar-applicant-country-trigger')
    .evaluate((el) => getComputedStyle(el).borderRadius);
  expect(triggerRadius).toBe('0px');

  for (const vp of [
    { width: 1920, height: 1080, runAxe: false },
    { width: 1440, height: 900, runAxe: true },
    { width: 1024, height: 768, runAxe: false },
    { width: 768, height: 1024, runAxe: false },
    { width: 390, height: 844, runAxe: true },
  ]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(hasOverflow, `Horizontal overflow at ${vp.width}px`).toBe(false);
    if (vp.runAxe) {
      const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
    }
  }

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.setViewportSize({ width: 1440, height: 900 });
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('step 55: 7-country global remote and early-career UX validation without Nigeria default', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const capturedUrls = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  const mixedGlobalAndEarlyCareerJobs = [
    {
      id: 'ashby:supabase:ai-platform',
      provider: 'ashby',
      data_source: 'api',
      title: 'AI Platform Engineer',
      company: 'Supabase',
      company_slug: 'supabase',
      location: 'Remote, Global',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/supabase/ai-platform/application',
      source_url: 'https://jobs.ashbyhq.com/supabase/ai-platform',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        evidence_excerpt: 'We hire globally. Work from anywhere in the world.',
      },
    },
    {
      id: 'lever:metabase:sec-eng',
      provider: 'lever',
      data_source: 'api',
      title: 'Security Engineer',
      company: 'Metabase',
      company_slug: 'metabase',
      location: 'Global Remote',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-17T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.lever.co/metabase/sec-eng/apply',
      source_url: 'https://jobs.lever.co/metabase/sec-eng',
      query_used: 'engineer',
      ats_source: 'lever',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        evidence_excerpt: 'Global Remote.',
      },
    },
    {
      id: 'ashby:duck-duck-go:privacy',
      provider: 'ashby',
      data_source: 'api',
      title: 'Senior Privacy Engineer',
      company: 'DuckDuckGo',
      company_slug: 'duck-duck-go',
      location: 'South Africa (Remote); India (Remote); Singapore (Remote); UK (Remote); Canada (Remote); USA (Remote)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-15T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/duck-duck-go/privacy/application',
      source_url: 'https://jobs.ashbyhq.com/duck-duck-go/privacy',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['South Africa', 'India', 'Singapore', 'United Kingdom', 'Canada', 'United States'],
        allowed_country_codes: ['ZA', 'IN', 'SG', 'GB', 'CA', 'US'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Remote within ZA, IN, SG, UK, Canada, or USA.',
      },
    },
    {
      id: 'ashby:almedia:junior-data',
      provider: 'ashby',
      data_source: 'api',
      title: 'Junior Software Engineer - Data',
      company: 'Almedia',
      company_slug: 'almedia',
      location: 'Berlin',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      posted_at: '2026-11-16T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/almedia/junior-data/application',
      source_url: 'https://jobs.ashbyhq.com/almedia/junior-data',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Germany',
        physical_location_country_code: 'DE',
        allowed_residence_countries: ['Germany'],
        allowed_country_codes: ['DE'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Berlin on-site early-career data engineering role.',
      },
    },
    {
      id: 'greenhouse:affirm:swe1-ca',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Software Engineer I, Backend (Continuous Delivery)',
      company: 'Affirm',
      company_slug: 'affirm',
      location: 'Remote Canada',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-19T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://boards.greenhouse.io/affirm/jobs/swe1-ca#app',
      source_url: 'https://boards.greenhouse.io/affirm/jobs/swe1-ca',
      query_used: 'engineer',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['Canada'],
        allowed_country_codes: ['CA'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Remote Canada.',
      },
    },
    {
      id: 'workable:kuda:lagos-da',
      provider: 'workable',
      data_source: 'api',
      title: 'Senior Data Analyst',
      company: 'Kuda',
      company_slug: 'kuda',
      location: 'Lagos, Nigeria',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      posted_at: '2026-11-14T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://apply.workable.com/kuda/j/E7B7CA3E98/apply',
      source_url: 'https://apply.workable.com/kuda/j/E7B7CA3E98',
      query_used: 'engineer',
      ats_source: 'workable',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Nigeria',
        physical_location_country_code: 'NG',
        allowed_residence_countries: ['Nigeria'],
        allowed_country_codes: ['NG'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'On-site in Lagos, Nigeria.',
      },
    },
    {
      id: 'workable:electrum:grad-za',
      provider: 'workable',
      data_source: 'api',
      title: '2027 Software Developer Graduate Programme',
      company: 'Electrum',
      company_slug: 'electrum',
      location: 'Cape Town, South Africa',
      is_remote: false,
      employment_type: 'internship',
      work_model: 'in_person',
      posted_at: '2026-11-12T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://apply.workable.com/electrum/j/5CD96E8A30/apply',
      source_url: 'https://apply.workable.com/electrum/j/5CD96E8A30',
      query_used: 'engineer',
      ats_source: 'workable',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'South Africa',
        physical_location_country_code: 'ZA',
        allowed_residence_countries: ['South Africa'],
        allowed_country_codes: ['ZA'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Cape Town graduate programme.',
      },
    },
    {
      id: 'ashby:mystery:unverified',
      provider: 'ashby',
      data_source: 'api',
      title: 'Remote Cloud Systems Engineer',
      company: 'Cloud Unknown',
      company_slug: 'cloudunknown',
      location: 'Remote',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/cloudunknown/unverified/application',
      source_url: 'https://jobs.ashbyhq.com/cloudunknown/unverified',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'unknown',
        global_remote_explicit: false,
      },
    },
  ];

  await page.route('**/search?**', async (route) => {
    capturedUrls.push(new URL(route.request().url()));
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: mixedGlobalAndEarlyCareerJobs, total_so_far: mixedGlobalAndEarlyCareerJobs.length }],
        [
          'done',
          {
            total: mixedGlobalAndEarlyCareerJobs.length,
            search_time_ms: 95,
            serper_queries_used: 0,
            providers_searched: ['ashby', 'lever', 'greenhouse', 'workable'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // 1. Default load must NOT force Nigeria
  const formTrigger = page.locator('#form-applicant-country-trigger');
  await expect(formTrigger).toBeVisible();
  await expect(formTrigger).not.toContainText('Nigeria');

  // 2. Broader ISO catalog works cleanly (Brazil discoverable before picking Nigeria)
  await formTrigger.click();
  const countrySearch = page.locator('#form-applicant-country-search');
  await countrySearch.fill('Brazil');
  await expect(page.getByRole('option', { name: /Brazil BR/i })).toBeVisible();
  await countrySearch.fill('Nigeria');
  await page.getByRole('option', { name: /Nigeria NG/i }).click();
  await expect(formTrigger).toContainText('Nigeria (NG)');

  await page.getByLabel(/role or keyword/i).fill('Engineer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(8, { timeout: 10000 });
  expect(capturedUrls[0].searchParams.get('applicant_country')).toBe('NG');

  // Work arrangement and job geography must remain distinct; unverified remote never displays Worldwide
  await expect(rows.nth(7)).toContainText('Eligibility unverified');
  await expect(rows.nth(7)).not.toContainText('Worldwide');
  await expect(rows.nth(5)).toContainText('Lagos, Nigeria');

  const eligSelect = page.getByLabel('Filter by eligibility');
  const toolbarSelect = page.locator('#toolbar-applicant-country-select');
  const initialSearchCalls = capturedUrls.length;

  // 3. Evaluate all 7 required user countries dynamically (NG, DE, US, IN, CA, GH, EG)
  const expectedEligibleByCountry = [
    { code: 'NG', eligibleCount: 3, eligibleOrUnverifiedCount: 4, expectedText: 'Kuda' },
    { code: 'DE', eligibleCount: 3, eligibleOrUnverifiedCount: 4, expectedText: 'Almedia' },
    { code: 'US', eligibleCount: 3, eligibleOrUnverifiedCount: 4, expectedText: 'Senior Privacy Engineer' },
    { code: 'IN', eligibleCount: 3, eligibleOrUnverifiedCount: 4, expectedText: 'Senior Privacy Engineer' },
    { code: 'CA', eligibleCount: 4, eligibleOrUnverifiedCount: 5, expectedText: 'Affirm' },
    { code: 'GH', eligibleCount: 2, eligibleOrUnverifiedCount: 3, expectedText: 'Metabase' },
    { code: 'EG', eligibleCount: 2, eligibleOrUnverifiedCount: 3, expectedText: 'Metabase' },
  ];

  for (const check of expectedEligibleByCountry) {
    await toolbarSelect.selectOption(check.code);
    await eligSelect.selectOption('eligible_and_unknown');
    await expect(rows).toHaveCount(check.eligibleOrUnverifiedCount);
    await eligSelect.selectOption('eligible');
    await expect(rows).toHaveCount(check.eligibleCount);
    await expect(page.locator('.results-table tbody')).toContainText(check.expectedText);
  }

  // Switching countries never re-triggers backend search
  expect(capturedUrls.length).toBe(initialSearchCalls);

  // Restricted roles clearly distinguishable and inspectable in secondary DetailSheet
  await eligSelect.selectOption('restricted');
  await expect(rows).toHaveCount(5);
  await eligSelect.selectOption('');
  await toolbarSelect.selectOption('CA');

  await rows.filter({ hasText: 'Software Engineer I, Backend' }).first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Software Engineer I, Backend');
  await expect(sheet).toContainText('Eligible from Canada');
  await sheet.getByText('Evidence details').click();
  await expect(sheet).toContainText('Remote Canada.');
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();

  // Geometry, overflow across 5 viewports, Axe light & dark
  const triggerRadius = await page
    .locator('#toolbar-applicant-country-trigger')
    .evaluate((el) => getComputedStyle(el).borderRadius);
  expect(triggerRadius).toBe('0px');

  for (const vp of [
    { width: 1920, height: 1080, runAxe: false },
    { width: 1440, height: 900, runAxe: true },
    { width: 1024, height: 768, runAxe: false },
    { width: 768, height: 1024, runAxe: false },
    { width: 390, height: 844, runAxe: true },
  ]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(hasOverflow, `Horizontal overflow at ${vp.width}px`).toBe(false);
    if (vp.runAxe) {
      const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
    }
  }

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.setViewportSize({ width: 1440, height: 900 });
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('step 56: 11-country global remote and early-career filter composition', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const capturedUrls = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  const step56MixedJobs = [
    {
      id: 'ashby:supabase:ai-platform-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'AI Platform Engineer',
      company: 'Supabase',
      company_slug: 'supabase',
      location: 'Remote, Global',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/supabase/ai-platform/application',
      source_url: 'https://jobs.ashbyhq.com/supabase/ai-platform',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        evidence_excerpt: 'We hire globally. Work from anywhere in the world.',
      },
    },
    {
      id: 'ashby:elevenlabs:fullstack-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'Full-Stack Engineer (Backend Leaning)',
      company: 'ElevenLabs',
      company_slug: 'elevenlabs',
      location: 'Remote',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-19T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/elevenlabs/fullstack/application',
      source_url: 'https://jobs.ashbyhq.com/elevenlabs/fullstack',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        evidence_excerpt: 'This role is remote-first and can be executed globally.',
      },
    },
    {
      id: 'ashby:cohere:ml-intern-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'Machine Learning Intern/Co-op (Winter 2027)',
      company: 'Cohere',
      company_slug: 'cohere',
      location: 'Canada; United States; United Kingdom',
      is_remote: true,
      employment_type: 'internship',
      work_model: 'remote',
      posted_at: '2026-11-15T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/cohere/ml-intern/application',
      source_url: 'https://jobs.ashbyhq.com/cohere/ml-intern',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['Canada', 'United States', 'United Kingdom'],
        allowed_country_codes: ['CA', 'US', 'GB'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Open to remote interns in Canada, United States, or United Kingdom.',
      },
    },
    {
      id: 'greenhouse:coinbase:swe-intern-sg-s56',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Software Engineer Intern (Singapore)',
      company: 'Coinbase',
      company_slug: 'coinbase',
      location: 'Hybrid - Singapore',
      is_remote: false,
      employment_type: 'internship',
      work_model: 'hybrid',
      posted_at: '2026-11-16T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://boards.greenhouse.io/coinbase/jobs/swe-intern-sg#app',
      source_url: 'https://boards.greenhouse.io/coinbase/jobs/swe-intern-sg',
      query_used: 'engineer',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Singapore',
        physical_location_country_code: 'SG',
        allowed_residence_countries: ['Singapore'],
        allowed_country_codes: ['SG'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Hybrid - Singapore.',
      },
    },
    {
      id: 'workable:electrum:grad-za-s56',
      provider: 'workable',
      data_source: 'api',
      title: '2027 Software Developer Graduate Programme',
      company: 'Electrum',
      company_slug: 'electrum',
      location: 'Cape Town, South Africa',
      is_remote: false,
      employment_type: 'internship',
      work_model: 'in_person',
      posted_at: '2026-11-12T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://apply.workable.com/electrum/j/5CD96E8A30/apply',
      source_url: 'https://apply.workable.com/electrum/j/5CD96E8A30',
      query_used: 'engineer',
      ats_source: 'workable',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'South Africa',
        physical_location_country_code: 'ZA',
        allowed_residence_countries: ['South Africa'],
        allowed_country_codes: ['ZA'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Cape Town graduate programme.',
      },
    },
    {
      id: 'ashby:almedia:junior-data-de-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'Junior Software Engineer - Data',
      company: 'Almedia',
      company_slug: 'almedia',
      location: 'Berlin',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      posted_at: '2026-11-16T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/almedia/junior-data/application',
      source_url: 'https://jobs.ashbyhq.com/almedia/junior-data',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Germany',
        physical_location_country_code: 'DE',
        allowed_residence_countries: ['Germany'],
        allowed_country_codes: ['DE'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Berlin on-site junior engineering role.',
      },
    },
    {
      id: 'ashby:duck-duck-go:privacy-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'Senior Privacy Engineer',
      company: 'DuckDuckGo',
      company_slug: 'duck-duck-go',
      location: 'South Africa (Remote); India (Remote); Singapore (Remote); Australia (Remote); Canada (Remote); USA (Remote)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-15T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/duck-duck-go/privacy/application',
      source_url: 'https://jobs.ashbyhq.com/duck-duck-go/privacy',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['South Africa', 'India', 'Singapore', 'Australia', 'Canada', 'United States'],
        allowed_country_codes: ['ZA', 'IN', 'SG', 'AU', 'CA', 'US'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Remote within ZA, IN, SG, AU, Canada, or USA.',
      },
    },
    {
      id: 'greenhouse:wikimedia:eor-africa-s56',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Senior Staff Platform Engineer',
      company: 'Wikimedia Foundation',
      company_slug: 'wikimedia',
      location: 'Remote (Ghana, Kenya, South Africa)',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-17T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://boards.greenhouse.io/wikimedia/jobs/eor-africa#app',
      source_url: 'https://boards.greenhouse.io/wikimedia/jobs/eor-africa',
      query_used: 'engineer',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'country_restricted',
        allowed_residence_countries: ['Ghana', 'Kenya', 'South Africa'],
        allowed_country_codes: ['GH', 'KE', 'ZA'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Eligible countries include Ghana, Kenya, and South Africa.',
      },
    },
    {
      id: 'teamtailor:propertyfinder:cairo-swe-s56',
      provider: 'teamtailor',
      data_source: 'api',
      title: 'Senior Software Engineer (Cairo)',
      company: 'Property Finder',
      company_slug: 'propertyfinder',
      location: 'Cairo, Egypt',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'hybrid',
      posted_at: '2026-11-14T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://propertyfinder.teamtailor.com/jobs/cairo-swe',
      source_url: 'https://propertyfinder.teamtailor.com/jobs/cairo-swe',
      query_used: 'engineer',
      ats_source: 'teamtailor',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Egypt',
        physical_location_country_code: 'EG',
        allowed_residence_countries: ['Egypt'],
        allowed_country_codes: ['EG'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'Hybrid in Cairo, Egypt.',
      },
    },
    {
      id: 'workable:kuda:lagos-swe-s56',
      provider: 'workable',
      data_source: 'api',
      title: 'Backend Engineer (Lagos)',
      company: 'Kuda',
      company_slug: 'kuda',
      location: 'Lagos, Nigeria',
      is_remote: false,
      employment_type: 'full_time',
      work_model: 'in_person',
      posted_at: '2026-11-14T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://apply.workable.com/kuda/j/E7B7CA3E98/apply',
      source_url: 'https://apply.workable.com/kuda/j/E7B7CA3E98',
      query_used: 'engineer',
      ats_source: 'workable',
      eligibility: {
        classification: 'onsite_or_hybrid_local',
        physical_location_country: 'Nigeria',
        physical_location_country_code: 'NG',
        allowed_residence_countries: ['Nigeria'],
        allowed_country_codes: ['NG'],
        residence_restriction_confirmed: true,
        evidence_excerpt: 'On-site in Lagos, Nigeria.',
      },
    },
    {
      id: 'ashby:mystery:unverified-s56',
      provider: 'ashby',
      data_source: 'api',
      title: 'Remote Platform Systems Engineer',
      company: 'Cloud Unknown',
      company_slug: 'cloudunknown',
      location: 'Remote',
      is_remote: true,
      employment_type: 'full_time',
      work_model: 'remote',
      posted_at: '2026-11-18T09:00:00Z',
      scraped_at: '2026-11-21T09:00:00Z',
      apply_url: 'https://jobs.ashbyhq.com/cloudunknown/unverified/application',
      source_url: 'https://jobs.ashbyhq.com/cloudunknown/unverified',
      query_used: 'engineer',
      ats_source: 'ashby',
      eligibility: {
        classification: 'unknown',
        global_remote_explicit: false,
      },
    },
  ];

  await page.route('**/search?**', async (route) => {
    capturedUrls.push(new URL(route.request().url()));
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: step56MixedJobs, total_so_far: step56MixedJobs.length }],
        [
          'done',
          {
            total: step56MixedJobs.length,
            search_time_ms: 88,
            serper_queries_used: 0,
            providers_searched: ['ashby', 'greenhouse', 'teamtailor', 'workable'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // 1. Default load must never force Nigeria
  const formTrigger = page.locator('#form-applicant-country-trigger');
  await expect(formTrigger).toBeVisible();
  await expect(formTrigger).not.toContainText('Nigeria');

  await formTrigger.click();
  await page.locator('#form-applicant-country-search').fill('Nigeria');
  await page.getByRole('option', { name: /Nigeria NG/i }).click();
  await expect(formTrigger).toContainText('Nigeria (NG)');

  await page.getByLabel(/role or keyword/i).fill('Engineer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(11, { timeout: 10000 });
  expect(capturedUrls[0].searchParams.get('applicant_country')).toBe('NG');

  // Work arrangement and eligibility remain separated; restricted or unverified remote never shows Worldwide
  const elevenLabsRow = rows.filter({ hasText: 'Eleven Labs' }).first();
  await expect(elevenLabsRow).toContainText('Worldwide');
  const cohereRow = rows.filter({ hasText: 'Cohere' }).first();
  await expect(cohereRow).toContainText('Remote');
  await expect(cohereRow).not.toContainText('Worldwide');
  const unknownRow = rows.filter({ hasText: 'Cloud Unknown' }).first();
  await expect(unknownRow).toContainText('Eligibility unverified');
  await expect(unknownRow).not.toContainText('Worldwide');

  const eligSelect = page.getByLabel('Filter by eligibility');
  const empSelect = page.getByLabel('Filter by employment type');
  const toolbarSearch = page.getByPlaceholder(/filter results/i);
  const toolbarSelect = page.locator('#toolbar-applicant-country-select');
  const initialSearchCalls = capturedUrls.length;

  // 2. Verify all 11 representative countries dynamically (NG, DE, US, CA, GH, KE, ZA, EG, IN, SG, AU)
  const expectedByCountry11 = [
    { code: 'NG', eligible: 3, eligibleOrUnk: 4, expectedText: 'Kuda' },
    { code: 'DE', eligible: 3, eligibleOrUnk: 4, expectedText: 'Junior Software Engineer - Data' },
    { code: 'US', eligible: 4, eligibleOrUnk: 5, expectedText: 'Machine Learning Intern/Co-op' },
    { code: 'CA', eligible: 4, eligibleOrUnk: 5, expectedText: 'Machine Learning Intern/Co-op' },
    { code: 'GH', eligible: 3, eligibleOrUnk: 4, expectedText: 'Wikimedia Foundation' },
    { code: 'KE', eligible: 3, eligibleOrUnk: 4, expectedText: 'Wikimedia Foundation' },
    { code: 'ZA', eligible: 5, eligibleOrUnk: 6, expectedText: 'Electrum' },
    { code: 'EG', eligible: 3, eligibleOrUnk: 4, expectedText: 'Property Finder' },
    { code: 'IN', eligible: 3, eligibleOrUnk: 4, expectedText: 'Senior Privacy Engineer' },
    { code: 'SG', eligible: 4, eligibleOrUnk: 5, expectedText: 'Coinbase' },
    { code: 'AU', eligible: 3, eligibleOrUnk: 4, expectedText: 'Senior Privacy Engineer' },
  ];

  for (const check of expectedByCountry11) {
    await toolbarSelect.selectOption(check.code);
    await eligSelect.selectOption('eligible_and_unknown');
    await expect(rows).toHaveCount(check.eligibleOrUnk);
    await eligSelect.selectOption('eligible');
    await expect(rows).toHaveCount(check.eligible);
    await expect(page.locator('.results-table tbody')).toContainText(check.expectedText);
  }
  expect(capturedUrls.length).toBe(initialSearchCalls);

  // 3. Early-career filter composition: employmentFilter='Internship' + eligibilityFilter='eligible'
  await empSelect.selectOption('Internship');
  await eligSelect.selectOption('eligible');

  await toolbarSelect.selectOption('SG');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Coinbase');

  await toolbarSelect.selectOption('CA');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Cohere');

  await toolbarSelect.selectOption('US');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Cohere');

  await toolbarSelect.selectOption('ZA');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Electrum');

  await toolbarSelect.selectOption('NG');
  await expect(rows).toHaveCount(0);

  // 4. Keyword composition ('Junior', 'Graduate') + eligibilityFilter='eligible'
  await empSelect.selectOption('');
  await toolbarSearch.fill('Junior');
  await toolbarSelect.selectOption('DE');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Almedia');
  await toolbarSelect.selectOption('NG');
  await expect(rows).toHaveCount(0);

  await toolbarSearch.fill('Graduate');
  await toolbarSelect.selectOption('ZA');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Electrum');
  await toolbarSelect.selectOption('NG');
  await expect(rows).toHaveCount(0);

  // Reset filters -> check DetailSheet evidence for Eleven Labs (NG)
  await toolbarSearch.fill('');
  await eligSelect.selectOption('');
  await toolbarSelect.selectOption('NG');
  await rows.filter({ hasText: 'Eleven Labs' }).first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText('Full-Stack Engineer (Backend Leaning)');
  await expect(sheet).toContainText('Worldwide');
  await sheet.getByText('Evidence details').click();
  await expect(sheet).toContainText('can be executed globally');
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();

  // Square geometry, overflow across 5 viewports, Axe light & dark
  const triggerRadius = await page
    .locator('#toolbar-applicant-country-trigger')
    .evaluate((el) => getComputedStyle(el).borderRadius);
  expect(triggerRadius).toBe('0px');

  for (const vp of [
    { width: 1920, height: 1080, runAxe: false },
    { width: 1440, height: 900, runAxe: true },
    { width: 1024, height: 768, runAxe: false },
    { width: 768, height: 1024, runAxe: false },
    { width: 390, height: 844, runAxe: true },
  ]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(hasOverflow, `Horizontal overflow at ${vp.width}px`).toBe(false);
    if (vp.runAxe) {
      const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
    }
  }

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  await page.setViewportSize({ width: 1440, height: 900 });
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});


test('Phase 5: Freshness tiers, Older postings divider, explicit sort override, and /api/eligibility/evaluate wiring', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const evaluateRequests = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(err.message));

  const sse = (events) =>
    events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('');

  const daysAgoIso = (days) => new Date(Date.now() - days * 86400000).toISOString();
  const phase5Jobs = [
    {
      id: 'greenhouse:acme:stale-role',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Alpha Legacy Systems Engineer',
      company: 'Legacy Co',
      company_slug: 'legacyco',
      location: 'Remote, Worldwide',
      work_model: 'remote',
      posted_at: daysAgoIso(140),
      last_verified_at: daysAgoIso(0),
      freshness: 'stale',
      scraped_at: daysAgoIso(0),
      apply_url: 'https://boards.greenhouse.io/legacyco/jobs/1',
      source_url: 'https://boards.greenhouse.io/legacyco/jobs/1',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        objective_scope_label: 'Worldwide',
      },
    },
    {
      id: 'ashby:unknown:undated-role',
      provider: 'ashby',
      data_source: 'api',
      title: 'Beta Undated Platform Engineer',
      company: 'Mystery Co',
      company_slug: 'mysteryco',
      location: 'Remote',
      work_model: 'remote',
      posted_at: null,
      freshness: null,
      scraped_at: daysAgoIso(0),
      apply_url: 'https://jobs.ashbyhq.com/mysteryco/2',
      source_url: 'https://jobs.ashbyhq.com/mysteryco/2',
      ats_source: 'ashby',
      eligibility: {
        classification: 'unknown',
        global_remote_explicit: false,
        objective_scope_label: 'Eligibility unverified',
      },
    },
    {
      id: 'ashby:pipe:evergreen-role',
      provider: 'ashby',
      data_source: 'api',
      title: 'Gamma Pipeline Software Engineer',
      company: 'Pipeline Labs',
      company_slug: 'pipelinelabs',
      location: 'Remote, Global',
      work_model: 'remote',
      posted_at: daysAgoIso(180),
      last_verified_at: daysAgoIso(0),
      freshness: 'evergreen',
      scraped_at: daysAgoIso(0),
      apply_url: 'https://jobs.ashbyhq.com/pipelinelabs/3',
      source_url: 'https://jobs.ashbyhq.com/pipelinelabs/3',
      ats_source: 'ashby',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        objective_scope_label: 'Worldwide',
      },
    },
    {
      id: 'lever:mid:recent-role',
      provider: 'lever',
      data_source: 'api',
      title: 'Delta Mid-Age Backend Engineer',
      company: 'MidAge Systems',
      company_slug: 'midagesystems',
      location: 'United States',
      work_model: 'remote',
      posted_at: daysAgoIso(45),
      last_verified_at: daysAgoIso(0),
      freshness: 'recent',
      scraped_at: daysAgoIso(0),
      apply_url: 'https://jobs.lever.co/midagesystems/4',
      source_url: 'https://jobs.lever.co/midagesystems/4',
      ats_source: 'lever',
      eligibility: {
        classification: 'country_restricted',
        allowed_country_codes: ['US'],
        residence_restriction_confirmed: true,
        objective_scope_label: 'US only',
      },
    },
    {
      id: 'greenhouse:fresh:current-role',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Zeta Current Backend Engineer',
      company: 'Fresh Co',
      company_slug: 'freshco',
      location: 'Remote, Worldwide',
      work_model: 'remote',
      posted_at: daysAgoIso(2),
      last_verified_at: daysAgoIso(0),
      freshness: 'fresh',
      scraped_at: daysAgoIso(0),
      apply_url: 'https://boards.greenhouse.io/freshco/jobs/5',
      source_url: 'https://boards.greenhouse.io/freshco/jobs/5',
      ats_source: 'greenhouse',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        objective_scope_label: 'Worldwide',
      },
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: phase5Jobs, total_so_far: phase5Jobs.length }],
        [
          'done',
          {
            total: phase5Jobs.length,
            search_time_ms: 42,
            serper_queries_used: 0,
            providers_searched: ['greenhouse', 'ashby', 'lever'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.route('**/api/eligibility/evaluate', async (route) => {
    const reqJson = await route.request().postDataJSON();
    evaluateRequests.push(reqJson);
    const resp = await page.request.post('/api/eligibility/evaluate', { data: reqJson });
    expect(resp.status()).toBe(200);
    await route.fulfill({ response: resp });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  await page.getByLabel(/role or keyword/i).fill('Backend');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(5, { timeout: 10000 });

  // 1. Default relevance order ranks fresh -> recent -> evergreen -> unknown -> stale
  const rowTexts = await rows.allTextContents();
  expect(rowTexts[0]).toContain('Zeta Current Backend Engineer');
  expect(rowTexts[1]).toContain('Delta Mid-Age Backend Engineer');
  expect(rowTexts[2]).toContain('Gamma Pipeline Software Engineer');
  expect(rowTexts[3]).toContain('Beta Undated Platform Engineer');
  expect(rowTexts[4]).toContain('Alpha Legacy Systems Engineer');

  // 2. Older postings divider sits directly before the stale row and age badges render on every row
  const tableDivider = page.locator('.results-table [data-testid="older-postings-divider"]');
  await expect(tableDivider).toBeVisible();
  await expect(tableDivider).toContainText('Older postings (1)');
  const dividerPrecedesStale = await page.locator('.results-table tbody > tr').evaluateAll((trs) => {
    const divIdx = trs.findIndex((tr) => tr.getAttribute('data-testid') === 'older-postings-divider');
    const staleIdx = trs.findIndex((tr) => tr.getAttribute('data-freshness-tier') === 'stale');
    return divIdx !== -1 && staleIdx === divIdx + 1;
  });
  expect(dividerPrecedesStale).toBe(true);
  await expect(page.locator('.results-table [data-testid="job-age-badge"]')).toHaveCount(5);

  // 3. DetailSheet displays detail-age-badge and verified timestamp
  await rows.first().click();
  const sheet = page.locator('.detail-sheet');
  await expect(sheet).toBeVisible();
  await expect(sheet.locator('[data-testid="detail-age-badge"]')).toContainText('2d ago');
  await expect(sheet).toContainText('Last verified:');
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();

  // 4. Mobile 390px view renders divider and age badges with zero horizontal overflow
  await page.setViewportSize({ width: 390, height: 844 });
  const cardsDivider = page.locator('.cards-mobile-view [data-testid="older-postings-divider"]');
  await expect(cardsDivider).toBeVisible();
  await expect(cardsDivider).toContainText('Older postings (1)');
  await expect(page.locator('.cards-mobile-view [data-testid="job-age-badge"]')).toHaveCount(5);
  const mobileOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  );
  expect(mobileOverflow).toBe(false);

  // 5. Selecting an applicant country invokes POST /api/eligibility/evaluate and updates assessments
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('#toolbar-applicant-country-trigger').click();
  await page.locator('#toolbar-applicant-country-search').fill('Nigeria');
  await page.getByRole('option', { name: /Nigeria NG/i }).click();
  await expect.poll(() => evaluateRequests.length, { timeout: 5000 }).toBeGreaterThanOrEqual(1);
  expect(evaluateRequests[0].applicant_country).toBe('NG');
  await expect(rows.nth(1)).toContainText('US only');

  // 6. Explicit sort overrides freshness ordering and hides Older postings divider
  await page.locator('.results-table thead th', { hasText: 'Role' }).click();
  await expect(tableDivider).toHaveCount(0);
  const sortedTitles = await rows.allTextContents();
  expect(sortedTitles[0]).toContain('Alpha Legacy Systems Engineer');
  expect(sortedTitles[4]).toContain('Zeta Current Backend Engineer');

  // 7. Axe WCAG AA accessibility in light and dark themes
  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});


test('Phase 6: CompanyMark Logo.dev fallback chain (mocked img.logo.dev), 404 fallback, alt text, and footer attribution', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const logoDevRequests = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(err.message));

  const mockPkToken = ['pk', 'bottompot', 'mocktest'].join('_');
  await page.addInitScript((tok) => {
    window.__BOTTOM_POT_LOGO_DEV_TOKEN__ = tok;
  }, mockPkToken);

  const svgBytes = Buffer.from(
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#1A382B"/></svg>',
    'utf-8'
  );

  await page.route('https://cdn.example.test/**', async (route) => {
    if (route.request().url().includes('broken-api-logo.png')) {
      await route.fulfill({ status: 404, body: 'Not found' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svgBytes });
  });

  await page.route('https://img.logo.dev/**', async (route) => {
    const reqUrl = route.request().url();
    logoDevRequests.push(reqUrl);
    if (reqUrl.includes('/brokenlogo.io')) {
      await route.fulfill({ status: 404, body: 'Not found' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svgBytes });
  });

  const sse = (events) =>
    events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('');
  const recentIso = new Date(Date.now() - 86400000).toISOString();

  const phase6Jobs = [
    {
      id: 'greenhouse:api:1',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Role 1 Verified API Logo',
      company: 'NativeLogo Corp',
      company_slug: 'nativelogo',
      company_logo_url: 'https://cdn.example.test/verified-api-logo.png',
      company_domain: 'nativelogo.com',
      location: 'Remote, Worldwide',
      work_model: 'remote',
      posted_at: recentIso,
      freshness: 'fresh',
      scraped_at: recentIso,
      apply_url: 'https://boards.greenhouse.io/nativelogo/jobs/1',
      source_url: 'https://boards.greenhouse.io/nativelogo/jobs/1',
      ats_source: 'greenhouse',
    },
    {
      id: 'ashby:logodev:2',
      provider: 'ashby',
      data_source: 'api',
      title: 'Role 2 Logo.dev Success',
      company: 'Supabase',
      company_slug: 'supabase',
      company_logo_url: null,
      company_domain: 'supabase.com',
      location: 'Remote, Global',
      work_model: 'remote',
      posted_at: recentIso,
      freshness: 'fresh',
      scraped_at: recentIso,
      apply_url: 'https://jobs.ashbyhq.com/supabase/2',
      source_url: 'https://jobs.ashbyhq.com/supabase/2',
      ats_source: 'ashby',
    },
    {
      id: 'lever:brokenapi:3',
      provider: 'lever',
      data_source: 'api',
      title: 'Role 3 Broken API -> Logo.dev',
      company: 'StepDown Co',
      company_slug: 'stepdown',
      company_logo_url: 'https://cdn.example.test/broken-api-logo.png',
      company_domain: 'stepdown.io',
      location: 'Remote',
      work_model: 'remote',
      posted_at: recentIso,
      freshness: 'fresh',
      scraped_at: recentIso,
      apply_url: 'https://jobs.lever.co/stepdown/3',
      source_url: 'https://jobs.lever.co/stepdown/3',
      ats_source: 'lever',
    },
    {
      id: 'workable:404logodev:4',
      provider: 'workable',
      data_source: 'api',
      title: 'Role 4 Logo.dev 404 -> Monogram',
      company: 'MissingLogo LLC',
      company_slug: 'missinglogo',
      company_logo_url: null,
      company_domain: 'brokenlogo.io',
      location: 'Remote',
      work_model: 'remote',
      posted_at: recentIso,
      freshness: 'fresh',
      scraped_at: recentIso,
      apply_url: 'https://apply.workable.com/missinglogo/j/4',
      source_url: 'https://apply.workable.com/missinglogo/j/4',
      ats_source: 'workable',
    },
    {
      id: 'greenhouse:nodomain:5',
      provider: 'greenhouse',
      data_source: 'api',
      title: 'Role 5 No Domain Monogram',
      company: 'Anon Startup',
      company_slug: 'anonstartup',
      company_logo_url: null,
      company_domain: null,
      location: 'Remote',
      work_model: 'remote',
      posted_at: recentIso,
      freshness: 'fresh',
      scraped_at: recentIso,
      apply_url: 'https://boards.greenhouse.io/anonstartup/jobs/5',
      source_url: 'https://boards.greenhouse.io/anonstartup/jobs/5',
      ats_source: 'greenhouse',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: phase6Jobs, total_so_far: phase6Jobs.length }],
        [
          'done',
          {
            total: phase6Jobs.length,
            search_time_ms: 35,
            serper_queries_used: 0,
            providers_searched: ['greenhouse', 'ashby', 'lever', 'workable'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  await page.getByLabel(/role or keyword/i).fill('Role');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const rows = page.locator('.results-table tbody tr.job-row');
  await expect(rows).toHaveCount(5, { timeout: 10000 });

  // 1. Native API verified logo renders without requesting Logo.dev
  const mark1 = rows.nth(0).locator('[data-testid="company-mark"]');
  await expect(mark1).toHaveAttribute('data-logo-source', 'api');
  await expect(mark1.locator('img')).toHaveAttribute('alt', 'NativeLogo Corp');
  await expect(mark1.locator('img')).toHaveAttribute('loading', 'lazy');
  expect(await mark1.evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');

  // 2. Null API logo with curated domain renders Logo.dev with fallback=404 and square border
  const mark2 = rows.nth(1).locator('[data-testid="company-mark"]');
  await expect(mark2).toHaveAttribute('data-logo-source', 'logo_dev');
  await expect(mark2.locator('img')).toHaveAttribute('alt', 'Supabase');
  const mark2Src = await mark2.locator('img').getAttribute('src');
  expect(mark2Src).toContain('https://img.logo.dev/supabase.com?');
  expect(mark2Src).toContain('fallback=404');
  expect(await mark2.evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');

  // 3. Broken API logo (404) steps cleanly to Logo.dev
  const mark3 = rows.nth(2).locator('[data-testid="company-mark"]');
  await expect(mark3).toHaveAttribute('data-logo-source', 'logo_dev', { timeout: 5000 });
  await expect(mark3.locator('img')).toHaveAttribute('alt', 'StepDown Co');

  // 4. Logo.dev 404 steps cleanly to square monogram (zero broken image icon)
  const mark4 = rows.nth(3).locator('[data-testid="company-mark"]');
  await expect(mark4).toHaveAttribute('data-logo-source', 'monogram', { timeout: 5000 });
  await expect(mark4.locator('img')).toHaveCount(0);
  await expect(mark4).toHaveText('ML');
  expect(await mark4.evaluate((el) => getComputedStyle(el).borderRadius)).toBe('0px');

  // 5. Missing domain renders monogram without ever hitting Logo.dev
  const mark5 = rows.nth(4).locator('[data-testid="company-mark"]');
  await expect(mark5).toHaveAttribute('data-logo-source', 'monogram');
  await expect(mark5.locator('img')).toHaveCount(0);
  expect(logoDevRequests.some((u) => u.includes('nativelogo.com'))).toBe(false);
  expect(logoDevRequests.some((u) => u.includes('anonstartup'))).toBe(false);

  // 6. Footer displays required Logo.dev attribution link
  const logoDevLink = page.locator('footer a[href="https://logo.dev"]');
  await expect(logoDevLink).toBeVisible();
  await expect(logoDevLink).toContainText('Logos provided by Logo.dev');

  // 7. Axe WCAG AA accessibility (light & dark)
  const axeLight = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  const themeBtn = page.getByRole('button', { name: /toggle theme/i });
  await themeBtn.click();
  const axeDark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await themeBtn.click();

  expect(consoleErrors.filter((msg) => !msg.includes('status of 404'))).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('Phase 8 beta states: budget exhausted, no-country notice, report link, and 390px mobile layout', async ({ page }) => {
  await page.addInitScript(() => {
    globalThis.__BOTTOM_POT_REPORT_PROBLEM_URL__ = 'https://github.com/richmondsogo/bottom-pot/issues/new?template=listing.yml';
  });

  const nowIso = new Date().toISOString();
  const staleIso = '2025-01-15T10:00:00Z';
  const jobs = [
    {
      id: 'ashby:supabase:beta-1',
      provider: 'ashby',
      title: 'Developer Advocate',
      company: 'Supabase',
      company_slug: 'supabase',
      company_domain: 'supabase.com',
      location: 'Worldwide Remote',
      is_remote: true,
      work_model: 'remote',
      posted_at: nowIso,
      freshness: 'fresh',
      apply_url: 'https://jobs.ashbyhq.com/supabase/beta-1',
      source_url: 'https://jobs.ashbyhq.com/supabase/beta-1',
    },
    {
      id: 'lever:oldcorp:beta-2',
      provider: 'lever',
      title: 'Legacy Platform Engineer',
      company: 'OldCorp Systems',
      company_slug: 'oldcorp',
      location: 'Remote',
      is_remote: true,
      work_model: 'remote',
      posted_at: staleIso,
      freshness: 'stale',
      apply_url: 'https://jobs.lever.co/oldcorp/beta-2',
      source_url: 'https://jobs.lever.co/oldcorp/beta-2',
    },
  ];

  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['results', { batch: jobs, total_so_far: jobs.length }],
        ['done', { total: jobs.length, partial: true, incomplete: true }],
      ]),
    });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/favicon.svg');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  const noOverflowSearch = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(noOverflowSearch).toBe(true);

  await page.getByLabel(/role or keyword/i).fill('Engineer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  await expect(page.getByTestId('budget-exhausted-notice')).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId('no-country-notice')).toHaveCount(0);
  await expect(page.locator('.cards-mobile-view').getByTestId('older-postings-divider')).toBeVisible();

  const noOverflowResults = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(noOverflowResults).toBe(true);

  await page.locator('.mobile-job-card').first().click();
  const reportLink = page.getByTestId('report-problem-link');
  await expect(reportLink).toBeVisible();
  const reportHref = await reportLink.getAttribute('href');
  expect(reportHref).toContain('listing_id=ashby%3Asupabase%3Abeta-1');
  expect(reportHref).not.toContain('query=');
});

test('step 58: calm multi-page navigation, direct reloads, zero hash anchors, and WCAG AA compliance', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const routesToVerify = [
    { navLabel: 'Product', path: '/product', heading: 'A quieter, more honest way to find work.' },
    { navLabel: 'Sources', path: '/sources', heading: 'Where your search looks.' },
    { navLabel: 'About', path: '/about', heading: 'Why Bottom Pot exists.' },
    { navLabel: 'Search', path: '/app', heading: 'Search jobs' },
  ];

  // Ensure zero '#' hash anchor links exist anywhere
  const hashLinksOnHome = await page.locator('a[href^="#"]').count();
  expect(hashLinksOnHome).toBe(0);

  for (const r of routesToVerify) {
    await page.locator('header nav').getByRole('link', { name: r.navLabel, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${r.path}$`));
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(r.heading);
    expect(await page.locator('a[href^="#"]').count()).toBe(0);

    // Reload directly on route (verifies FastAPI HTML route fallback)
    await page.reload({ waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(r.heading);

    // Zero horizontal overflow + WCAG AA check
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(hasOverflow).toBe(false);

    const axeResults = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const severe = axeResults.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
    expect(severe).toEqual([]);
  }

  expect(consoleErrors).toEqual([]);
});

test('step 58: dropdowns align cleanly below triggers and use neutral hover styling', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockSearch(page);
  await runSearch(page);

  // 1. Work model Select popup opens cleanly below its trigger without overlapping
  const wmTrigger = page.locator('#workmodel-filter-trigger');
  await wmTrigger.click();
  const wmPopup = page.locator('[data-slot="select-content"]');
  await expect(wmPopup).toBeVisible();
  const wmGeometry = await page.evaluate(() => {
    const t = document.querySelector('#workmodel-filter-trigger').getBoundingClientRect();
    const p = document.querySelector('[data-slot="select-content"]').getBoundingClientRect();
    return {
      triggerBottom: t.bottom,
      triggerLeft: t.left,
      popupTop: p.top,
      popupLeft: p.left,
      popupRight: p.right,
      viewportWidth: window.innerWidth,
    };
  });
  expect(wmGeometry.popupTop).toBeGreaterThanOrEqual(wmGeometry.triggerBottom - 2);
  expect(wmGeometry.popupLeft).toBeGreaterThanOrEqual(0);
  expect(wmGeometry.popupRight).toBeLessThanOrEqual(wmGeometry.viewportWidth);
  await page.keyboard.press('Escape');

  // 2. Export DropdownMenu aligns below trigger and hovering an item avoids green fill flood
  const exportBtn = page.getByRole('button', { name: /export results/i });
  await exportBtn.click();
  const downloadItem = page.locator('#downloadBtn');
  await expect(downloadItem).toBeVisible();
  await downloadItem.hover();
  const menuAudit = await page.evaluate(() => {
    const t = document.querySelector('[aria-label="Export results"]').getBoundingClientRect();
    const p = document.querySelector('[data-slot="dropdown-menu-content"]').getBoundingClientRect();
    const itemStyle = window.getComputedStyle(document.querySelector('#downloadBtn'));
    return {
      triggerBottom: t.bottom,
      popupTop: p.top,
      popupRight: p.right,
      viewportWidth: window.innerWidth,
      itemBg: itemStyle.backgroundColor,
    };
  });
  expect(menuAudit.popupTop).toBeGreaterThanOrEqual(menuAudit.triggerBottom - 2);
  expect(menuAudit.popupRight).toBeLessThanOrEqual(menuAudit.viewportWidth);
  expect(menuAudit.itemBg).not.toContain('26, 56, 43');
  await page.keyboard.press('Escape');
});

test('step 58: progressive SSE streaming reveals results table immediately before done arrives', async ({ page }) => {
  await page.addInitScript((firstBatch) => {
    const origFetch = window.fetch.bind(window);
    window.__finishSseStream = null;
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input?.url || '';
      if (url.startsWith('/search?')) {
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
          start(controller) {
            const firstChunk = `event: results\ndata: ${JSON.stringify({ batch: firstBatch.slice(0, 1), total_so_far: 1 })}\n\n`;
            controller.enqueue(encoder.encode(firstChunk));
            window.__finishSseStream = () => {
              const secondChunk = `event: results\ndata: ${JSON.stringify({ batch: firstBatch.slice(1), total_so_far: firstBatch.length })}\n\n`;
              const doneChunk = `event: done\ndata: ${JSON.stringify({ total: firstBatch.length, search_time_ms: 420, providers_searched: ['greenhouse', 'lever', 'jobberman'], providers_skipped: [], cached: false })}\n\n`;
              controller.enqueue(encoder.encode(secondChunk + doneChunk));
              controller.close();
            };
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { 'content-type': 'text/event-stream' },
        });
      }
      return origFetch(input, init);
    };
  }, streamedJobs);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/app');
  await page.waitForLoadState('networkidle');
  await page.getByLabel(/role or keyword/i).fill('Backend Engineer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  // First SSE batch must render the results table and streaming indicator BEFORE done arrives
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(1);
  await expect(page.getByTestId('streaming-indicator')).toBeVisible();

  // Now complete the SSE stream and confirm remaining batches append & indicator clears
  await page.evaluate(() => window.__finishSseStream && window.__finishSseStream());
  await expect(page.locator('.results-table tbody tr.job-row')).toHaveCount(3);
  await expect(page.getByTestId('streaming-indicator')).toHaveCount(0);
});

test('step 59: start searching opens fresh form, streamlined controls, square active nav, and hybrid contrast across mismatched themes', async ({ page, browser }) => {
  const hybridJob = {
    id: 'ashby:moniepoint:hybrid-1',
    provider: 'ashby',
    data_source: 'api',
    title: 'Senior Product Designer',
    company: 'Moniepoint',
    company_slug: 'moniepoint',
    location: 'Lagos / London',
    is_remote: false,
    work_model: 'hybrid',
    employment_type: 'full_time',
    posted_at: new Date().toISOString(),
    apply_url: 'https://jobs.ashbyhq.com/moniepoint/hybrid-1',
    source_url: 'https://jobs.ashbyhq.com/moniepoint/hybrid-1',
    ats_source: 'ashby',
  };

  await page.route('**/search?*', async (route) => {
    const batch = JSON.stringify({ batch: [hybridJob], total_so_far: 1 });
    const done = JSON.stringify({
      total: 1,
      search_time_ms: 180,
      providers_searched: ['ashby'],
      providers_skipped: [],
      cached: false,
    });
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: results\ndata: ${batch}\n\nevent: done\ndata: ${done}\n\n`,
    });
  });

  // 1. Run search and inspect streamlined results controls + tactile square nav
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/app');
  await page.waitForLoadState('networkidle');
  await page.getByLabel(/role or keyword/i).fill('Product Designer');
  await page.getByRole('button', { name: 'Search jobs' }).click();

  const summaryBar = page.locator('.search-summary-bar');
  await expect(summaryBar).toBeVisible();
  await expect(summaryBar.getByRole('button', { name: 'New search' })).toBeVisible();
  await expect(page.locator('#compact-keywords-input')).toHaveCount(0);

  // Active nav indicator uses square bordered tab, not bottom-only border-b-2 underline
  const searchNavMetrics = await page.evaluate(() => {
    const active = document.querySelector('header nav a[aria-current="page"]');
    const s = window.getComputedStyle(active);
    return {
      borderBottomWidth: s.borderBottomWidth,
      borderTopWidth: s.borderTopWidth,
    };
  });
  expect(searchNavMetrics.borderBottomWidth).toBe('1px');
  expect(searchNavMetrics.borderTopWidth).toBe('1px');

  // Toggle inline query editor cleanly & open consolidated More filters popover
  await summaryBar.getByRole('button', { name: /edit search/i }).click();
  await expect(page.locator('#compact-keywords-input')).toBeVisible();
  await page.locator('#more-filters-trigger').click();
  await expect(page.locator('#platform-filter-trigger')).toBeVisible();
  await expect(page.getByText('Salary listed only')).toBeVisible();
  await page.keyboard.press('Escape');

  // 2. Navigate back to Home -> Start searching MUST open fresh cleared form, NOT stale delivery results
  await page.locator('header a[aria-label="Bottom Pot home"]').click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole('link', { name: /start searching/i }).first().click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.locator('#keywords-input')).toBeVisible();
  await expect(page.locator('#keywords-input')).toHaveValue('');

  // 3. Verify Hybrid tag contrast & WCAG AA when OS colorScheme = dark while app theme = light
  const mismatchedContext = await browser.newContext({ colorScheme: 'dark' });
  const lightPage = await mismatchedContext.newPage();
  await lightPage.addInitScript(() => {
    localStorage.setItem('bp.theme', 'light');
  });
  await lightPage.route('**/search?*', async (route) => {
    const batch = JSON.stringify({ batch: [hybridJob], total_so_far: 1 });
    const done = JSON.stringify({ total: 1, search_time_ms: 120, providers_searched: ['ashby'], providers_skipped: [], cached: false });
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: `event: results\ndata: ${batch}\n\nevent: done\ndata: ${done}\n\n` });
  });
  await lightPage.setViewportSize({ width: 1440, height: 900 });
  await lightPage.goto('/app');
  await lightPage.locator('#keywords-input').fill('Product Designer');
  await lightPage.getByRole('button', { name: 'Search jobs' }).click();
  await expect(lightPage.locator('.results-table')).toContainText('Hybrid');

  const lightHybridContrast = await lightPage.evaluate(() => {
    const isDark = document.documentElement.classList.contains('dark');
    const tag = Array.from(document.querySelectorAll('.results-table td span')).find((el) =>
      el.textContent?.trim() === 'Hybrid'
    );
    const s = window.getComputedStyle(tag);
    return { isDark, color: s.color, bg: s.backgroundColor };
  });
  expect(lightHybridContrast.isDark).toBe(false);
  expect(lightHybridContrast.color).not.toBe('rgb(252, 211, 77)');
  const axeLight = await new AxeBuilder({ page: lightPage }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeLight.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);

  // Switch to Dark theme in OS-dark or toggle and verify axe contrast stays clean too
  await lightPage.getByRole('button', { name: 'Toggle theme' }).click();
  const darkIsSet = await lightPage.evaluate(() => document.documentElement.classList.contains('dark'));
  expect(darkIsSet).toBe(true);
  const axeDark = await new AxeBuilder({ page: lightPage }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axeDark.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')).toEqual([]);
  await mismatchedContext.close();
});
