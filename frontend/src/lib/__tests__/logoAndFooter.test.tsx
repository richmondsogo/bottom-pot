import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { LogoLockup, LogoSymbol } from '../../components/BottomPotLogo';
import { Footer } from '../../components/Footer';
import { Header } from '../../components/Header';
import { AdminLogin } from '../../components/AdminLogin';

describe('Step 19: LogoLockup, LogoSymbol, Header, and Footer', () => {
  it('renders LogoLockup and LogoSymbol with both light and dark (.dark) optical cuts and respects aria-hidden vs role="img"', () => {
    // 1. Standalone LogoLockup (e.g. AdminLogin): has role="img" and aria-label="Bottom Pot"
    const standaloneLockup = renderToStaticMarkup(
      <LogoLockup className="h-[18px] sm:h-7 w-auto" />
    );
    expect(standaloneLockup).toContain('role="img"');
    expect(standaloneLockup).toContain('aria-label="Bottom Pot"');
    expect(standaloneLockup).not.toContain('aria-hidden="true"');
    // Light cut (dark:hidden) + forest green symbol fill + standard path
    expect(standaloneLockup).toContain('dark:hidden');
    expect(standaloneLockup).toContain('fill="var(--logo-symbol, #1A382B)"');
    expect(standaloneLockup).toContain('M171.05 116H236V140H171.05');
    // Dark cut (hidden dark:block) + currentColor fill + thinned reversed path
    expect(standaloneLockup).toContain('hidden dark:block');
    expect(standaloneLockup).toContain('M171.2 117H236V139H171.2');

    // 2. Decorative LogoLockup inside a labelled button: aria-hidden="true", no role="img"
    const hiddenLockup = renderToStaticMarkup(
      <LogoLockup className="h-[18px] sm:h-7 w-auto" aria-hidden="true" />
    );
    expect(hiddenLockup).toContain('aria-hidden="true"');
    expect(hiddenLockup).not.toContain('role="img"');
    expect(hiddenLockup).not.toContain('aria-label=');

    // 3. Standalone and aria-hidden LogoSymbol
    const standaloneSymbol = renderToStaticMarkup(
      <LogoSymbol className="h-4 w-auto" title="Bottom Pot symbol" />
    );
    expect(standaloneSymbol).toContain('role="img"');
    expect(standaloneSymbol).toContain('aria-label="Bottom Pot symbol"');
    expect(standaloneSymbol).toContain('M171.05 116H236V140H171.05');
    expect(standaloneSymbol).toContain('M171.2 117H236V139H171.2');

    const hiddenSymbol = renderToStaticMarkup(
      <LogoSymbol className="h-4 w-auto" aria-hidden="true" />
    );
    expect(hiddenSymbol).toContain('aria-hidden="true"');
    expect(hiddenSymbol).not.toContain('role="img"');
  });

  it('replaces the legacy BP monogram tile in Header and AdminLogin with standalone LogoSymbol (symbol-only branding)', () => {
    const headerHtml = renderToStaticMarkup(
      <Header
        onOpenShortcuts={() => {}}
        onOpenCommand={() => {}}
        onResetSearch={() => {}}
        onBackToMarketing={() => {}}
        theme="light"
        onToggleTheme={() => {}}
        mode="user"
      />
    );
    expect(headerHtml).toContain('aria-label="Bottom Pot - Return to Overview"');
    expect(headerHtml).toContain('viewBox="20 52 216 152"');
    expect(headerHtml).not.toContain('viewBox="0 -88.75 705.84 106.5"');
    expect(headerHtml).not.toContain('>BP<');

    const loginHtml = renderToStaticMarkup(<AdminLogin onLoginSuccess={() => {}} />);
    expect(loginHtml).toContain('viewBox="20 52 216 152"');
    expect(loginHtml).not.toContain('viewBox="0 -88.75 705.84 106.5"');
    expect(loginHtml).toContain('role="img"');
    expect(loginHtml).toContain('ADMIN');
    expect(loginHtml).not.toContain('>BP<');
  });

  it('renders Footer with marketing link set on / and workspace action set on /app, with zero dead links', () => {
    const onStartSearching = vi.fn();
    const marketingFooterHtml = renderToStaticMarkup(
      <Footer variant="marketing" onStartSearching={onStartSearching} />
    );

    // Brand symbol + tagline
    expect(marketingFooterHtml).toContain('viewBox="20 52 216 152"');
    expect(marketingFooterHtml).toContain('Bottom Pot · Jobs straight from the company');
    // Marketing actions
    expect(marketingFooterHtml).toContain('Search jobs');
    expect(marketingFooterHtml).toContain('Where we search');
    expect(marketingFooterHtml).toContain('Why Bottom Pot');
    expect(marketingFooterHtml).toContain('Manifesto');
    // Workspace-only actions absent on marketing footer
    expect(marketingFooterHtml).not.toContain('Shortcuts (?)');
    expect(marketingFooterHtml).not.toContain('New search');
    // Dead links strictly absent
    for (const deadLink of ['Privacy', 'Terms', 'About', 'Careers', 'Blog', 'Contact', 'Status']) {
      expect(marketingFooterHtml).not.toContain(deadLink);
    }

    // Workspace footer
    const onBackToMarketing = vi.fn();
    const onNewSearch = vi.fn();
    const onOpenShortcuts = vi.fn();
    const workspaceFooterHtml = renderToStaticMarkup(
      <Footer
        variant="workspace"
        onBackToMarketing={onBackToMarketing}
        onNewSearch={onNewSearch}
        onOpenShortcuts={onOpenShortcuts}
      />
    );
    expect(workspaceFooterHtml).toContain('Bottom Pot · Jobs straight from the company');
    expect(workspaceFooterHtml).toContain('Overview');
    expect(workspaceFooterHtml).toContain('New search');
    expect(workspaceFooterHtml).toContain('Shortcuts (?)');
    expect(workspaceFooterHtml).not.toContain('Where we search');
    for (const deadLink of ['Privacy', 'Terms', 'About', 'Careers', 'Blog', 'Contact', 'Status']) {
      expect(workspaceFooterHtml).not.toContain(deadLink);
    }

    // Verify all footer buttons include h-8 px-3 for spacing audit compliance
    const buttonMatches = workspaceFooterHtml.match(/<button[^>]*>/g) || [];
    expect(buttonMatches.length).toBe(3);
    for (const btnTag of buttonMatches) {
      expect(btnTag).toContain('h-8');
      expect(btnTag).toContain('px-3');
    }

    // Verify callbacks invoke cleanly when called via Footer component tree
    const footerElement = Footer({
      variant: 'workspace',
      onBackToMarketing,
      onNewSearch,
      onOpenShortcuts,
    }) as any;
    const navChildren = footerElement.props.children.props.children[1].props.children.props.children;
    const buttons = navChildren.filter(Boolean);
    expect(buttons.length).toBe(3);
    buttons[0].props.onClick();
    expect(onBackToMarketing).toHaveBeenCalledTimes(1);
    buttons[1].props.onClick();
    expect(onNewSearch).toHaveBeenCalledTimes(1);
    buttons[2].props.onClick();
    expect(onOpenShortcuts).toHaveBeenCalledTimes(1);
  });
});
