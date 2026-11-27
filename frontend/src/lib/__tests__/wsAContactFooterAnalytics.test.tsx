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

    for (const publicPath of ['/', '/app', '/product', '/sources', '/about', '/contact', '/privacy', '/terms']) {
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

  it('renders ContactPage with approved copy, Send an email action, configured address, no form, and zero GitHub links', () => {
    vi.stubEnv('VITE_CONTACT_EMAIL', '');
    const defaultHtml = renderToStaticMarkup(<ContactPage onNavigate={() => {}} />);
    expect(defaultHtml).toContain('Get in touch.');
    expect(defaultHtml).toContain(
      'Found a broken link, incorrect job detail or confusing eligibility label? Have feedback about the search experience? Send us a message. Useful reports help us make Bottom Pot better.'
    );
    expect(defaultHtml).toContain('Email us');
    expect(defaultHtml).toContain(
      'Tell us what happened and include the company, role title or listing link when relevant.'
    );
    expect(defaultHtml).toContain('Send an email');
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
    expect(overriddenHtml).toContain('Send an email');
    expect(overriddenHtml).toContain('team@bottompot.example');
    expect(overriddenHtml).not.toMatch(/github/i);
  });

  it('renders AboutPage principles and 13 FAQs with approved copy and zero GitHub or stale claims', () => {
    const aboutHtml = renderToStaticMarkup(<AboutPage onNavigate={() => {}} />);

    expect(aboutHtml).toContain('What we build around');
    expect(aboutHtml).toContain('A search with intent');
    expect(aboutHtml).toContain('Clarity before the application');
    expect(aboutHtml).toContain('Honest information');
    expect(aboutHtml).toContain('The original source');
    expect(aboutHtml).toContain('Useful without an account');

    expect(aboutHtml).toContain('Frequently asked questions');
    expect(aboutHtml).toContain('What is Bottom Pot?');
    expect(aboutHtml).toContain('How is Bottom Pot different from a traditional job board?');
    expect(aboutHtml).toContain('Why do I have to search instead of browsing all jobs?');
    expect(aboutHtml).toContain('Can I search for jobs in different locations?');
    expect(aboutHtml).toContain('Does remote mean I can work from anywhere?');
    expect(aboutHtml).toContain('What do Eligible, Restricted and Unverified mean?');
    expect(aboutHtml).toContain('Where do the job listings come from?');
    expect(aboutHtml).toContain(
      'Bottom Pot searches 10 hiring platforms and 3 selected job boards. The hiring platforms host career pages for individual employers; they are not 10 individual employers.'
    );
    expect(aboutHtml).toContain('How current are the listings?');
    expect(aboutHtml).toContain('Are salary details shown for every job?');
    expect(aboutHtml).toContain('Where do the application links go?');
    expect(aboutHtml).toContain('Do I need an account?');
    expect(aboutHtml).toContain('Are my saved jobs synced across devices?');
    expect(aboutHtml).toContain('What should I do if a listing looks wrong or the link is broken?');

    expect(aboutHtml).not.toContain('28 curated tracked company boards');
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
