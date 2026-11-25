import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { LogoLockup, LogoSymbol } from '../../components/BottomPotLogo';
import { Footer } from '../../components/Footer';
import { Header } from '../../components/Header';
import { AdminLogin } from '../../components/AdminLogin';

describe('Brandmarks, Multi-Page Header, and Editorial 3-Column Footer', () => {
  it('renders LogoLockup and LogoSymbol with both light and dark (.dark) optical cuts and respects aria-hidden vs role="img"', () => {
    const standaloneLockup = renderToStaticMarkup(
      <LogoLockup className="h-[18px] sm:h-7 w-auto" />
    );
    expect(standaloneLockup).toContain('role="img"');
    expect(standaloneLockup).toContain('aria-label="Bottom Pot"');
    expect(standaloneLockup).not.toContain('aria-hidden="true"');
    expect(standaloneLockup).toContain('dark:hidden');
    expect(standaloneLockup).toContain('fill="var(--logo-symbol, #1A382B)"');
    expect(standaloneLockup).toContain('M171.05 116H236V140H171.05');
    expect(standaloneLockup).toContain('hidden dark:block');
    expect(standaloneLockup).toContain('M171.2 117H236V139H171.2');

    const hiddenLockup = renderToStaticMarkup(
      <LogoLockup className="h-[18px] sm:h-7 w-auto" aria-hidden="true" />
    );
    expect(hiddenLockup).toContain('aria-hidden="true"');
    expect(hiddenLockup).not.toContain('role="img"');
    expect(hiddenLockup).not.toContain('aria-label=');

    const standaloneSymbol = renderToStaticMarkup(
      <LogoSymbol className="h-4 w-auto" title="Bottom Pot symbol" />
    );
    expect(standaloneSymbol).toContain('role="img"');
    expect(standaloneSymbol).toContain('aria-label="Bottom Pot symbol"');

    const hiddenSymbol = renderToStaticMarkup(
      <LogoSymbol className="h-4 w-auto" aria-hidden="true" />
    );
    expect(hiddenSymbol).toContain('aria-hidden="true"');
    expect(hiddenSymbol).not.toContain('role="img"');
  });

  it('renders unified Header navigation and AdminLogin LogoSymbol without BP monogram tile', () => {
    const headerHtml = renderToStaticMarkup(
      <Header
        activeRoute="search"
        onNavigate={() => {}}
        onOpenShortcuts={() => {}}
        onOpenCommand={() => {}}
        theme="light"
        onToggleTheme={() => {}}
        mode="user"
      />
    );
    expect(headerHtml).toContain('aria-label="Bottom Pot home"');
    expect(headerHtml).toContain('href="/"');
    expect(headerHtml).toContain('href="/app"');
    expect(headerHtml).toContain('href="/product"');
    expect(headerHtml).toContain('href="/sources"');
    expect(headerHtml).toContain('href="/about"');
    expect(headerHtml).not.toContain('href="#');
    expect(headerHtml).toContain('viewBox="20 52 216 152"');
    expect(headerHtml).not.toContain('>BP<');

    const loginHtml = renderToStaticMarkup(<AdminLogin onLoginSuccess={() => {}} />);
    expect(loginHtml).toContain('viewBox="20 52 216 152"');
    expect(loginHtml).toContain('role="img"');
    expect(loginHtml).toContain('ADMIN');
    expect(loginHtml).not.toContain('>BP<');
  });

  it('renders Footer with real multi-page links, zero dead or # links, and compliant button spacing', () => {
    const onNavigate = vi.fn();
    const onNewSearch = vi.fn();
    const onOpenShortcuts = vi.fn();

    const footerHtml = renderToStaticMarkup(
      <Footer
        activeRoute="search"
        onNavigate={onNavigate}
        onNewSearch={onNewSearch}
        onOpenShortcuts={onOpenShortcuts}
      />
    );

    expect(footerHtml).toContain('viewBox="20 52 216 152"');
    expect(footerHtml).toContain('Bottom Pot · Direct to the hiring team');
    expect(footerHtml).toContain('href="https://logo.dev"');
    expect(footerHtml).toContain('Logos provided by Logo.dev');

    expect(footerHtml).toContain('href="/app"');
    expect(footerHtml).toContain('Search jobs');
    expect(footerHtml).toContain('href="/product"');
    expect(footerHtml).toContain('Product');
    expect(footerHtml).toContain('href="/sources"');
    expect(footerHtml).toContain('Sources');
    expect(footerHtml).toContain('href="/about"');
    expect(footerHtml).toContain('About');
    expect(footerHtml).toContain('New search');
    expect(footerHtml).toContain('Shortcuts (?)');

    // Zero # anchors and zero dead placeholder links
    expect(footerHtml).not.toContain('href="#');
    for (const deadLink of ['Privacy', 'Terms', 'Careers', 'Blog', 'Contact', 'Status']) {
      expect(footerHtml).not.toContain(deadLink);
    }

    // All footer buttons include h-8 px-3 for spacing audit compliance
    const buttonMatches = footerHtml.match(/<button[^>]*>/g) || [];
    expect(buttonMatches.length).toBe(2);
    for (const btnTag of buttonMatches) {
      expect(btnTag).toContain('h-8');
      expect(btnTag).toContain('px-3');
    }
  });
});
