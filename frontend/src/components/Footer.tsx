import React, { useRef } from 'react';
import { LogoSymbol } from './BottomPotLogo';
import { FooterFlickeringGrid } from './FooterFlickeringGrid';
import { getConfiguredContactEmail } from '../lib/contactConfig';
import { routeToPath, type AppRoute } from '../lib/router';

export interface FooterProps {
  activeRoute?: AppRoute;
  onNavigate?: (route: AppRoute) => void;
  onNewSearch?: () => void;
  onOpenShortcuts?: () => void;
  onLogoEasterEgg?: () => void;
  contactEmailOverride?: string | null;
}

export const Footer: React.FC<FooterProps> = ({
  onNavigate,
  onNewSearch,
  onOpenShortcuts,
  onLogoEasterEgg,
  contactEmailOverride,
}) => {
  const logoClicksRef = useRef<number[]>([]);
  const contactEmail = getConfiguredContactEmail(contactEmailOverride);

  const handleLogoTap = () => {
    if (!onLogoEasterEgg) return;
    const now = Date.now();
    const recent = logoClicksRef.current.filter((t) => now - t < 2500);
    recent.push(now);
    logoClicksRef.current = recent;
    if (recent.length >= 5) {
      logoClicksRef.current = [];
      onLogoEasterEgg();
    }
  };

  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (!onNavigate) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  const handleSearchLinkClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    if (onNewSearch) {
      e.preventDefault();
      onNewSearch();
    } else if (onNavigate) {
      e.preventDefault();
      onNavigate('search');
    }
  };

  return (
    <footer className="relative overflow-hidden w-full border-t border-[var(--border)] bg-[var(--bg)] text-xs text-[var(--ink-muted)] font-sans">
      <FooterFlickeringGrid />

      <div className="page-shell relative z-10 py-10 flex flex-col gap-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-10 items-start">
          {/* Left: Brand summary + optional direct email */}
          <div className="md:col-span-6 flex flex-col gap-3 items-start">
            <div
              className="flex items-center gap-2 text-[var(--ink)] w-fit select-none"
              onClick={handleLogoTap}
            >
              <LogoSymbol className="h-5 w-auto shrink-0 text-[var(--ink)] select-none" aria-hidden="true" />
              <span className="font-semibold text-sm tracking-tight">Bottom Pot</span>
            </div>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed max-w-[36ch]">
              Live roles straight from company career pages and Nigerian job boards.
            </p>
            {contactEmail && (
              <a
                href={`mailto:${contactEmail}`}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs font-medium text-[var(--ink)] hover:text-[var(--ink-muted)] underline underline-offset-4 decoration-[var(--border-strong)] transition-colors"
              >
                {contactEmail}
              </a>
            )}
          </div>

          {/* Right: Editorial Link Columns */}
          <div className="md:col-span-6 grid grid-cols-2 gap-8 sm:gap-12 items-start">
            <nav aria-label="Product pages" className="flex flex-col gap-1.5 items-start">
              <span className="text-xs font-medium text-[var(--ink-subtle)] mb-1">Product</span>
              <a
                href={routeToPath('search')}
                onClick={handleSearchLinkClick}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
              >
                Search
              </a>
              <a
                href={routeToPath('product')}
                onClick={handleLinkClick('product')}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
              >
                How it works
              </a>
              <a
                href={routeToPath('sources')}
                onClick={handleLinkClick('sources')}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
              >
                Sources
              </a>
            </nav>

            <nav aria-label="Project pages" className="flex flex-col gap-1.5 items-start">
              <span className="text-xs font-medium text-[var(--ink-subtle)] mb-1">Project</span>
              <a
                href={routeToPath('about')}
                onClick={handleLinkClick('about')}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
              >
                About
              </a>
              <a
                href={routeToPath('contact')}
                onClick={handleLinkClick('contact')}
                className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-xs text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
              >
                Contact
              </a>
              {onOpenShortcuts && (
                <button
                  type="button"
                  onClick={onOpenShortcuts}
                  className="h-8 max-md:h-11 max-md:min-w-11 px-3 -ml-3 rounded-md inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  Shortcuts (?)
                </button>
              )}
            </nav>
          </div>
        </div>

        <div className="pt-5 border-t border-[var(--border-subtle)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-[var(--ink-muted)]">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="select-none">© 2026 Bottom Pot</span>
            <span aria-hidden="true" className="text-[var(--ink-subtle)]">
              ·
            </span>
            <a
              href="https://logo.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="py-1 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center text-[var(--ink-muted)] hover:text-[var(--ink)] underline underline-offset-2 transition-colors"
            >
              Logos provided by Logo.dev
            </a>
          </div>
          <span className="text-[var(--ink-subtle)] select-none">
            Scraped from the bottom of the pot.
          </span>
        </div>
      </div>
    </footer>
  );
};
