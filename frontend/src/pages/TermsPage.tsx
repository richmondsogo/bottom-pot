import React from 'react';
import { Mail } from 'lucide-react';
import { DEFAULT_CONTACT_EMAIL, getConfiguredContactEmail } from '../lib/contactConfig';
import { routeToPath, type AppRoute } from '../lib/router';

export interface TermsPageProps {
  onNavigate?: (route: AppRoute) => void;
  contactEmailOverride?: string | null;
}

const LAST_UPDATED = 'November 27, 2026';

export const TermsPage: React.FC<TermsPageProps> = ({
  onNavigate,
  contactEmailOverride,
}) => {
  const contactEmail = getConfiguredContactEmail(contactEmailOverride) ?? DEFAULT_CONTACT_EMAIL;

  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (!onNavigate) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Terms of Service
          </h1>
          <p className="text-sm text-[var(--ink-subtle)] mt-3">
            Last updated: {LAST_UPDATED}
          </p>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            These terms explain what Bottom Pot does, what we do not promise, and how we ask you to
            use the site.
          </p>

          <div
            data-testid="terms-summary-box"
            className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col gap-3"
          >
            <h2 className="text-sm font-semibold text-[var(--ink)]">In plain words</h2>
            <ul className="list-disc pl-5 space-y-1.5 text-sm text-[var(--ink-muted)] leading-relaxed">
              <li>Bottom Pot gathers public job listings, but we are not an employer or recruiter.</li>
              <li>Job details can be wrong or closed, so always verify details with the employer.</li>
              <li>Country and work labels are a guide, not a hiring or legal guarantee.</li>
              <li>Use the site for your own job search and follow our request limits.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">What Bottom Pot is</h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Bottom Pot collects public job listings from hiring platforms, Nigerian job boards, and
            company career pages so you can search them in one place. We are a search tool only. We
            are not an employer, staffing firm, or recruiter, and we do not endorse or guarantee any
            job, company, or employer.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Listings can be out of date or wrong
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Jobs close fast, and outside pages change without warning. Pay, job title, work setup,
            and deadlines shown here may be incomplete, delayed, or inaccurate. Always check the
            official employer posting before you spend time applying or make any career decision.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Eligibility labels are a guide, not a guarantee
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Country labels, work tags, and source quotes are best-effort hints built from job text.
            Our checks can miss hidden rules or misread wording. Only the hiring company can tell you
            if your country, visa, or work setup qualifies for a role.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Links, logos, and outside content belong to their owners
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Job descriptions, company names, trademarks, logos, and external links belong to the
            companies and job sites that published them. When you follow a link to apply or view a
            source, you leave Bottom Pot. We do not control or check outside websites, and your visit
            there follows that site&apos;s own rules.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">Fair use and limits</h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Please use Bottom Pot for personal job hunting. The site has rate limits on searches and
            eligibility checks so everyone gets fair access. Do not run bots, scrape our search
            endpoints, send heavy automated traffic, or try to break security or access controls.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            The service may change or go down
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            We may add, change, pause, or shut down sources or features at any time. Searches may
            return partial matches or fail when outside job sites slow down, block requests, or
            reach daily search caps.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            No promises and limit on responsibility
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            You use Bottom Pot as it is, at your own risk. We make no promise that the site will be
            always online, error free, or accurate. As far as the law allows, we are not
            responsible for missed jobs, wrong listing info, lost browser data, or anything that
            happens on outside employer websites.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">Changes to these terms</h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            If we update these terms, we will post the new text here and change the &ldquo;Last
            updated&rdquo; date at the top. Keeping on using the site after an update means you
            accept the new terms.
          </p>
        </div>
      </section>

      <section className="py-12">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">Contact</h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Questions or feedback about these terms are welcome by email.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <a
              href={`mailto:${contactEmail}`}
              className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              <Mail className="size-4 text-[var(--ink-muted)]" aria-hidden="true" />
              <span>{contactEmail}</span>
            </a>
            <a
              href={routeToPath('contact')}
              onClick={handleLinkClick('contact')}
              className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              Contact page
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
