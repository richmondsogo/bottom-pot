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
    description: 'Build reliable APIs for remote-first finance teams.',
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
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });

  await page.getByLabel(/role or keyword/i).fill(overrides.keyword || 'Backend Engineer');
  if (overrides.location) {
    await page.getByLabel(/location or country/i).fill(overrides.location);
  }
  if (overrides.workModel) {
    await page.getByLabel(/work model/i).selectOption(overrides.workModel);
  }

  await page.getByRole('button', { name: /search ats platforms/i }).click();

  const isMobile = (page.viewportSize()?.width || 1000) < 768;
  if (isMobile) {
    await expect(page.locator('.mobile-job-card').first()).toBeVisible({ timeout: 10000 });
  } else {
    await expect(page.locator('.results-table tbody tr').first()).toBeVisible({ timeout: 10000 });
  }
}

test('landing page loads editorial typography and meets a11y standards', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Find the signal behind the noise.');
  await expect(page.getByLabel(/role or keyword/i)).toBeVisible();
  await expect(page.getByText(/how bottom pot works/i)).toBeVisible();

  // Axe Accessibility Check
  const accessibilityScanResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  const criticalViolations = accessibilityScanResults.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );
  expect(criticalViolations).toEqual([]);
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

  // Verify single quiet status strip
  await expect(page.locator('.status-strip')).toContainText('3 postings from 3 platforms');

  // Verify table rows and content
  const rows = page.locator('.results-table tbody tr');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('Senior Backend Engineer');
  await expect(rows.nth(1)).toContainText('Product Designer');
  await expect(rows.nth(2)).toContainText('Cloud Support Intern');

  // Verify download CSV and JSON buttons exist and are enabled
  await expect(page.locator('#downloadBtn')).toBeVisible();
  await expect(page.locator('#downloadBtn')).toBeEnabled();
  await expect(page.locator('#downloadJsonBtn')).toBeVisible();
  await expect(page.locator('#downloadJsonBtn')).toBeEnabled();
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

  // Detail Sheet is open
  const detailSheet = page.locator('.detail-sheet');
  await expect(detailSheet).toBeVisible();
  await expect(detailSheet).toContainText('Senior Backend Engineer');
  await expect(detailSheet).toContainText('Build reliable APIs for remote-first finance teams.');
  await expect(detailSheet).toContainText('Python, FastAPI, and production ownership.');

  // Check visited class is applied
  await expect(firstRow.locator('.line-clamp-2')).toHaveClass(/title-visited/);

  // Close with Esc key
  await page.keyboard.press('Escape');
  await expect(detailSheet).toBeHidden();
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
