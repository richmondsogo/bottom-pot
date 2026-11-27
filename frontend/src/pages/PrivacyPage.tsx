import React from 'react';
import { Mail } from 'lucide-react';
import { DEFAULT_CONTACT_EMAIL, getConfiguredContactEmail } from '../lib/contactConfig';
import { routeToPath, type AppRoute } from '../lib/router';

export interface PrivacyPageProps {
  onNavigate?: (route: AppRoute) => void;
  contactEmailOverride?: string | null;
}

const LAST_UPDATED = 'November 27, 2026';

export const PrivacyPage: React.FC<PrivacyPageProps> = ({
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
            Privacy Policy
          </h1>
          <p className="text-sm text-[var(--ink-subtle)] mt-3">
            Last updated: {LAST_UPDATED}
          </p>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            This page explains in plain words what Bottom Pot receives when you search, what stays on
            your device, and which outside services help run the site.
          </p>

          <div
            data-testid="privacy-summary-box"
            className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col gap-3"
          >
            <h2 className="text-sm font-semibold text-[var(--ink)]">In plain words</h2>
            <ul className="list-disc pl-5 space-y-1.5 text-sm text-[var(--ink-muted)] leading-relaxed">
              <li>You do not need an account, password, or email to search or save jobs.</li>
              <li>We do not set visitor cookies when you browse or search.</li>
              <li>Your saved jobs, stages, filters, and recent searches stay on your device in your browser.</li>
              <li>You can email us anytime if you have a privacy question or want help.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Who runs Bottom Pot and how to reach us
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Bottom Pot runs this job search website. If you have questions about this page or how
            your information is handled, email us directly. Feedback is always welcome by email.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <a
              href={`mailto:${contactEmail}`}
              className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none"
            >
              <Mail className="size-4 text-[var(--ink-muted)]" aria-hidden="true" />
              <span>{contactEmail}</span>
            </a>
            <a
              href={routeToPath('contact')}
              onClick={handleLinkClick('contact')}
              className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none"
            >
              Contact page
            </a>
          </div>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-4">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            What we collect when you use the site
          </h2>
          <ul className="list-disc pl-5 space-y-2.5 text-body text-[var(--ink-muted)] leading-relaxed">
            <li>
              <strong className="font-semibold text-[var(--ink)]">Search details:</strong> When you
              search, our server receives the job title, location, work style, post age, selected job
              sources, and the country you chose.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Country checks:</strong> When you
              pick or change a country in results, our server checks the country code against the
              listed jobs and returns labels without saving that check.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Internet address for rate limits:</strong>{' '}
              Our server reads your internet address in memory to block too many requests in a short
              time. We do not save your internet address into our database tables.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Server logs and caches:</strong>{' '}
              Our server writes search words, errors, and source timings to runtime logs. It also
              keeps temporary search and job-page caches to avoid hitting job sites too hard.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Email and problem reports:</strong>{' '}
              No form on the website collects your email or name. Clicking our email link or using
              &ldquo;Report a problem with this listing&rdquo; opens your own email app. Problem
              reports prefill only the job details on screen, and nothing is sent until you send
              the email yourself.
            </li>
          </ul>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-4">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            What stays on your device and how to clear it
          </h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            To keep your place without an account, Bottom Pot saves a few items on your device in
            your browser:
          </p>
          <ul className="list-disc pl-5 space-y-2 text-body text-[var(--ink-muted)] leading-relaxed">
            <li>Your light or dark theme choice.</li>
            <li>Your last search fields, selected job sources, filters, and sort order.</li>
            <li>Up to 5 recent searches.</li>
            <li>Your saved jobs list and job stage choices, such as saved or applied.</li>
            <li>Your last list of search results, up to a small size limit in your browser.</li>
            <li>Up to 1,000 job links you already clicked so read roles look marked.</li>
          </ul>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            We do not set cookies for ordinary visitors. Only the separate admin area sets a sign-in
            cookie for site admins.
          </p>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            You can clear your recent searches, saved jobs, or last search results inside the search
            workspace. You can also delete all saved site data at any time through your browser
            settings.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-4">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Services that help us run Bottom Pot
          </h2>
          <ul className="list-disc pl-5 space-y-2.5 text-body text-[var(--ink-muted)] leading-relaxed">
            <li>
              <strong className="font-semibold text-[var(--ink)]">Vercel:</strong> Hosts our website
              and server functions, so normal web requests pass through Vercel. In live production
              only, Bottom Pot also runs page analytics through Vercel on public pages.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Neon:</strong> Hosts the cloud
              database that holds public company boards, public job listings, and temporary search
              caches.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Serper:</strong> When tracked
              company boards do not return enough matches, Serper gets the job search text,
              location, work style, and post age to find more public postings. It does not get your
              internet address or chosen applicant country.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Logo.dev:</strong> When a listing
              is missing a company logo and logo fallback is turned on, your browser requests the
              company logo image straight from Logo.dev using the company web domain.
            </li>
            <li>
              <strong className="font-semibold text-[var(--ink)]">Job sites and employers:</strong>{' '}
              Our server reads public job pages from hiring platforms and Nigerian job boards. When
              you open an application link or source proof link, you go to that outside site under
              its own privacy policy.
            </li>
          </ul>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            Our fonts are built right into the app files. Public pages do not load outside fonts or
            outside ad scripts.
          </p>
        </div>
      </section>

      <section className="py-12 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-4">
          <h2 className="text-title font-semibold text-[var(--ink)]">Your choices</h2>
          <ul className="list-disc pl-5 space-y-2 text-body text-[var(--ink-muted)] leading-relaxed">
            <li>Use Bottom Pot without creating a profile or sharing your email.</li>
            <li>Clear saved jobs, recent searches, or cached results in the workspace anytime.</li>
            <li>Clear or block browser storage in your browser settings.</li>
            <li>Email us anytime with questions about what this site stores.</li>
          </ul>
        </div>
      </section>

      <section className="py-12">
        <div className="page-shell max-w-3xl flex flex-col gap-3">
          <h2 className="text-title font-semibold text-[var(--ink)]">Changes to this policy</h2>
          <p className="text-body text-[var(--ink-muted)] leading-relaxed">
            If we change how Bottom Pot handles your data, we will update this page and change the
            &ldquo;Last updated&rdquo; date at the top.
          </p>
        </div>
      </section>
    </div>
  );
};
