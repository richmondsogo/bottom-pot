import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface ProductPageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const STEPS = [
  {
    eyebrow: '01 · Search',
    title: 'Start with the work you want',
    body: 'Enter a job title, skill or keyword. Add a location, choose a work arrangement or narrow the date range when you need to.',
  },
  {
    eyebrow: '02 · Review',
    title: 'Check the details that matter',
    body: 'Review the employer, location, work arrangement, posting date and salary when those details are available. Choose your country to see the eligibility information found in the listing.',
  },
  {
    eyebrow: '03 · Apply',
    title: 'Continue with the employer',
    body: "Open the original job listing or application page. Confirm the employer's requirements and complete your application there.",
  },
];

const LISTING_DETAILS = [
  {
    title: 'Work arrangement',
    body: 'See whether a role is listed as remote, hybrid or in-person. If the listing does not say, we do not guess.',
  },
  {
    title: 'Applicant-country eligibility',
    body: 'Remote work can still have location restrictions. Select your country to review whether the available listing information indicates eligible, restricted or unverified.',
  },
  {
    title: 'Posting date and salary',
    body: 'See dates and pay information when the source provides them. Missing details stay blank or marked as not stated.',
  },
  {
    title: 'Original listing',
    body: 'Open the source listing or employer application page to confirm the details and apply.',
  },
];

const ELIGIBILITY_LABELS = [
  {
    label: 'Eligible',
    body: 'The available listing information indicates that applicants in your selected country may apply. Confirm the requirements with the employer.',
  },
  {
    label: 'Restricted',
    body: 'The available listing information indicates that your selected country is excluded.',
  },
  {
    label: 'Unverified',
    body: 'There is not enough reliable information in the listing to determine whether your country is accepted.',
  },
];

export const ProductPage: React.FC<ProductPageProps> = ({ onNavigate, onStartNewSearch }) => {
  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  const handleStartClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (onStartNewSearch) {
      onStartNewSearch();
    } else {
      onNavigate('search');
    }
  };

  return (
    <div className="w-full">
      {/* Intro */}
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Find the role. Check the details. Apply at the source.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Bottom Pot brings job listings from supported hiring platforms and selected job boards
            into one searchable workspace. Find roles that fit your search, review the information
            available and continue to the original listing.
          </p>
        </div>
      </section>

      {/* Three steps */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            A clearer way to search
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {STEPS.map((step, index) => (
              <div
                key={step.eyebrow}
                className={`rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5 bp-fade-up ${
                  index === 0 ? 'bp-delay-1' : index === 1 ? 'bp-delay-2' : 'bp-delay-3'
                }`}
              >
                <span className="font-mono text-xs text-[var(--ink-subtle)]">{step.eyebrow}</span>
                <h3 className="text-base font-semibold text-[var(--ink)]">{step.title}</h3>
                <p className="text-sm text-[var(--ink-muted)] leading-relaxed">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Listing details */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Useful details, without the guesswork
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {LISTING_DETAILS.map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2"
              >
                <h3 className="text-sm font-semibold text-[var(--ink)]">{item.title}</h3>
                <p className="text-sm text-[var(--ink-muted)] leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Eligibility explanation */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Understand the eligibility labels
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {ELIGIBILITY_LABELS.map((item) => (
              <div
                key={item.label}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2"
              >
                <h3 className="text-sm font-semibold text-[var(--ink)]">{item.label}</h3>
                <p className="text-sm text-[var(--ink-muted)] leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
            These labels are guidance based on the information available to Bottom Pot. The employer
            makes the final decision.
          </p>
        </div>
      </section>

      {/* Shortlist section */}
      <section className="py-14">
        <div className="page-shell flex flex-col gap-8">
          <div className="max-w-3xl">
            <h2 className="text-title font-semibold text-[var(--ink)]">
              Keep promising roles close
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-3 leading-relaxed">
              Save jobs to a private shortlist, keep track of your application stage and export your
              saved roles. Your shortlist stays in your browser. No account needed.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 max-md:h-11 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Search jobs</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out motion-reduce:transform-none" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="h-10 max-md:h-11 px-5 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer"
            >
              Explore sources
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
