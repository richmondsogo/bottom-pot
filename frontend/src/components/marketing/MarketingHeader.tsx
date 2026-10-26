import React from 'react';
import { Sun, Moon, Search } from 'lucide-react';

interface MarketingHeaderProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onOpenCommand: () => void;
  onLaunchWorkspace: () => void;
}

export const MarketingHeader: React.FC<MarketingHeaderProps> = ({
  theme,
  onToggleTheme,
  onOpenCommand,
  onLaunchWorkspace,
}) => {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="sticky top-0 z-40 h-14 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur-md">
      <div className="page-shell h-full flex items-center justify-between">
        {/* Left: Monogram + Wordmark + Version Pill */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="flex items-center gap-2.5 text-left cursor-pointer group"
          >
            <div className="w-7 h-7 bg-[var(--accent)] text-[var(--accent-foreground)] font-semibold text-xs flex items-center justify-center select-none shadow-none">
              BP
            </div>
            <span className="font-semibold text-[15px] tracking-[-0.02em] text-[var(--ink)]">
              Bottom Pot
            </span>
          </button>
          <span className="hidden sm:inline-flex items-center px-2 py-0.5 border border-[var(--border)] text-[11px] font-mono text-[var(--ink-muted)] select-none">
            v2.4 · ats-direct
          </span>
        </div>

        {/* Center: Quiet navigation links */}
        <nav className="hidden md:flex items-center gap-7 text-[13px] text-[var(--ink-muted)]">
          <button
            type="button"
            onClick={() => scrollTo('stage')}
            className="hover:text-[var(--ink)] transition-colors cursor-pointer"
          >
            Interactive preview
          </button>
          <button
            type="button"
            onClick={() => scrollTo('provenance')}
            className="hover:text-[var(--ink)] transition-colors cursor-pointer"
          >
            Provenance ladder
          </button>
          <button
            type="button"
            onClick={() => scrollTo('platforms')}
            className="hover:text-[var(--ink)] transition-colors cursor-pointer"
          >
            ATS engines
          </button>
          <button
            type="button"
            onClick={() => scrollTo('manifesto')}
            className="hover:text-[var(--ink)] transition-colors cursor-pointer"
          >
            Why Bottom Pot
          </button>
        </nav>

        {/* Right: Quick actions */}
        <div className="flex items-center gap-2">
          {/* ⌘K Trigger */}
          <button
            type="button"
            onClick={onOpenCommand}
            className="h-8 px-2.5 border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] hover:border-[var(--border-strong)] font-mono flex items-center gap-1.5 transition-colors cursor-pointer"
            title="Open command palette (⌘K)"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">⌘K</span>
          </button>

          {/* Theme Polarity Toggle */}
          <button
            type="button"
            onClick={onToggleTheme}
            className="h-8 w-8 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] flex items-center justify-center transition-colors cursor-pointer"
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          >
            {theme === 'light' ? (
              <Moon className="w-4 h-4 text-[var(--ink)]" />
            ) : (
              <Sun className="w-4 h-4 text-[var(--ink)]" />
            )}
          </button>

          {/* Primary Action Button */}
          <button
            type="button"
            onClick={onLaunchWorkspace}
            className="h-8 px-3.5 bg-[var(--accent)] text-[var(--accent-foreground)] text-xs font-medium hover:bg-[var(--accent-hover)] transition-colors cursor-pointer select-none"
          >
            Open job engine
          </button>
        </div>
      </div>
    </header>
  );
};
