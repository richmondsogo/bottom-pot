import React, { useState } from 'react';
import { ArrowRight, CornerDownLeft } from 'lucide-react';

interface HeroSectionProps {
  onLaunchWorkspace: () => void;
  onLaunchMock: () => void;
  onQuickSearch: (query: string, workModel?: 'any' | 'remote' | 'hybrid' | 'in_person', location?: string) => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onLaunchWorkspace,
  onLaunchMock,
  onQuickSearch,
}) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onQuickSearch(query.trim());
    } else {
      onLaunchWorkspace();
    }
  };

  const handleChipClick = (presetQuery: string, workModel?: 'any' | 'remote' | 'hybrid' | 'in_person', location?: string) => {
    onQuickSearch(presetQuery, workModel, location);
  };

  return (
    <section className="relative pt-16 pb-12 md:pt-24 md:pb-16 text-center">
      <div className="page-shell">
        {/* Status Indicator Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1 border border-[var(--border)] bg-[var(--surface)] mb-6 select-none">
          <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" />
          <span className="text-xs font-mono text-[var(--ink-muted)]">
            18+ ats platforms · zero aggregator middlemen
          </span>
        </div>

        {/* Display Headline */}
        <h1 className="font-semibold text-3xl sm:text-4xl md:text-5xl lg:text-[3.5rem] leading-[1.06] tracking-[-0.035em] text-[var(--ink)] max-w-[960px] mx-auto text-balance">
          Direct-to-ATS job discovery without aggregator noise.
        </h1>

        {/* Lead Subcopy */}
        <p className="text-base sm:text-[17px] leading-[1.6] text-[var(--ink-muted)] max-w-[60ch] mx-auto mt-5 text-pretty">
          Mainstream job boards bury real engineering and product roles beneath ghost listings, affiliate reposts, and guessed remote tags. Bottom Pot queries 18+ company ATS boards in real time—streaming verified roles with auditable provenance straight to your screen.
        </p>

        {/* Dual CTA Buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={onLaunchWorkspace}
            className="h-11 px-6 bg-[var(--accent)] text-[var(--accent-foreground)] font-medium text-sm rounded-none hover:bg-[var(--accent-hover)] transition-colors flex items-center gap-2 cursor-pointer select-none"
          >
            <span>Launch job engine</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={onLaunchMock}
            className="h-11 px-5 border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] font-medium text-sm rounded-none hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
          >
            Inspect live mock dataset
          </button>
        </div>

        {/* Inline Quick-Search Handoff Bar */}
        <form
          onSubmit={handleSubmit}
          className="mt-6 max-w-[560px] w-full mx-auto"
        >
          <div className="h-11 flex items-center border border-[var(--border-strong)] bg-[var(--surface)] focus-within:border-[var(--accent)] transition-colors">
            <span className="px-3 text-xs font-mono text-[var(--ink-muted)] select-none shrink-0 border-r border-[var(--border)] h-full flex items-center bg-[var(--surface-subtle)]">
              query:
            </span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Try 'Senior Backend Engineer', 'Product Designer', 'Paystack'..."
              className="flex-1 bg-transparent border-0 px-3 text-sm text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none"
            />
            <button
              type="submit"
              className="h-full px-3.5 border-l border-[var(--border)] text-xs font-medium bg-[var(--surface-subtle)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors flex items-center gap-1.5 cursor-pointer shrink-0 select-none"
            >
              <span>Run SSE search</span>
              <CornerDownLeft className="w-3.5 h-3.5 text-[var(--ink-muted)]" />
            </button>
          </div>

          {/* Preset Quick Chips */}
          <div className="mt-3 flex flex-wrap justify-center items-center gap-2 text-xs font-mono text-[var(--ink-muted)]">
            <span className="text-[var(--ink-subtle)] select-none">quick presets:</span>
            <button
              type="button"
              onClick={() => handleChipClick('Staff Frontend Engineer', 'remote')}
              className="px-2 py-0.5 border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] transition-colors cursor-pointer"
            >
              staff frontend · remote
            </button>
            <button
              type="button"
              onClick={() => handleChipClick('Backend Engineer', 'any', 'Lagos, Nigeria')}
              className="px-2 py-0.5 border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] transition-colors cursor-pointer"
            >
              backend engineer · lagos / nigeria
            </button>
            <button
              type="button"
              onClick={() => handleChipClick('Design Systems', 'remote')}
              className="px-2 py-0.5 border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] transition-colors cursor-pointer"
            >
              design systems · ashby + linear
            </button>
          </div>
        </form>
      </div>
    </section>
  );
};
