import React from 'react';

export const SignalMetricsStrip: React.FC = () => {
  return (
    <section className="border-y border-[var(--border)] bg-[var(--surface)]">
      <div className="page-shell">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] border-x border-[var(--border)]">
          {/* Cell 1 */}
          <div className="p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="font-mono text-3xl sm:text-4xl font-medium text-[var(--ink)] tracking-tight">
                18+
              </div>
              <div className="font-semibold text-sm sm:text-[15px] text-[var(--ink)] mt-2">
                Direct ATS engines
              </div>
            </div>
            <p className="text-[13px] text-[var(--ink-muted)] leading-relaxed mt-3">
              Queries company career boards directly&mdash;bypassing LinkedIn, Indeed, and recruiter scrapers.
            </p>
          </div>

          {/* Cell 2 */}
          <div className="p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="font-mono text-3xl sm:text-4xl font-medium text-[var(--ink)] tracking-tight">
                7 tiers
              </div>
              <div className="font-semibold text-sm sm:text-[15px] text-[var(--ink)] mt-2">
                Work-model provenance ladder
              </div>
            </div>
            <p className="text-[13px] text-[var(--ink-muted)] leading-relaxed mt-3">
              Every Remote, Hybrid, or Onsite label cites its exact extraction tier and literal source evidence.
            </p>
          </div>

          {/* Cell 3 */}
          <div className="p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="font-mono text-3xl sm:text-4xl font-medium text-[var(--ink)] tracking-tight">
                0
              </div>
              <div className="font-semibold text-sm sm:text-[15px] text-[var(--ink)] mt-2">
                Fabricated or guessed fields
              </div>
            </div>
            <p className="text-[13px] text-[var(--ink-muted)] leading-relaxed mt-3">
              Unknown beats wrong. If an ATS posting omits compensation or workplace type, the cell stays clean whitespace.
            </p>
          </div>

          {/* Cell 4 */}
          <div className="p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="font-mono text-3xl sm:text-4xl font-medium text-[var(--ink)] tracking-tight">
                &lt;50ms
              </div>
              <div className="font-semibold text-sm sm:text-[15px] text-[var(--ink)] mt-2">
                Local restore &amp; SQLite cache
              </div>
            </div>
            <p className="text-[13px] text-[var(--ink-muted)] leading-relaxed mt-3">
              Instant client-side session restore (bp.savedResults) and two-tier SQLite caching preserve your daily Serper budget.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
