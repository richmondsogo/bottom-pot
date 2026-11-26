import React from 'react';
import { ArrowRight, ArrowUpRight, Mail } from 'lucide-react';
import { getConfiguredContactEmail } from '../lib/contactConfig';
import { getConfiguredReportProblemUrl } from '../lib/reportLink';
import { routeToPath, type AppRoute } from '../lib/router';

const FALLBACK_GITHUB_ISSUES_URL = 'https://github.com/richmondsogo/bottom-pot/issues/new';

export interface ContactPageProps {
  onNavigate: (route: AppRoute) => void;
  contactEmailOverride?: string | null;
  reportUrlOverride?: string | null;
}

export const ContactPage: React.FC<ContactPageProps> = ({
  onNavigate,
  contactEmailOverride,
  reportUrlOverride,
}) => {
  const contactEmail = getConfiguredContactEmail(contactEmailOverride);
  const issueUrl = getConfiguredReportProblemUrl(reportUrlOverride) || FALLBACK_GITHUB_ISSUES_URL;

  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Get in touch.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Found a broken apply link, a mislabeled country rule, or a bug in the search
            workspace? Report it directly on GitHub so it can be tracked and fixed in the open.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-6">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-3 items-start">
            <h2 className="text-sm font-semibold text-[var(--ink)]">
              Report an issue or broken listing
            </h2>
            <p className="text-sm text-[var(--ink-muted)] leading-relaxed max-w-[60ch]">
              Include the company name, role title, or link if a posting had the wrong date,
              salary, or country eligibility label.
            </p>
            <a
              href={issueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="group h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Open an issue on GitHub</span>
              <ArrowUpRight className="size-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
          </div>

          {contactEmail && (
            <div
              data-testid="contact-direct-email"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-3 items-start"
            >
              <h2 className="text-sm font-semibold text-[var(--ink)]">Direct email</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed max-w-[60ch]">
                Prefer to send a note directly? Reach out at the address configured for this
                deployment.
              </p>
              <a
                href={`mailto:${contactEmail}`}
                className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97]"
              >
                <Mail className="size-4 text-[var(--ink-muted)]" aria-hidden="true" />
                <span>{contactEmail}</span>
              </a>
            </div>
          )}

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <a
              href={routeToPath('about')}
              onClick={handleLinkClick('about')}
              className="group h-10 max-md:h-11 max-md:min-w-11 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
            >
              <span>Read how Bottom Pot works</span>
              <ArrowRight className="size-4 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
