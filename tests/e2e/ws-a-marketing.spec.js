const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const path = require('path');

const SCREENSHOT_DIR =
  'C:/Users/Richmond/.gemini/antigravity-cli/brain/422c453b-569d-47cc-b3f0-d00acc3877f2/scratch';

test.describe('WS-A Marketing Pages, Footer, Contact, and Analytics Guard', () => {
  test('never loads Vercel Analytics script or fires /_vercel/insights requests in Playwright', async ({
    page,
  }) => {
    const analyticsRequests = [];
    page.on('request', (req) => {
      if (req.url().includes('/_vercel/insights') || req.url().includes('va.vercel-scripts.com')) {
        analyticsRequests.push(req.url());
      }
    });

    for (const targetUrl of ['/', '/about', '/app?mock=1']) {
      await page.goto(targetUrl);
      await page.waitForLoadState('networkidle');
    }

    expect(analyticsRequests).toEqual([]);
  });

  test('About page renders keyboard-accessible Rules and FAQ accordions with neutral ink icons and zero green accent on icons', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/about');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Five rules we stick to' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Frequently asked questions' })).toBeVisible();

    const countryTrigger = page.getByRole('button', { name: /Clear country rules/i });
    await expect(countryTrigger).toHaveAttribute('aria-expanded', 'false');

    // Keyboard activation with Enter
    await countryTrigger.focus();
    await page.keyboard.press('Enter');
    await expect(countryTrigger).toHaveAttribute('aria-expanded', 'true');
    await expect(
      page.getByText(/Nigerian job boards are treated as workable from Nigeria/i)
    ).toBeVisible();

    // Neutral ink icon check (never green)
    const iconColor = await countryTrigger.locator('svg').first().evaluate((el) => {
      return getComputedStyle(el).color;
    });
    expect(iconColor).not.toBe('rgb(26, 56, 43)');
    expect(iconColor).not.toBe('rgb(46, 125, 82)');

    // FAQ accordion expansion
    const faqTrigger = page.getByRole('button', { name: /How fresh are the results\?/i });
    await faqTrigger.click();
    await expect(faqTrigger).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByText(/30-minute schedule/i)).toBeVisible();

    // Accessibility check in light mode
    const lightAxe = await new AxeBuilder({ page }).analyze();
    const lightSerious = lightAxe.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || '')
    );
    expect(lightSerious).toEqual([]);

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'about-desktop-light.png'),
      fullPage: true,
    });

    // Switch to dark mode and verify axe + screenshot
    await page.getByRole('button', { name: 'Toggle theme' }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    const darkAxe = await new AxeBuilder({ page }).analyze();
    const darkSerious = darkAxe.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || '')
    );
    expect(darkSerious).toEqual([]);

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'about-desktop-dark.png'),
      fullPage: true,
    });
  });

  test('Footer navigation reaches /contact, renders FooterFlickeringGrid quietly, and passes 390px and 360px mobile checks in light + dark', async ({
    page,
  }) => {
    for (const width of [390, 360]) {
      for (const theme of ['light', 'dark']) {
        await page.setViewportSize({ width, height: 844 });
        await page.goto('/favicon.svg');
        await page.evaluate((t) => {
          localStorage.setItem('bp.theme', t);
        }, theme);

        await page.goto('/about');
        await page.waitForLoadState('networkidle');

        // Zero horizontal overflow on /about
        const aboutOverflow = await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth
        );
        expect(aboutOverflow).toBe(true);

        const footer = page.locator('footer');
        await expect(footer).toBeVisible();
        await expect(footer.getByText('© 2026 Bottom Pot')).toBeVisible();
        await expect(footer.getByText('Logos provided by Logo.dev')).toBeVisible();
        await expect(footer.getByText('Scraped from the bottom of the pot.')).toBeVisible();

        const grid = footer.getByTestId('footer-flickering-grid');
        await expect(grid).toHaveAttribute('aria-hidden', 'true');
        const gridStyles = await grid.evaluate((el) => {
          const style = getComputedStyle(el);
          return {
            pointerEvents: style.pointerEvents,
            position: style.position,
          };
        });
        expect(gridStyles.pointerEvents).toBe('none');
        expect(gridStyles.position).toBe('absolute');

        // Tap target check >= 44x44px for all footer links & buttons on mobile
        const footerTargets = footer.locator('a, button');
        const targetCount = await footerTargets.count();
        expect(targetCount).toBeGreaterThanOrEqual(7);
        for (let i = 0; i < targetCount; i++) {
          const box = await footerTargets.nth(i).boundingBox();
          expect(box).not.toBeNull();
          expect(box.height).toBeGreaterThanOrEqual(44);
          expect(box.width).toBeGreaterThanOrEqual(44);
        }

        // Navigate to /contact via Footer link
        await footer.getByRole('link', { name: 'Contact' }).click();
        await expect(page).toHaveURL(/\/contact$/);
        await expect(page.getByRole('heading', { name: 'Get in touch.' })).toBeVisible();
        await expect(
          page.getByRole('link', { name: /Open an issue on GitHub/i })
        ).toHaveAttribute('href', 'https://github.com/richmondsogo/bottom-pot/issues/new');
        await expect(page.locator('form')).toHaveCount(0);

        const contactOverflow = await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth
        );
        expect(contactOverflow).toBe(true);

        if (width === 390) {
          await page.screenshot({
            path: path.join(SCREENSHOT_DIR, `contact-mobile-${theme}.png`),
            fullPage: true,
          });
        }
      }
    }

    // Desktop screenshot of Contact + Footer in light mode
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/favicon.svg');
    await page.evaluate(() => localStorage.setItem('bp.theme', 'light'));
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('footer').getByRole('link', { name: 'Contact' }).click();
    await expect(page).toHaveURL(/\/contact$/);
    await expect(page.getByRole('heading', { name: 'Get in touch.' })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'contact-footer-desktop-light.png'),
      fullPage: true,
    });
  });
});
