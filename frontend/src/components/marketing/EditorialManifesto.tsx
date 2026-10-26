import React from 'react';
import { ArrowRight } from 'lucide-react';

interface EditorialManifestoProps {
  onLaunchWorkspace: () => void;
  onLaunchMock: () => void;
}

export const EditorialManifesto: React.FC<EditorialManifestoProps> = ({
  onLaunchWorkspace,
  onLaunchMock,
}) => {
  return (
    <div id="manifesto">
      {/* Editorial Story Section */}
      <section className="py-20 sm:py-28 bg-[var(--bg)] border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="max-w-[680px] mx-auto">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] text-xs font-mono text-[var(--ink-muted)] mb-6">
              the bottom pot manifesto
            </div>

            <h2 className="font-semibold text-2xl sm:text-3xl md:text-4xl tracking-tight text-[var(--ink)] text-balance mb-8">
              Job hunting shouldn&rsquo;t mean fighting SEO spam.
            </h2>

            <div className="space-y-6 text-base leading-[1.7] text-[var(--ink-muted)] font-normal">
              <p>
                <strong className="text-[var(--ink)] font-semibold">Every week, millions of engineers search for roles on aggregator platforms</strong> designed to maximize ad impressions rather than hiring accuracy. Roles closed three months ago are automatically reposted. &ldquo;Remote&rdquo; filters return hybrid jobs requiring relocation. Third-party staffing agencies clone real company descriptions to harvest resumes.
              </p>

              <p>
                <strong className="text-[var(--ink)] font-semibold">We built Bottom Pot on a simpler premise:</strong> go straight to the system of record. When a company opens a role, it lives in their Applicant Tracking System&mdash;Greenhouse, Ashby, Lever, Workable&mdash;long before aggregators scrape and distort it.
              </p>

              <p>
                <strong className="text-[var(--ink)] font-semibold">By querying those ATS platforms directly,</strong> enforcing a strict 7-tier provenance ladder, and refusing to fabricate missing fields, Bottom Pot gives you a quiet, high-density workspace where every single row is a real job at a real company.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Full-Width Architectural Footer CTA */}
      <section className="py-16 sm:py-24 bg-[var(--surface-subtle)] border-b border-[var(--border)] text-center">
        <div className="page-shell">
          <div className="max-w-[640px] mx-auto">
            <h3 className="font-semibold text-2xl sm:text-3xl tracking-tight text-[var(--ink)] text-balance mb-4">
              Ready to query the source directly?
            </h3>
            <p className="text-sm text-[var(--ink-muted)] mb-8">
              Start streaming real-time ATS job postings or explore the verified mock dataset in under two seconds.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={onLaunchWorkspace}
                className="h-11 px-6 bg-[var(--accent)] text-[var(--accent-foreground)] font-medium text-sm rounded-none hover:bg-[var(--accent-hover)] transition-colors flex items-center gap-2 cursor-pointer select-none"
              >
                <span>Open Bottom Pot workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={onLaunchMock}
                className="h-11 px-5 border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] font-medium text-sm rounded-none hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
              >
                Load instant mock workspace (?mock=1)
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom Metadata Bar */}
      <footer className="py-6 bg-[var(--bg)] text-xs text-[var(--ink-subtle)]">
        <div className="page-shell flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <div>
            Bottom Pot &middot; Direct-to-ATS Job Discovery Engine
          </div>
          <div className="font-mono text-[11px] text-[var(--ink-muted)]">
            radius: 0px &middot; adr-0001..0021 verified &middot; press ⌘K anytime
          </div>
        </div>
      </footer>
    </div>
  );
};
