import React, { useState, useEffect } from 'react';
import { Sun, Moon, ArrowRight } from 'lucide-react';
import { GlyphPortal } from '../ui/glyph-portal';
import { PromptSuggestion } from '../prompt-kit/prompt-suggestion';

interface HeroPortalSectionProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onStartSearching: () => void;
  onQuickSearch: (query: string, workModel?: 'any' | 'remote' | 'hybrid' | 'in_person', location?: string) => void;
}

export const HeroPortalSection: React.FC<HeroPortalSectionProps> = ({
  theme,
  onToggleTheme,
  onStartSearching,
  onQuickSearch,
}) => {
  const [fontStatus, setFontStatus] = useState<'loading' | 'ready' | 'timeout'>(() => {
    if (typeof document === 'undefined' || !('fonts' in document)) {
      return 'timeout';
    }
    return 'loading';
  });

  useEffect(() => {
    if (typeof document === 'undefined' || !('fonts' in document)) {
      return;
    }

    let isMounted = true;
    const timeoutId = window.setTimeout(() => {
      if (isMounted) {
        setFontStatus((prev) => (prev === 'loading' ? 'timeout' : prev));
      }
    }, 1600);

    document.fonts
      .load('700 100px "Geist Variable"')
      .then((fonts) => {
        if (!isMounted) return;
        window.clearTimeout(timeoutId);
        if (fonts && fonts.length > 0) {
          setFontStatus('ready');
        } else {
          setFontStatus('timeout');
        }
      })
      .catch(() => {
        if (isMounted) {
          window.clearTimeout(timeoutId);
          setFontStatus('timeout');
        }
      });

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Shared opening header (used in both portal front slot and static fallback)
  const renderHeader = () => (
    <div className="w-full border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur-md pointer-events-auto">
      <div className="page-shell h-14 flex items-center justify-between">
        {/* Left: Brandmark + Wordmark (No version tag) */}
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="flex items-center gap-2.5 text-left cursor-pointer group"
          aria-label="Bottom Pot home"
        >
          <div className="w-7 h-7 bg-[var(--accent)] text-[var(--accent-foreground)] font-semibold text-xs flex items-center justify-center select-none shadow-none">
            BP
          </div>
          <span className="font-semibold text-[15px] tracking-[-0.02em] text-[var(--ink)]">
            Bottom Pot
          </span>
        </button>

        {/* Right: Anchor links + Theme toggle (No ⌘K chip) */}
        <div className="flex items-center gap-6 sm:gap-8">
          <nav className="hidden md:flex items-center gap-5 sm:gap-7 text-[13px] text-[var(--ink-muted)]">
            <button
              type="button"
              onClick={() => scrollTo('where-we-search')}
              className="hover:text-[var(--ink)] transition-colors cursor-pointer font-medium"
            >
              Where we search
            </button>
            <button
              type="button"
              onClick={() => scrollTo('why-bottom-pot')}
              className="hover:text-[var(--ink)] transition-colors cursor-pointer font-medium"
            >
              Why Bottom Pot
            </button>
            <button
              type="button"
              onClick={() => scrollTo('manifesto')}
              className="hover:text-[var(--ink)] transition-colors cursor-pointer font-medium"
            >
              Manifesto
            </button>
          </nav>

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
        </div>
      </div>
    </div>
  );

  // Shared revealed content / CTA section (No embedded form)
  const renderRevealedContent = () => (
    <div className="w-full max-w-[640px] mx-auto flex flex-col items-center text-center gap-6 py-4">
      <h2 className="text-xl sm:text-2xl md:text-3xl font-semibold text-[var(--gp-foreground)] tracking-tight text-balance">
        What kind of role are you after?
      </h2>

      {/* Primary Start Searching CTA with restrained motion */}
      <button
        type="button"
        onClick={onStartSearching}
        className="group h-12 px-8 bg-[var(--accent)] text-[var(--accent-foreground)] font-medium text-[15px] rounded-none hover:bg-[var(--accent-hover)] transition-[background-color,color,transform] duration-140 ease-out active:scale-[0.98] motion-reduce:transform-none motion-reduce:transition-none flex items-center justify-center gap-2.5 cursor-pointer select-none shadow-none"
      >
        <span>Start searching</span>
        <ArrowRight className="w-4 h-4 transition-transform duration-140 ease-out group-hover:translate-x-0.5 motion-reduce:transform-none" aria-hidden="true" />
      </button>

      {/* Under the button: square PromptSuggestion chips + quiet trust line */}
      <div className="flex flex-col items-center gap-3 pt-2">
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
          <span className="text-xs text-[var(--gp-foreground)]/70 font-sans mr-1">Quick starters:</span>
          <PromptSuggestion
            onClick={() => onQuickSearch('React engineer', 'remote', '')}
            className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
          >
            React engineer · Remote
          </PromptSuggestion>
          <PromptSuggestion
            onClick={() => onQuickSearch('Python developer', 'any', 'Lagos')}
            className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
          >
            Python developer · Lagos
          </PromptSuggestion>
          <PromptSuggestion
            onClick={() => onQuickSearch('Product designer', 'any', '')}
            className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
          >
            Product designer
          </PromptSuggestion>
        </div>

        <p className="text-xs text-[var(--gp-foreground)]/70 text-center max-w-lg mx-auto font-sans leading-relaxed">
          If a listing doesn&rsquo;t say whether it&rsquo;s remote, we leave it blank instead of guessing.
        </p>
      </div>
    </div>
  );

  // If font failed or timed out (~1.6s), render static hero fallback
  if (fontStatus !== 'ready') {
    return (
      <section className="w-full flex flex-col bg-[var(--bg)] text-[var(--ink)]">
        {renderHeader()}

        <div className="page-shell py-16 sm:py-24 flex flex-col items-center text-center">
          <h1 className="text-sm sm:text-base font-medium text-[var(--ink-muted)] mb-4 tracking-normal">
            Jobs straight from the company.
          </h1>

          <div
            className="text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-[var(--ink)] mb-4 select-none"
            style={{ fontFamily: '"Geist Variable", sans-serif', fontWeight: 700 }}
          >
            Bottom Pot
          </div>

          <p className="text-sm sm:text-base text-[var(--ink-muted)] max-w-md mx-auto mb-8 leading-relaxed font-sans">
            Real openings from company career pages. No reposts, no recruiter spam.
          </p>

          <button
            type="button"
            onClick={onStartSearching}
            className="group h-12 px-7 bg-[var(--accent)] text-[var(--accent-foreground)] font-medium text-[15px] inline-flex items-center justify-center gap-2 hover:bg-[var(--accent-hover)] transition-[background-color,color,transform] duration-140 ease-out active:scale-[0.98] motion-reduce:transform-none motion-reduce:transition-none cursor-pointer select-none mb-10 shadow-none"
          >
            <span>Start searching</span>
            <ArrowRight className="w-4 h-4 transition-transform duration-140 ease-out group-hover:translate-x-0.5 motion-reduce:transform-none" aria-hidden="true" />
          </button>

          <div className="w-full max-w-[640px] mx-auto flex flex-col items-center gap-3 pt-2 text-center">
            <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
              <span className="text-xs text-[var(--ink-subtle)] mr-1">Quick starters:</span>
              <PromptSuggestion
                onClick={() => onQuickSearch('React engineer', 'remote', '')}
                className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
              >
                React engineer · Remote
              </PromptSuggestion>
              <PromptSuggestion
                onClick={() => onQuickSearch('Python developer', 'any', 'Lagos')}
                className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
              >
                Python developer · Lagos
              </PromptSuggestion>
              <PromptSuggestion
                onClick={() => onQuickSearch('Product designer', 'any', '')}
                className="rounded-none! border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs h-7 px-2.5 hover:bg-[var(--surface-hover)]"
              >
                Product designer
              </PromptSuggestion>
            </div>
            <p className="text-xs text-[var(--ink-subtle)] text-center max-w-lg mx-auto font-sans leading-relaxed">
              If a listing doesn&rsquo;t say whether it&rsquo;s remote, we leave it blank instead of guessing.
            </p>
          </div>
        </div>
      </section>
    );
  }

  // Front slot for GlyphPortal opening frame
  const frontContent = (
    <div className="relative w-full h-full flex flex-col justify-between pointer-events-none">
      {/* Pinned Top Navigation */}
      {renderHeader()}

      {/* Above Wordmark: h1 */}
      <div
        className="absolute w-full px-4 text-center pointer-events-auto"
        style={{
          top: 'calc(var(--gp-word-top, 38%) - 42px)',
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      >
        <h1 className="text-sm sm:text-base font-medium text-[var(--ink-muted)] tracking-normal">
          Jobs straight from the company.
        </h1>
      </div>

      {/* Below Wordmark: Support line */}
      <div
        className="absolute w-full px-4 text-center pointer-events-auto"
        style={{
          top: 'calc(var(--gp-word-bottom, 54%) + 24px)',
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      >
        <p className="text-sm sm:text-base text-[var(--ink-muted)] max-w-md mx-auto leading-relaxed font-sans">
          Real openings from company career pages. No reposts, no recruiter spam.
        </p>
      </div>

      {/* Empty bottom spacer to let data-gp-caption align at the bottom */}
      <div className="h-16" />
    </div>
  );

  return (
    <GlyphPortal
      word="Bottom Pot"
      fontFamily="Geist Variable"
      fontWeight={700}
      scrollLength={1.8}
      interactive={true}
      annotations={false}
      enterLabel="Start searching"
      front={frontContent}
    >
      {renderRevealedContent()}
    </GlyphPortal>
  );
};
