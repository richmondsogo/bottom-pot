const { chromium } = require('@playwright/test');
const path = require('path');

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
    work_model_source: 'api',
    work_model_evidence: 'remote=true',
    raw_workplace_type: 'remote',
    department: 'Engineering',
    salary: { minimum: 120000, maximum: 150000, currency: 'USD', period: 'year' },
    description: 'Build reliable distributed systems and APIs for global finance teams.',
    requirements: 'Python, FastAPI, PostgreSQL, and high-scale system design.',
    posted_at: '2026-09-10T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/acme/backend-engineer',
    source_url: 'https://boards.greenhouse.io/acme/jobs/1',
    query_used: 'backend engineer',
    ats_source: 'greenhouse',
    description_ok: true,
  },
  {
    id: 'lever:orbit:2',
    provider: 'lever',
    data_source: 'api',
    title: 'Lead Product Designer',
    company: 'Orbit Works',
    company_slug: 'orbit',
    location: 'London, UK',
    is_remote: false,
    employment_type: 'contract',
    work_model: 'in_person',
    work_model_source: 'page_label',
    work_model_evidence: 'On-site London office',
    raw_workplace_type: 'on-site',
    department: 'Design',
    posted_at: '2026-09-08T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/orbit/product-designer',
    source_url: 'https://jobs.lever.co/orbit/2',
    query_used: 'backend engineer',
    ats_source: 'lever',
    description_ok: true,
  },
  {
    id: 'jobberman:cloud:3',
    provider: 'jobberman',
    data_source: 'scrape',
    title: 'Cloud Infrastructure Intern',
    company: 'Cloud Nine Tech',
    company_slug: 'cloud-nine',
    location: 'Abuja, Nigeria',
    is_remote: null,
    employment_type: 'internship',
    work_model: 'hybrid',
    work_model_source: 'description',
    work_model_evidence: 'hybrid 2 days office',
    raw_workplace_type: 'hybrid',
    salary: 'NGN 350,000 / month',
    description: 'Support core AWS cloud services while learning operations.',
    requirements: 'Basic Linux, Git, and curiosity.',
    posted_at: '2026-09-12T09:00:00Z',
    scraped_at: '2026-09-13T09:00:00Z',
    apply_url: 'https://jobs.example.test/cloud/support-intern',
    source_url: 'https://www.jobberman.com/listings/cloud-support-intern',
    query_used: 'backend engineer',
    ats_source: 'jobberman',
    description_ok: true,
  },
];

function sse(events) {
  return events.map(([eventName, payload]) => `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`).join('');
}

async function main() {
  const browser = await chromium.launch();
  const artifactDir = 'C:/Users/Richmond/.gemini/antigravity-ide/brain/217a02c1-91e5-4585-9750-078934da9928';

  const viewports = [
    { width: 1440, height: 900, name: 'screenshot_1440px.png' },
    { width: 1920, height: 1080, name: 'screenshot_1920px.png' },
    { width: 390, height: 844, name: 'screenshot_390px.png' },
  ];

  for (const vp of viewports) {
    const page = await browser.newPage({
      viewport: { width: vp.width, height: vp.height },
    });

    await page.route('**/search?**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([
          ['results', { batch: streamedJobs, total_so_far: 3 }],
          ['done', {
            total: 3,
            search_time_ms: 640,
            serper_queries_used: 3,
            serper_calls: 3,
            serper_cache_hits: 1,
            pages_fetched: 5,
            providers_searched: ['greenhouse', 'lever', 'jobberman'],
            providers_skipped: [],
            cached: false,
            dropped_count: { '404_expired': 1 },
          }],
        ]),
      });
    });

    await page.goto('http://127.0.0.1:8000/');
    await page.getByLabel('Role or keyword *').fill('Backend Engineer');
    await page.getByRole('button', { name: /search ats platforms/i }).click();

    await page.waitForSelector('#resultsBody tr');

    // Toggle quick filter chips on (Salary Disclosed and Remote Only)
    const salaryChip = page.getByRole('button', { name: 'Salary Disclosed' });
    await salaryChip.click();
    const remoteChip = page.getByRole('button', { name: 'Remote Only' });
    await remoteChip.click();
    await page.waitForTimeout(100);

    // Open details panel for first row
    const firstRow = page.locator('#resultsBody tr').first();
    await firstRow.getByRole('button', { name: 'Details' }).click();
    await page.waitForSelector('article.job-detail-panel');
    await page.waitForTimeout(200);

    // Check horizontal scroll on document / page
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    const hasHorizontalPageScroll = scrollWidth > clientWidth;
    console.log(`Viewport ${vp.width}px: scrollWidth=${scrollWidth}, clientWidth=${clientWidth}, pageOverflow=${hasHorizontalPageScroll}`);

    // Scroll to top so position:sticky header is captured at y=0 without obscuring content below
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);

    const outPath = path.join(artifactDir, vp.name);
    await page.screenshot({ path: outPath, fullPage: true });
    console.log(`Saved screenshot: ${outPath}`);

    await page.close();
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
