import React from 'react';
import { ArrowRight } from 'lucide-react';

interface EditorialManifestoProps {
  onStartSearching: () => void;
  onTryExample?: () => void;
}

export const EditorialManifesto: React.FC<EditorialManifestoProps> = ({
  onStartSearching,
  onTryExample,
}) => {
  return (
    <div id="manifesto">
      {/* Manifesto Section */}
      <section className="py-20 sm:py-28 bg-[var(--bg)] border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="max-w-[680px] mx-auto">
            <h2 className="font-semibold text-2xl sm:text-3xl md:text-4xl tracking-tight text-[var(--ink)] text-balance mb-8">
              Job hunting shouldn&rsquo;t mean wading through spam.
            </h2>

            <div className="space-y-6 text-base leading-[1.7] text-[var(--ink-muted)] font-normal font-sans">
              <p>
                Most job boards are built to show ads, not to get you hired. Roles that closed months ago get reposted, &ldquo;remote&rdquo; filters return jobs that need relocation, and agencies copy real company descriptions to collect r&eacute;sum&eacute;s.
              </p>

              <p>
                Bottom Pot starts where the job actually lives: the company&rsquo;s own hiring page. If a company opens a role, it shows up here, before the copies.
              </p>

              <p>
                And when a listing doesn&rsquo;t say whether it&rsquo;s remote, hybrid or on-site, we leave it blank instead of guessing.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="py-20 sm:py-28 bg-[var(--surface-subtle)] border-b border-[var(--border)] text-center">
        <div className="page-shell">
          <div className="max-w-[640px] mx-auto">
            <h3 className="font-semibold text-2xl sm:text-3xl tracking-tight text-[var(--ink)] text-balance mb-4">
              Ready to find your next role?
            </h3>
            <p className="text-sm sm:text-base text-[var(--ink-muted)] mb-8 font-sans">
              Search real career pages directly. Clean data, direct employer links, zero spam.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-5">
              <button
                type="button"
                onClick={onStartSearching}
                className="h-12 px-7 bg-[var(--accent)] text-[var(--accent-foreground)] font-medium text-[15px] rounded-none hover:bg-[var(--accent-hover)] transition-colors flex items-center gap-2 cursor-pointer select-none shadow-none"
              >
                <span>Start searching</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              {onTryExample && (
                <button
                  type="button"
                  onClick={onTryExample}
                  className="text-sm font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] hover:underline transition-colors cursor-pointer select-none py-2 px-1"
                >
                  Try an example
                </button>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 bg-[var(--bg)] text-xs text-[var(--ink-muted)] font-sans">
        <div className="page-shell flex items-center justify-center text-center">
          <div>
            Bottom Pot &middot; Jobs straight from the company
          </div>
        </div>
      </footer>
    </div>
  );
};
