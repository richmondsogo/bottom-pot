const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
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
        ['results', { batch: [], total_so_far: 0 }],
        [
          'done',
          {
            total: 0,
            search_time_ms: 50,
            serper_queries_used: 1,
            providers_searched: ['greenhouse'],
            providers_skipped: [],
            cached: false,
          },
        ],
      ]),
    });
  });
}

test.describe('Admin Authentication & Route Separation', () => {
  test.beforeEach(async ({ context, page }) => {
    // Clean cookies and localStorage before every test
    await context.clearCookies();
    await page.goto('/favicon.svg');
    await page.evaluate(() => localStorage.clear());
  });

  test('anonymous /admin shows login screen and does NOT request /search', async ({ page }) => {
    let searchRequested = false;
    page.on('request', (req) => {
      try {
        const url = new URL(req.url());
        if (url.pathname === '/search') {
          searchRequested = true;
        }
      } catch {
        // Ignore malformed URLs
      }
    });

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    // Confirm login card is rendered
    const passwordInput = page.locator('#admin-password');
    await expect(passwordInput).toBeVisible();
    await expect(page.getByRole('button', { name: /access admin workspace/i })).toBeVisible();

    // Confirm /search was NEVER requested while anonymous
    expect(searchRequested).toBe(false);
  });

  test('query params are preserved on /admin through login', async ({ page }) => {
    await mockSearch(page);
    await page.goto('/admin?q=Golang&loc=Lagos');
    await page.waitForLoadState('networkidle');

    // Confirm URL still contains query parameters on the login screen
    expect(page.url()).toContain('q=Golang');
    expect(page.url()).toContain('loc=Lagos');

    // Fill password and login
    await page.fill('#admin-password', 'test-admin-password');
    await page.click('button[type="submit"]');

    // Workspace mounts; auto-search runs with mock and completes to delivery
    await expect(page.getByRole('button', { name: /log out/i })).toBeVisible();
    await expect(page.getByTitle('Administrator Workspace')).toBeVisible();

    // Delivery screen shows the active search keyword
    await expect(page.getByText(/Golang/i).first()).toBeVisible();

    // Click "Edit search" to inspect the search form input
    const editSearchBtn = page.getByRole('button', { name: /edit search/i });
    await expect(editSearchBtn).toBeVisible();
    await editSearchBtn.click();

    const searchInput = page.locator('#keywords-input');
    await expect(searchInput).toHaveValue('Golang');
  });

  test('wrong password shows alert message and remains on login screen', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    await page.fill('#admin-password', 'wrong-password');
    await page.click('button[type="submit"]');

    const alert = page.locator('div[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Incorrect admin password.');
    await expect(page.locator('#admin-password')).toBeVisible();
  });

  test('correct password logs in, displays ADMIN badge in header, and allows logout', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    await page.fill('#admin-password', 'test-admin-password');
    await page.click('button[type="submit"]');

    // Header has ADMIN badge and Log out button
    await expect(page.getByTitle('Administrator Workspace')).toBeVisible();
    const logoutBtn = page.getByRole('button', { name: /log out/i });
    await expect(logoutBtn).toBeVisible();

    // Click logout
    await logoutBtn.click();

    // Returns to login screen and clears cookie
    await expect(page.locator('#admin-password')).toBeVisible();
    await expect(page.getByTitle('Administrator Workspace')).toHaveCount(0);
  });

  test('/app and / never request /api/admin/verify', async ({ page }) => {
    let verifyRequested = false;
    page.on('request', (req) => {
      try {
        const url = new URL(req.url());
        if (url.pathname === '/api/admin/verify') {
          verifyRequested = true;
        }
      } catch {}
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    expect(verifyRequested).toBe(false);

    await page.goto('/app');
    await page.waitForLoadState('networkidle');
    expect(verifyRequested).toBe(false);
  });

  test('/admin -> Overview -> Start searching lands on /app in user mode with no ADMIN badge', async ({ page }) => {
    // Login to /admin
    await page.goto('/admin');
    await page.fill('#admin-password', 'test-admin-password');
    await page.click('button[type="submit"]');
    await expect(page.getByTitle('Administrator Workspace')).toBeVisible();

    // Click "← Overview"
    const overviewLink = page.getByRole('button', { name: '← Overview' });
    await expect(overviewLink).toBeVisible();
    await overviewLink.click();

    // Lands on marketing landing (/)
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/');

    let verifyAfterLandingCount = 0;
    page.on('request', (req) => {
      try {
        if (new URL(req.url()).pathname === '/api/admin/verify') {
          verifyAfterLandingCount++;
        }
      } catch {}
    });

    // Click "Start searching"
    const startSearchingBtn = page.getByRole('button', { name: /start searching/i }).first();
    await startSearchingBtn.click();
    await page.waitForLoadState('networkidle');

    // Confirm landed on /app
    expect(new URL(page.url()).pathname).toBe('/app');

    // In user mode: no ADMIN badge, no Log out button
    await expect(page.getByTitle('Administrator Workspace')).toHaveCount(0);
    await expect(page.getByRole('button', { name: /log out/i })).toHaveCount(0);

    // No admin verify calls made after landing on /app
    expect(verifyAfterLandingCount).toBe(0);
  });

  test('Back twice returns to /admin and triggers exactly one verify', async ({ page }) => {
    // 1. Login to /admin
    await page.goto('/admin');
    await page.fill('#admin-password', 'test-admin-password');
    await page.click('button[type="submit"]');
    await expect(page.getByTitle('Administrator Workspace')).toBeVisible();

    // 2. Click "← Overview" to navigate to /
    const overviewLink = page.getByRole('button', { name: '← Overview' });
    await expect(overviewLink).toBeVisible();
    await overviewLink.click();
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/');

    // 3. Click "Start searching" to land on /app
    const startSearchingBtn = page.getByRole('button', { name: /start searching/i }).first();
    await startSearchingBtn.click();
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/app');

    // 4. Press Back twice to return to /admin
    await page.goBack(); // Back to /
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/');

    let backVerifyCount = 0;
    page.on('request', (req) => {
      try {
        if (new URL(req.url()).pathname === '/api/admin/verify') {
          backVerifyCount++;
        }
      } catch {}
    });

    const verifyPromise = page.waitForRequest(
      (req) => new URL(req.url()).pathname === '/api/admin/verify'
    );
    await page.goBack(); // Back to /admin
    await verifyPromise;
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/admin');

    // Assert: exactly one verify call was triggered, and admin workspace is restored
    expect(backVerifyCount).toBe(1);
    await expect(page.getByTitle('Administrator Workspace')).toBeVisible();
  });

  test('with an expired or invalid cookie set before load, /admin shows the login, and after Overview then Back it still shows the login', async ({ page, context }) => {
    // Set invalid/garbage admin session cookie
    await context.addCookies([
      {
        name: 'bp_admin_session',
        value: 'garbage_expired_or_invalid_session_token',
        domain: '127.0.0.1',
        path: '/',
        httpOnly: true,
      },
    ]);

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    // /admin shows the login (not the workspace)
    await expect(page.locator('#admin-password')).toBeVisible();
    await expect(page.getByTitle('Administrator Workspace')).toHaveCount(0);

    // Navigate to Overview (/)
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/');

    // Back to /admin
    await page.goBack();
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname).toBe('/admin');

    // Still shows the login screen (not workspace)
    await expect(page.locator('#admin-password')).toBeVisible();
    await expect(page.getByTitle('Administrator Workspace')).toHaveCount(0);
  });

  test('keyboard shortcuts guard: typing in password field does not trigger single-key shortcuts', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    const passwordInput = page.locator('#admin-password');
    await passwordInput.focus();

    // Type shortcut keys: j, k, /, s, ?, o
    await page.keyboard.type('jk/s?o');

    // Input value must be exactly "jk/s?o"
    expect(await passwordInput.inputValue()).toBe('jk/s?o');

    // Shortcuts modal must not be opened
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });

  test('green budget audit: enforces strict green usage on login screen', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    const greenElementsOnLogin = await page.evaluate(() => {
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

    // Strictly budgeted: only the BP icon badge uses green accent (<= 2 elements)
    expect(greenElementsOnLogin).toBeLessThanOrEqual(2);
  });

  test('accessibility and horizontal overflow audit on /admin login across 5 viewports', async ({ page }) => {
    for (const vp of VIEWPORTS) {
      await page.setViewportSize(vp);
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Axe WCAG 2.0 A & AA check
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );
      expect(criticalViolations).toEqual([]);

      // Horizontal overflow check
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasHorizontalScroll).toBe(false);
    }
  });
});
