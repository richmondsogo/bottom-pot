import React from 'react';
import { CornerDownLeft } from 'lucide-react';

export const WhyDifferentSection: React.FC = () => {
  return (
    <section id="why-bottom-pot" className="py-20 sm:py-28 bg-[var(--bg)] border-b border-[var(--border)]">
      <div className="page-shell">
        {/* Section Header */}
        <div className="max-w-2xl mb-12 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">
            Why Bottom Pot is different.
          </h2>
          <p className="text-sm sm:text-base text-[var(--ink-muted)] mt-2 font-sans">
            Built for signal and honesty, without aggregator noise or inflated claims.
          </p>
        </div>

        {/* Three Plain Columns, Hairline-Separated, No Cards */}
        <div className="border border-[var(--border)] bg-[var(--surface)] grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
          {/* Column 1: Straight from the source */}
          <div className="p-8 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono text-[var(--ink-subtle)] mb-4">01</div>
              <h3 className="text-lg font-semibold tracking-tight text-[var(--ink)] mb-3">
                Straight from the source
              </h3>
              <p className="text-sm leading-relaxed text-[var(--ink-muted)] font-sans">
                We search company career pages directly, so every job is one the employer posted themselves.
              </p>
            </div>
          </div>

          {/* Column 2: Remote means remote */}
          <div className="p-8 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono text-[var(--ink-subtle)] mb-4">02</div>
              <h3 className="text-lg font-semibold tracking-tight text-[var(--ink)] mb-3">
                Remote means remote
              </h3>
              <p className="text-sm leading-relaxed text-[var(--ink-muted)] font-sans">
                We only call a job remote, hybrid or on-site when the listing says so. If it doesn&rsquo;t, we leave it blank.
              </p>
            </div>
          </div>

          {/* Column 3: Made with Nigerian developers in mind */}
          <div className="p-8 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono text-[var(--ink-subtle)] mb-4">03</div>
              <h3 className="text-lg font-semibold tracking-tight text-[var(--ink)] mb-3">
                Made with Nigerian developers in mind
              </h3>
              <p className="text-sm leading-relaxed text-[var(--ink-muted)] font-sans">
                Find roles open to Lagos, Abuja and remote-friendly teams, plus local boards like Jobberman and MyJobMag.
              </p>
            </div>
          </div>
        </div>

        {/* Quiet keyboard hint note */}
        <div className="mt-6 flex items-center justify-between text-xs text-[var(--ink-subtle)] font-sans">
          <div className="flex items-center gap-2">
            <span>Browse with your keyboard</span>
            <span className="inline-flex items-center gap-1 font-mono text-[11px] px-1.5 py-0.5 border border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]">
              j
            </span>
            <span className="inline-flex items-center gap-1 font-mono text-[11px] px-1.5 py-0.5 border border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]">
              k
            </span>
            <span className="inline-flex items-center gap-1 font-mono text-[11px] px-1.5 py-0.5 border border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]">
              Enter <CornerDownLeft className="size-2.5" />
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
