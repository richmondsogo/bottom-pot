const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

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

    for (const targetUrl of ['/', '/about', '/privacy', '/terms', '/app?mock=1']) {
      await page.goto(targetUrl);
      await page.waitForLoadState('networkidle');
    }

    expect(analyticsRequests).toEqual([]);
  });

  test('About page renders keyboard-accessible Rules and FAQ accordions with neutral ink icons and zero green accent on icons', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/about');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'What we build around' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Frequently asked questions' })).toBeVisible();

    const countryTrigger = page.getByRole('button', { name: /Clarity before the application/i });
    await expect(countryTrigger).toHaveAttribute('aria-expanded', 'false');

    // Keyboard activation with Enter
    await countryTrigger.focus();
    await page.keyboard.press('Enter');
    await expect(countryTrigger).toHaveAttribute('aria-expanded', 'true');
    await expect(
      page.getByText(/Work arrangement and country eligibility are different questions/i)
    ).toBeVisible();

    // Neutral ink icon check (never green)
    const iconColor = await countryTrigger.locator('svg').first().evaluate((el) => {
      return getComputedStyle(el).color;
    });
    expect(iconColor).not.toBe('rgb(26, 56, 43)');
    expect(iconColor).not.toBe('rgb(46, 125, 82)');

    // FAQ accordion expansion
    const faqTrigger = page.getByRole('button', { name: /How current are the listings\?/i });
    await faqTrigger.click();
    await expect(faqTrigger).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByText(/Source update methods and timing vary/i)).toBeVisible();

    // Accessibility check in light mode
    const lightAxe = await new AxeBuilder({ page }).analyze();
    const lightSerious = lightAxe.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || '')
    );
    expect(lightSerious).toEqual([]);

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath('about-desktop-light.png'),
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
      path: testInfo.outputPath('about-desktop-dark.png'),
      fullPage: true,
    });
  });

  test('Footer navigation reaches /contact, renders FooterFlickeringGrid quietly, and passes 390px and 360px mobile checks in light + dark', async ({
    page,
  }, testInfo) => {
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
        await expect(footer.locator('a[href*="github"]')).toHaveCount(0);
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
          page.getByTestId('contact-direct-email').getByRole('link', { name: 'Send an email' })
        ).toHaveAttribute('href', 'mailto:richmondsogo@gmail.com');
        await expect(page.getByTestId('contact-direct-email')).toContainText('richmondsogo@gmail.com');
        await expect(page.locator('a[href*="github"]')).toHaveCount(0);
        await expect(page.locator('form')).toHaveCount(0);

        const contactOverflow = await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth
        );
        expect(contactOverflow).toBe(true);

        if (width === 390) {
          await page.screenshot({
            path: testInfo.outputPath(`contact-mobile-${theme}.png`),
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
      path: testInfo.outputPath('contact-footer-desktop-light.png'),
      fullPage: true,
    });
  });

  test('Privacy and Terms pages render plain copy without forms/em-dashes, pass axe light+dark, resolve from Footer, and keep >=44px mobile targets', async ({
    page,
  }) => {
    const routes = [
      { linkName: 'Privacy', path: '/privacy', heading: 'Privacy Policy' },
      { linkName: 'Terms', path: '/terms', heading: 'Terms of Service' },
    ];

    // Desktop navigation from Footer + axe light & dark
    for (const item of routes) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto('/favicon.svg');
      await page.evaluate(() => localStorage.setItem('bp.theme', 'light'));
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('footer').getByRole('link', { name: item.linkName, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${item.path}$`));
      await expect(page.getByRole('heading', { level: 1, name: item.heading })).toBeVisible();
      await expect(page.getByText(/Last updated:/i)).toBeVisible();
      await expect(page.getByRole('heading', { name: 'In plain words' })).toBeVisible();
      await expect(page.locator('form')).toHaveCount(0);
      await expect(page.locator('a[href*="github"]')).toHaveCount(0);
      const mainText = await page.locator('main').innerText();
      expect(mainText).not.toContain('\u2014');

      const lightAxe = await new AxeBuilder({ page }).analyze();
      expect(lightAxe.violations.filter((v) => ['serious', 'critical'].includes(v.impact || ''))).toEqual([]);

      await page.getByRole('button', { name: 'Toggle theme' }).click();
      await expect(page.locator('html')).toHaveClass(/dark/);
      const darkAxe = await new AxeBuilder({ page }).analyze();
      expect(darkAxe.violations.filter((v) => ['serious', 'critical'].includes(v.impact || ''))).toEqual([]);
    }

    // Mobile 390px and 360px zero overflow & >= 44x44 tap targets
    for (const width of [390, 360]) {
      for (const item of routes) {
        await page.setViewportSize({ width, height: 844 });
        await page.goto(item.path);
        await page.waitForLoadState('networkidle');

        const noOverflow = await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth
        );
        expect(noOverflow, `horizontal overflow on ${item.path} at ${width}px`).toBe(true);

        const interactive = page.locator('main a, main button, footer a, footer button');
        const count = await interactive.count();
        expect(count).toBeGreaterThanOrEqual(8);
        for (let i = 0; i < count; i++) {
          const box = await interactive.nth(i).boundingBox();
          expect(box).not.toBeNull();
          expect(box.height).toBeGreaterThanOrEqual(44);
          expect(box.width).toBeGreaterThanOrEqual(44);
        }
      }
    }
  });

  test('built routes serve route-specific SEO/social metadata, indexing directives, robots.txt, and sitemap.xml', async ({
    request,
  }) => {
    const origin = 'https://bottom-pot-puce.vercel.app';
    const expectedRoutes = [
      {
        path: '/',
        title: 'Find Jobs You Can Actually Apply To · Bottom Pot',
        description:
          'Search company career pages and selected job boards. Check the work setup and country eligibility, then open the original listing.',
        robots: 'index,follow',
        canonical: `${origin}/`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/product',
        title: 'How Bottom Pot Works · Search and Apply at the Source',
        description:
          'See how to search for jobs, review work arrangements and applicant-country eligibility, and continue to the original employer listing.',
        robots: 'index,follow',
        canonical: `${origin}/product`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/about',
        title: 'About Bottom Pot · Search-First Job Discovery',
        description:
          'Bottom Pot helps people find relevant opportunities and reach the original employer listing.',
        robots: 'index,follow',
        canonical: `${origin}/about`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/sources',
        title: 'Job Search Sources · Bottom Pot',
        description:
          'Explore the hiring platforms and selected job boards Bottom Pot searches for job opportunities.',
        robots: 'index,follow',
        canonical: `${origin}/sources`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/contact',
        title: 'Contact Bottom Pot',
        description:
          'Contact Bottom Pot with feedback, broken links, incorrect job details or questions about the search experience.',
        robots: 'index,follow',
        canonical: `${origin}/contact`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/privacy',
        title: 'Privacy Policy · Bottom Pot',
        description:
          'Learn what information Bottom Pot receives, what stays in your browser and which services help run the site.',
        robots: 'index,follow',
        canonical: `${origin}/privacy`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/terms',
        title: 'Terms of Service · Bottom Pot',
        description:
          'Read the terms for using Bottom Pot, including important information about job listings, eligibility labels and external links.',
        robots: 'index,follow',
        canonical: `${origin}/terms`,
        xRobotsHeader: null,
        inSitemap: true,
      },
      {
        path: '/app',
        title: 'Search Jobs · Bottom Pot',
        description:
          'Search job listings across supported hiring platforms and selected job boards with Bottom Pot.',
        robots: 'noindex,follow',
        canonical: `${origin}/app`,
        xRobotsHeader: 'noindex, follow',
        inSitemap: false,
      },
      {
        path: '/admin',
        title: 'Admin · Bottom Pot',
        description: 'Administrator workspace for Bottom Pot.',
        robots: 'noindex,nofollow',
        canonical: null,
        xRobotsHeader: 'noindex, nofollow',
        inSitemap: false,
      },
    ];

    for (const entry of expectedRoutes) {
      const res = await request.get(entry.path);
      expect(res.status(), `status for ${entry.path}`).toBe(200);
      const html = await res.text();
      expect(html).toContain(`<title>${entry.title}</title>`);
      expect(html).toContain(`<meta name="description" content="${entry.description}" />`);
      expect(html).toContain(`<meta name="robots" content="${entry.robots}" />`);
      expect(html).toContain(`<meta property="og:title" content="${entry.title}" />`);
      expect(html).toContain(`<meta property="og:image" content="${origin}/og-image.png" />`);
      expect(html).toContain('<meta name="twitter:card" content="summary_large_image" />');

      if (entry.canonical) {
        expect(html).toContain(`<link rel="canonical" href="${entry.canonical}" />`);
      } else {
        expect(html).not.toContain('rel="canonical"');
      }

      const headers = res.headers();
      if (entry.xRobotsHeader) {
        expect(headers['x-robots-tag']).toBe(entry.xRobotsHeader);
      } else {
        expect(headers['x-robots-tag']).toBeUndefined();
      }
    }

    const robotsRes = await request.get('/robots.txt');
    expect(robotsRes.status()).toBe(200);
    const robotsText = await robotsRes.text();
    expect(robotsText).toContain('Disallow: /admin');
    expect(robotsText).toContain('Disallow: /api/');
    expect(robotsText).toContain(`Sitemap: ${origin}/sitemap.xml`);

    const sitemapRes = await request.get('/sitemap.xml');
    expect(sitemapRes.status()).toBe(200);
    const sitemapText = await sitemapRes.text();
    for (const entry of expectedRoutes) {
      const expectedLoc = entry.path === '/' ? `${origin}/` : `${origin}${entry.path}`;
      if (entry.inSitemap) {
        expect(sitemapText).toContain(`<loc>${expectedLoc}</loc>`);
      } else {
        expect(sitemapText).not.toContain(`<loc>${expectedLoc}</loc>`);
      }
    }
    expect(sitemapText).not.toMatch(/<loc>[^<]*\?/);
  });
});
