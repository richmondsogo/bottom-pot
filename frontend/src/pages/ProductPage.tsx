import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface ProductPageProps {
  onNavigate: (route: AppRoute) => void;
}

const GUARANTEES = [
  {
    title: 'Work model separated from country rules',
    body: 'Whether a job is remote, hybrid, or in-person is read strictly from structured fields and listing text. Country eligibility is evaluated separately on the server for the country you select, never guessed from your IP address.',
  },
  {
    title: 'Freshness ordering with an explicit cutoff',
    body: 'Verified recent postings stay at the top (<= 30 days fresh, <= 90 days recent). Anything older than 90 days moves beneath an "Older postings" divider so evergreen listings do not bury active openings.',
  },
  {
    title: 'Verified company marks without domain guessing',
    body: 'Employer logos come first from the ATS board or verified board upload, then from curated company domains and corporate mailto domains via Logo.dev, and drop to a crisp square monogram rather than showing the wrong company.',
  },
  {
    title: 'Blank beats wrong',
    body: 'If an employer omits salary or keeps workplace attendance vague, Bottom Pot leaves that cell empty instead of printing synthetic ranges or placeholder dashes.',
  },
];

export const ProductPage: React.FC<ProductPageProps> = ({ onNavigate }) => {
  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  return (
    <div className="w-full">
      {/* Intro */}
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Built for verifiable job search.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Most job boards trade precision for volume: stale roles pinned at the top, remote tags on
            region-locked jobs, and paraphrased summaries. Bottom Pot works like an inspection desk
            over direct career pages.
          </p>
        </div>
      </section>

      {/* How Retrieval Works */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <div>
            <h2 className="text-title font-semibold text-[var(--ink)]">
              Monitored boards first, search fallback second
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[62ch]">
              Running a search does not waste paid web queries on companies we already track cleanly.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">phase 01 · immediate stream</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                Local board store &amp; direct company checks
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Your query hits the monitored ATS board index, checks matching company slugs directly,
                and scrapes Jobberman, MyJobMag, and HotNigerianJobs concurrently. As soon as the first
                batch lands, rows stream straight into the workspace table.
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">phase 02 · sparse fallback</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                On-demand web discovery when coverage is thin
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                If monitored ATS results fall below threshold, Phase 2 queries Google across the 10
                supported ATS engines, enriches the matched pages, and registers newly found company
                boards for ongoing monitoring without manual maintenance.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Four Verification Guarantees */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">What every table row preserves</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {GUARANTEES.map((item) => (
              <div
                key={item.title}
                className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2"
              >
                <h3 className="text-sm font-semibold text-[var(--ink)]">{item.title}</h3>
                <p className="text-sm text-[var(--ink-muted)] leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Workspace Workflow */}
      <section className="py-14">
        <div className="page-shell flex flex-col gap-8">
          <div className="max-w-3xl">
            <h2 className="text-title font-semibold text-[var(--ink)]">
              Keyboard review, local shortlist, clean exports
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-3 leading-relaxed">
              Once results arrive, stay in the workspace without losing your place. Adjust query fields
              from the sticky bar above the table, filter by text (<kbd className="font-mono text-xs px-1 border border-[var(--border)]">/</kbd>),
              step rows with <kbd className="font-mono text-xs px-1 border border-[var(--border)]">j</kbd> /{' '}
              <kbd className="font-mono text-xs px-1 border border-[var(--border)]">k</kbd>, save roles
              with <kbd className="font-mono text-xs px-1 border border-[var(--border)]">s</kbd>, track
              application stages locally in your browser, or export the exact filtered table as CSV or JSON.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={routeToPath('search')}
              onClick={handleLinkClick('search')}
              className="h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-opacity cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
              style={{ borderRadius: 0 }}
            >
              View supported sources
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
