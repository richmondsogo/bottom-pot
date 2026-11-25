import React, { useRef } from 'react';
import { LogoSymbol } from './BottomPotLogo';
import { routeToPath, type AppRoute } from '../lib/router';

export interface FooterProps {
  activeRoute?: AppRoute;
  onNavigate?: (route: AppRoute) => void;
  onNewSearch?: () => void;
  onOpenShortcuts?: () => void;
  onLogoEasterEgg?: () => void;
}

export const Footer: React.FC<FooterProps> = ({
  onNavigate,
  onNewSearch,
  onOpenShortcuts,
  onLogoEasterEgg,
}) => {
  const logoClicksRef = useRef<number[]>([]);

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

  const handleNewSearchClick = () => {
    if (onNewSearch) {
      onNewSearch();
    } else if (onNavigate) {
      onNavigate('search');
    }
  };

  return (
    <footer className="w-full border-t border-[var(--border)] bg-[var(--bg)] text-xs text-[var(--ink-muted)] font-sans">
      <div className="page-shell py-8 flex flex-col gap-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
          {/* Column 1: Brand summary */}
          <div className="flex flex-col gap-2.5">
            <div
              className="flex items-center gap-2 text-[var(--ink)] w-fit select-none"
              onClick={handleLogoTap}
            >
              <LogoSymbol className="h-5 w-auto shrink-0 text-[var(--ink)] select-none" aria-hidden="true" />
              <span className="font-semibold text-sm tracking-tight">Bottom Pot</span>
            </div>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed max-w-[34ch]">
              Live roles straight from company career pages and Nigerian job boards.
            </p>
          </div>

          {/* Column 2: Explore */}
          <nav aria-label="Product pages" className="flex flex-col gap-1.5 items-start">
            <span className="text-xs font-medium text-[var(--ink)] mb-1">Explore</span>
            <a
              href={routeToPath('search')}
              onClick={handleSearchLinkClick}
              className="py-1 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            >
              Search jobs
            </a>
            <a
              href={routeToPath('product')}
              onClick={handleLinkClick('product')}
              className="py-1 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            >
              Product
            </a>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="py-1 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            >
              Sources
            </a>
          </nav>

          {/* Column 3: Project & Actions (all buttons h-8 px-3 for spacing audit compliance) */}
          <nav aria-label="Project and workspace actions" className="flex flex-col gap-1.5 items-start">
            <span className="text-xs font-medium text-[var(--ink)] mb-1">Project</span>
            <a
              href={routeToPath('about')}
              onClick={handleLinkClick('about')}
              className="py-1 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            >
              About
            </a>
            <div className="flex flex-wrap items-center gap-1.5 pt-1 -ml-3">
              <button
                type="button"
                onClick={handleNewSearchClick}
                className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
              >
                New search
              </button>
              {onOpenShortcuts && (
                <button
                  type="button"
                  onClick={onOpenShortcuts}
                  className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  Shortcuts (?)
                </button>
              )}
            </div>
          </nav>
        </div>

        <div className="pt-5 border-t border-[var(--border-subtle)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-[var(--ink-muted)]">
          <span className="select-none">Bottom Pot · Direct to the hiring team</span>
          <a
            href="https://logo.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--ink-muted)] hover:text-[var(--ink)] underline underline-offset-2 transition-colors"
          >
            Logos provided by Logo.dev
          </a>
        </div>
      </div>
    </footer>
  );
};
