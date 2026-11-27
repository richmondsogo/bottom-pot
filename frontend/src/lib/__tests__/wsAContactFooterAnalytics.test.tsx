import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { getConfiguredContactEmail, isValidContactEmail } from '../contactConfig';
import { shouldEnableVercelAnalytics } from '../analytics';
import { AboutPage } from '../../pages/AboutPage';
import { ContactPage } from '../../pages/ContactPage';
import { Footer } from '../../components/Footer';
import { FooterFlickeringGrid } from '../../components/FooterFlickeringGrid';
import vercelJsonRaw from '../../../../vercel.json?raw';
import appSrc from '../../App.tsx?raw';

describe('WS-A Contact, About Accordions, Footer Flickering Grid, and Vercel Analytics', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    delete (globalThis as { __BOTTOM_POT_CONTACT_EMAIL__?: unknown })
      .__BOTTOM_POT_CONTACT_EMAIL__;
  });

  it('resolves configured contact email with default Gmail fallback and rejects invalid overrides', () => {
    vi.stubEnv('VITE_CONTACT_EMAIL', '');
    expect(getConfiguredContactEmail()).toBe('richmondsogo@gmail.com');
    expect(getConfiguredContactEmail('')).toBeNull();
    expect(getConfiguredContactEmail('   ')).toBeNull();
    expect(getConfiguredContactEmail('not-an-email')).toBeNull();
    expect(getConfiguredContactEmail('@example.com')).toBeNull();
    expect(getConfiguredContactEmail('user@')).toBeNull();
    expect(isValidContactEmail('richmondsogo@gmail.com')).toBe(true);
    expect(getConfiguredContactEmail('  richmondsogo@gmail.com  ')).toBe('richmondsogo@gmail.com');

    vi.stubEnv('VITE_CONTACT_EMAIL', 'team@bottompot.example');
    expect(getConfiguredContactEmail()).toBe('team@bottompot.example');
    expect(getConfiguredContactEmail('invalid-override')).toBeNull();
  });

  it('gates Vercel Analytics strictly to production non-mock non-webdriver public routes', () => {
    expect(shouldEnableVercelAnalytics()).toBe(false);

    expect(
      shouldEnableVercelAnalytics({
        isProd: false,
        isMock: false,
        isWebdriver: false,
        pathname: '/',
      })
    ).toBe(false);

    expect(
      shouldEnableVercelAnalytics({
        isProd: true,
        isMock: true,
        isWebdriver: false,
        pathname: '/app',
      })
    ).toBe(false);

    expect(
      shouldEnableVercelAnalytics({
        isProd: true,
        isMock: false,
        isWebdriver: true,
        pathname: '/about',
      })
    ).toBe(false);

    expect(
      shouldEnableVercelAnalytics({
        isProd: true,
        isMock: false,
        isWebdriver: false,
        pathname: '/admin',
      })
    ).toBe(false);

    expect(
      shouldEnableVercelAnalytics({
        isProd: true,
        isMock: false,
        isWebdriver: false,
        pathname: '/admin/',
      })
    ).toBe(false);

    for (const publicPath of ['/', '/app', '/product', '/sources', '/about', '/contact']) {
      expect(
        shouldEnableVercelAnalytics({
          isProd: true,
          isMock: false,
          isWebdriver: false,
          pathname: publicPath,
        })
      ).toBe(true);
    }
  });

  it('renders ContactPage with default Gmail mailto link, no form, and zero GitHub links', () => {
    vi.stubEnv('VITE_CONTACT_EMAIL', '');
    const defaultHtml = renderToStaticMarkup(<ContactPage onNavigate={() => {}} />);
    expect(defaultHtml).toContain('Get in touch.');
    expect(defaultHtml).toContain('welcome by email');
    expect(defaultHtml).toContain('data-testid="contact-direct-email"');
    expect(defaultHtml).toContain('href="mailto:richmondsogo@gmail.com"');
    expect(defaultHtml).toContain('richmondsogo@gmail.com');
    expect(defaultHtml).not.toContain('<form');
    expect(defaultHtml).not.toMatch(/github/i);
    expect(defaultHtml).not.toContain('\u2014');

    const overriddenHtml = renderToStaticMarkup(
      <ContactPage onNavigate={() => {}} contactEmailOverride="team@bottompot.example" />
    );
    expect(overriddenHtml).toContain('href="mailto:team@bottompot.example"');
    expect(overriddenHtml).toContain('team@bottompot.example');
    expect(overriddenHtml).not.toMatch(/github/i);
  });

  it('renders AboutPage rules and FAQ accordions with verified copy, privacy link, and zero GitHub references', () => {
    const aboutHtml = renderToStaticMarkup(<AboutPage onNavigate={() => {}} />);

    expect(aboutHtml).toContain('Five rules we stick to');
    expect(aboutHtml).toContain('Direct apply links');
    expect(aboutHtml).toContain('Blank beats guessed');
    expect(aboutHtml).toContain('Clear country rules');
    expect(aboutHtml).toContain('No account needed');
    expect(aboutHtml).toContain('Reliable sources only');
    expect(aboutHtml).toContain(
      'Listings from Nigerian job boards are treated as workable from Nigeria unless the posting explicitly excludes Nigeria.'
    );

    expect(aboutHtml).toContain('Frequently asked questions');
    expect(aboutHtml).toContain('Where do listings come from?');
    expect(aboutHtml).toContain('28 curated tracked company boards');
    expect(aboutHtml).toContain('Do I need an account to use Bottom Pot?');
    expect(aboutHtml).toContain('How fresh are the results?');
    expect(aboutHtml).toContain('30-minute schedule');
    expect(aboutHtml).toContain('5-minute in-memory result cache');
    expect(aboutHtml).toContain('12-hour search query cache');
    expect(aboutHtml).toContain('24-hour listing detail cache');
    expect(aboutHtml).toContain('What is stored locally in my browser?');
    expect(aboutHtml).toContain('1,000 entries');
    expect(aboutHtml).toContain('3 MB');
    expect(aboutHtml).toContain('What does analytics collect?');
    expect(aboutHtml).toContain('page analytics through Vercel');
    expect(aboutHtml).toContain('href="/privacy"');
    expect(aboutHtml).not.toContain('Per Vercel documentation');
    expect(aboutHtml).not.toMatch(/github|open source|pull request/i);

    expect(aboutHtml).toContain('rounded-lg');
    expect(aboutHtml).toContain('text-[var(--ink-muted)]');
    expect(aboutHtml).not.toContain('\u2014');
    expect(aboutHtml).not.toContain('href="#');
  });

  it('renders FooterFlickeringGrid as quiet pointer-events-none aria-hidden background at 0.37 opacity without green accent', () => {
    const gridHtml = renderToStaticMarkup(<FooterFlickeringGrid />);
    expect(gridHtml).toContain('data-testid="footer-flickering-grid"');
    expect(gridHtml).toContain('aria-hidden="true"');
    expect(gridHtml).toContain('pointer-events-none');
    expect(gridHtml).toContain('opacity-[0.37]');
    expect(gridHtml).not.toContain('opacity-40');
    expect(gridHtml).not.toContain('dark:opacity-50');
    expect(gridHtml).toContain('mask-image');
    expect(gridHtml).not.toContain('--accent');
    expect(gridHtml).not.toContain('#1A382B');
    expect(gridHtml).not.toContain('#2E7D52');

    const footerHtml = renderToStaticMarkup(<Footer onNavigate={() => {}} />);
    expect(footerHtml).toContain('data-testid="footer-flickering-grid"');
    expect(footerHtml).not.toContain('Shortcuts (?)');
  });

  it('updates vercel.json rewrites to exclude _vercel/ and easter/ and keeps App.tsx analytics + eligibility provider wiring intact', () => {
    const config = JSON.parse(vercelJsonRaw);
    const spaRewrite = config.rewrites.find((r: { destination: string }) => r.destination === '/index.html');
    expect(spaRewrite).toBeDefined();
    expect(spaRewrite.source).toContain('_vercel/');
    expect(spaRewrite.source).toContain('easter/');

    const allHeaderKeys = (config.headers || []).flatMap((rule: { headers?: Array<{ key: string }> }) =>
      (rule.headers || []).map((h) => h.key.toLowerCase())
    );
    expect(allHeaderKeys).not.toContain('content-security-policy');

    expect(appSrc).toContain("from '@vercel/analytics/react'");
    expect(appSrc).toContain('shouldEnableVercelAnalytics() && !isAdminRoute && mode !== \'admin\'');
    expect(appSrc).toContain('<Analytics />');
    expect(appSrc).toContain('provider: job.provider ?? null');
  });
});
