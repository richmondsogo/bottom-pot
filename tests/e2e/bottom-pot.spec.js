const { test, expect } = require('@playwright/test');

const streamedJobs = [
  {
    id: 'greenhouse:acme:1',
    provider: 'greenhouse',
    data_source: 'api',
    title: 'Backend Engineer',
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
    posted_at: null,
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/cloud/support-intern',
    source_url: 'https://www.jobberman.com/listings/cloud-support-intern',
    query_used: 'backend engineer',
    ats_source: 'jobberman',
  },
];

function sse(events) {
  return events.map(([eventName, payload]) => (
    `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`
  )).join('');
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
        ['done', {
          total: 3,
          search_time_ms: 812,
          serper_queries_used: 4,
          providers_searched: ['greenhouse', 'lever', 'jobberman'],
          providers_skipped: [],
          cached: false,
        }],
      ]),
    });
  });
}

async function runSearch(page, overrides = {}) {
  await page.goto('/');
  await page.getByLabel('Role or keyword *').fill(overrides.keyword || 'Backend Engineer');
  await page.getByLabel('Location').fill(overrides.location || 'Nigeria');
  await page.getByLabel('Work model').selectOption(overrides.workModel || 'remote');
  await page.getByLabel('Posted within').selectOption(overrides.days || '14');
  if (overrides.includeNigerian === false) {
    await page.getByLabel('Include Nigerian job boards').uncheck();
  }
  if (overrides.deepScrape) {
    await page.getByLabel('Deep scrape matched job pages').check();
  }
  await page.getByRole('button', { name: /search ats platforms/i }).click();
  await expect(page.getByText('Search complete')).toBeVisible();
}

test('search sends the user-selected parameters and renders streamed job results', async ({ page }) => {
  let searchUrl;
  await mockSearch(page, { onRequest: (url) => { searchUrl = url; } });

  await runSearch(page, { deepScrape: true });

  expect(searchUrl.searchParams.get('q')).toBe('Backend Engineer');
  expect(searchUrl.searchParams.get('location')).toBe('Nigeria');
  expect(searchUrl.searchParams.get('remote')).toBe('true');
  expect(searchUrl.searchParams.get('days_back')).toBe('14');
  expect(searchUrl.searchParams.get('include_nigerian')).toBe('true');
  expect(searchUrl.searchParams.get('deep_scrape')).toBe('true');

  await expect(page.locator('#filterSummary')).toHaveText('3 results');
  await expect(page.locator('#metrics')).toContainText('3');
  await expect(page.locator('#metrics')).toContainText('812 ms');
  await expect(page.locator('#resultsBody')).toContainText('Backend Engineer');
  await expect(page.locator('#resultsBody')).toContainText('Product Designer');
  await expect(page.locator('#resultsBody')).toContainText('Cloud Support Intern');
});

test('filters narrow results by keyword, provider, remote status, and employment type', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  await page.getByLabel('Filter results').fill('designer');
  await expect(page.locator('#filterSummary')).toHaveText('Showing 1 of 3 results');
  await expect(page.locator('#resultsBody')).toContainText('Product Designer');
  await expect(page.locator('#resultsBody')).not.toContainText('Backend Engineer');

  await page.getByRole('button', { name: /clear filters/i }).click();
  await page.getByLabel('Provider').selectOption('jobberman');
  await page.getByLabel('Work model').selectOption('onsite');
  await page.getByLabel('Job type').selectOption('Internship');
  await expect(page.locator('#filterSummary')).toHaveText('Showing 1 of 3 results');
  await expect(page.locator('#resultsBody')).toContainText('Cloud Support Intern');
  await expect(page.locator('#resultsBody')).not.toContainText('Backend Engineer');
});

test('job details reveal source, description, requirements, and salary context', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  const backendRow = page.locator('#resultsBody tr', { hasText: 'Backend Engineer' }).first();
  await backendRow.getByRole('button', { name: 'Details' }).click();

  const detail = page.getByLabel('Backend Engineer details');
  await expect(detail).toContainText('Build reliable APIs for remote-first finance teams.');
  await expect(detail).toContainText('Python, FastAPI, and production ownership.');
  await expect(detail).toContainText('USD 120,000-150,000 / year');
  await expect(detail).toContainText('greenhouse - api');

  await backendRow.getByRole('button', { name: 'Hide details' }).click();
  await expect(detail).toBeHidden();
});

test('remote status and salary display use normalized values rather than raw codes', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  await expect(page.locator('#resultsBody tr', { hasText: 'Backend Engineer' }).first())
    .toContainText('Remote');
  await expect(page.locator('#resultsBody tr', { hasText: 'Backend Engineer' }).first())
    .toContainText('USD 120,000-150,000 / year');
  await expect(page.locator('#resultsBody tr', { hasText: 'Product Designer' }).first())
    .toContainText('In-person');
  await expect(page.locator('#resultsBody tr', { hasText: 'Product Designer' }).first())
    .toContainText('Not listed');
  await expect(page.locator('#resultsBody tr', { hasText: 'Cloud Support Intern' }).first())
    .toContainText('Hybrid');
  await expect(page.locator('#resultsBody tr', { hasText: 'Cloud Support Intern' }).first())
    .toContainText('NGN 250,000 / month');
});

test('application link opens the selected job application URL', async ({ page, context }) => {
  await mockSearch(page);
  await context.route('https://jobs.example.test/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Apply</title>' });
  });
  await runSearch(page);

  const backendRow = page.locator('#resultsBody tr', { hasText: 'Backend Engineer' }).first();
  const popupPromise = page.waitForEvent('popup');
  await backendRow.getByRole('link', { name: /apply/i }).click();
  const popup = await popupPromise;

  await expect(popup).toHaveURL('https://jobs.example.test/acme/backend-engineer');
});

test('keyboard navigation operates active row highlight, toggles details with Enter, closes with Esc, and focuses filter with /', async ({ page }) => {
  await mockSearch(page);
  await runSearch(page);

  // Press / to focus table search
  await page.keyboard.press('/');
  await expect(page.locator('#tableSearch')).toBeFocused();

  // Blur search and use j / k navigation
  await page.locator('#tableSearch').blur();
  await page.keyboard.press('j');
  const rows = page.locator('#resultsBody tr:not(.detail-row)');
  await expect(rows.nth(0)).toHaveClass(/row-active/);

  await page.keyboard.press('j');
  await expect(rows.nth(1)).toHaveClass(/row-active/);

  await page.keyboard.press('k');
  await expect(rows.nth(0)).toHaveClass(/row-active/);

  // Enter toggles details
  await page.keyboard.press('Enter');
  const detail = page.getByLabel('Backend Engineer details');
  await expect(detail).toBeVisible();

  // Esc closes details
  await page.keyboard.press('Escape');
  await expect(detail).toBeHidden();
});

test('persistence restores search params, filters, density, and saved results with restore banner', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('bp.density', JSON.stringify('compact'));
    localStorage.setItem('bp.searchParams', JSON.stringify({
      keywords: 'Staff Engineer',
      location: 'Lagos',
      workModel: 'remote',
      postAge: '14',
      includeNigerian: true,
      deepScrape: false,
    }));
    localStorage.setItem('bp.savedResults', JSON.stringify({
      rawResults: [{
        id: 'greenhouse:test:10',
        provider: 'greenhouse',
        data_source: 'api',
        title: 'Staff Platform Engineer',
        company: 'Stripe',
        location: 'Remote, Nigeria',
        work_model: 'remote',
        apply_url: 'https://example.com/apply',
        source_url: 'https://example.com/job',
      }],
      metrics: {
        total: 1,
        search_time_ms: 450,
        providers_searched: ['greenhouse'],
        cached: true,
      },
      extractionSummary: 'Loaded from recent search cache.',
      savedAt: Date.now() - 14 * 60 * 1000, // 14 min ago
    }));
  });

  await page.goto('/');

  // Banner should appear
  const banner = page.locator('.saved-results-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('Showing saved results from 14m ago');
  await expect(banner).toContainText('Run search again');
  await expect(banner).toContainText('Clear saved results');

  // Result row should be rendered
  await expect(page.locator('#resultsBody')).toContainText('Staff Platform Engineer');
  await expect(page.locator('#densityToggleBtn')).toContainText('Compact');

  // Clicking Clear saved results resets to form
  await banner.getByRole('button', { name: 'Clear saved results' }).click();
  await expect(banner).toBeHidden();
  await expect(page.locator('#queryForm')).toBeVisible();
});

test('skeleton loading rows show while search stream is active with no results yet', async ({ page }) => {
  await page.route('**/search?**', async () => {
    // Hang request to keep stream open without results
  });

  await page.goto('/');
  await page.getByLabel('Role or keyword *').fill('DevOps');
  await page.getByRole('button', { name: /search ats platforms/i }).click();

  await expect(page.locator('#processingScreen')).toBeVisible();
  const skeletonRows = page.locator('#processingScreen .skeleton-row');
  await expect(skeletonRows).toHaveCount(6);
});

test('budget exhausted banner is displayed when done event signals budget_exhausted', async ({ page }) => {
  await page.route('**/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: sse([
        ['done', {
          total: 0,
          search_time_ms: 120,
          serper_queries_used: 0,
          providers_searched: [],
          providers_skipped: [],
          cached: false,
          budget_exhausted: true,
          message: 'Serper daily budget limit (200) exceeded. Returning cached results.',
        }],
      ]),
    });
  });

  await page.goto('/');
  await page.getByLabel('Role or keyword *').fill('DevOps');
  await page.getByRole('button', { name: /search ats platforms/i }).click();

  const budgetBanner = page.locator('.budget-banner');
  await expect(budgetBanner).toBeVisible();
  await expect(budgetBanner).toContainText('Serper daily budget limit (200) exceeded.');
});

