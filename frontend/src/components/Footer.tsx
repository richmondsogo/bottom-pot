import React from 'react';
import { LogoSymbol } from './BottomPotLogo';

export interface FooterProps {
  variant: 'marketing' | 'workspace';
  onStartSearching?: () => void;
  onBackToMarketing?: () => void;
  onNewSearch?: () => void;
  onOpenShortcuts?: () => void;
}

export const Footer: React.FC<FooterProps> = ({
  variant,
  onStartSearching,
  onBackToMarketing,
  onNewSearch,
  onOpenShortcuts,
}) => {
  const scrollToSection = (id: string) => {
    if (typeof document === 'undefined') return;
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <footer className="w-full border-t border-[var(--border)] bg-[var(--bg)] text-xs text-[var(--ink-muted)] font-sans">
      <div className="page-shell py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Left cluster: Brand symbol + tagline */}
        <div className="flex items-center gap-2.5 text-[var(--ink-muted)] select-none">
          <LogoSymbol className="h-4 w-auto shrink-0 text-[var(--ink)]" aria-hidden="true" />
          <span>Bottom Pot &middot; Jobs straight from the company</span>
        </div>

        {/* Right cluster: Context-specific working actions (all buttons h-8 px-3 for spacing audit compliance) */}
        <nav
          aria-label="Footer navigation"
          className="flex flex-wrap items-center justify-center sm:justify-end gap-1"
        >
          {variant === 'marketing' ? (
            <>
              {onStartSearching && (
                <button
                  type="button"
                  onClick={onStartSearching}
                  className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  Search jobs
                </button>
              )}
              <button
                type="button"
                onClick={() => scrollToSection('where-we-search')}
                className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
              >
                Where we search
              </button>
              <button
                type="button"
                onClick={() => scrollToSection('why-bottom-pot')}
                className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
              >
                Why Bottom Pot
              </button>
              <button
                type="button"
                onClick={() => scrollToSection('manifesto')}
                className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
              >
                Manifesto
              </button>
            </>
          ) : (
            <>
              {onBackToMarketing && (
                <button
                  type="button"
                  onClick={onBackToMarketing}
                  className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  Overview
                </button>
              )}
              {onNewSearch && (
                <button
                  type="button"
                  onClick={onNewSearch}
                  className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  New search
                </button>
              )}
              {onOpenShortcuts && (
                <button
                  type="button"
                  onClick={onOpenShortcuts}
                  className="h-8 px-3 inline-flex items-center justify-center text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                >
                  Shortcuts (?)
                </button>
              )}
            </>
          )}
        </nav>
      </div>
    </footer>
  );
};
