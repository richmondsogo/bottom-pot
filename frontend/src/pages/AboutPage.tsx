import React from 'react';
import { ArrowRight, MinusIcon, PlusIcon } from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import { routeToPath, type AppRoute } from '../lib/router';

interface AboutPageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const PRINCIPLES = [
  {
    value: 'search-with-intent',
    heading: 'A search with intent',
    body: 'Start with a role, skill or keyword. Bottom Pot is designed around focused searches, not an endless feed.',
  },
  {
    value: 'clarity-before-application',
    heading: 'Clarity before the application',
    body: 'Work arrangement and country eligibility are different questions. We keep them separate so you can review both.',
  },
  {
    value: 'honest-information',
    heading: 'Honest information',
    body: 'We show details when the source provides them. We do not invent salaries, posting dates or work arrangements to fill a gap.',
  },
  {
    value: 'original-source',
    heading: 'The original source',
    body: "Bottom Pot helps you discover opportunities. The employer's own site is where you confirm the listing and apply.",
  },
  {
    value: 'useful-without-account',
    heading: 'Useful without an account',
    body: 'Search, save roles and organise your shortlist in your browser without creating a profile.',
  },
];

const FAQ_ITEMS: Array<{
  value: string;
  question: string;
  answer: string;
}> = [
  {
    value: 'what-is-bottom-pot',
    question: 'What is Bottom Pot?',
    answer:
      'Bottom Pot is a job search tool that brings listings from supported employer career pages and selected job boards into one searchable workspace. It helps you review opportunities and continue to the original listing.',
  },
  {
    value: 'different-from-job-board',
    question: 'How is Bottom Pot different from a traditional job board?',
    answer:
      'Bottom Pot is built around focused searches rather than an open-ended feed. It also separates work arrangement from applicant-country eligibility and links you to the original listing or application page.',
  },
  {
    value: 'why-search-first',
    question: 'Why do I have to search instead of browsing all jobs?',
    answer:
      'Bottom Pot is search-first by design. Start with a role, skill or keyword, then use filters to narrow the opportunities you want to review.',
  },
  {
    value: 'different-locations',
    question: 'Can I search for jobs in different locations?',
    answer:
      'Yes. Add a city or office hub to narrow your search. The “Where can you work from?” setting is separate: it checks the eligibility information available for your country.',
  },
  {
    value: 'remote-anywhere',
    question: 'Does remote mean I can work from anywhere?',
    answer:
      'Not always. Some remote jobs are limited to specific countries or regions. Check the applicant-country eligibility information and confirm the final requirements with the employer.',
  },
  {
    value: 'eligibility-labels',
    question: 'What do Eligible, Restricted and Unverified mean?',
    answer:
      'Eligible means the available listing information indicates your selected country may be accepted. Restricted means the listing indicates that country is excluded. Unverified means there is not enough reliable information to tell. These labels are guidance, not an employer decision.',
  },
  {
    value: 'where-listings-come-from',
    question: 'Where do the job listings come from?',
    answer:
      'Bottom Pot searches 10 hiring platforms and 3 selected job boards. The hiring platforms host career pages for individual employers; they are not 10 individual employers.',
  },
  {
    value: 'how-current',
    question: 'How current are the listings?',
    answer:
      "Source update methods and timing vary. Some supported employer boards are checked regularly, while other sources are searched when needed. Listings can change or close, so confirm the opportunity on the employer's site before applying.",
  },
  {
    value: 'salary-details',
    question: 'Are salary details shown for every job?',
    answer:
      'No. Salary appears when the source provides it. If a listing does not include pay information, Bottom Pot leaves it blank rather than guessing.',
  },
  {
    value: 'application-links',
    question: 'Where do the application links go?',
    answer:
      "They open the original employer listing or application page. You review the employer's requirements and complete the application on that site.",
  },
  {
    value: 'account-needed',
    question: 'Do I need an account?',
    answer:
      'No. You can search, save opportunities, track application stages and export your shortlist without signing up.',
  },
  {
    value: 'saved-jobs-sync',
    question: 'Are my saved jobs synced across devices?',
    answer:
      'No. Your shortlist and application stages are stored in the browser you use. They do not automatically sync to another device.',
  },
  {
    value: 'broken-listing',
    question: 'What should I do if a listing looks wrong or the link is broken?',
    answer:
      'Contact us with the job title, company and listing link. Include what looks incorrect so we can investigate it.',
  },
];

export const AboutPage: React.FC<AboutPageProps> = ({ onNavigate, onStartNewSearch }) => {
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
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Job search should start with what you&apos;re looking for.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Bottom Pot is a search-first job discovery tool. It brings opportunities from supported
            hiring platforms and selected job boards into one place, so you can focus on relevant
            roles and reach the original listing when you&apos;re ready.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-5 text-body text-[var(--ink-muted)] leading-relaxed">
          <p>
            Job hunting takes enough effort without sorting through unrelated listings, discovering
            location restrictions halfway through an application or chasing links that lead nowhere
            useful.
          </p>
          <p>
            We built Bottom Pot to make job discovery more focused. Search for the work you want,
            review the details available and continue to the employer&apos;s original listing when
            a role looks right.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-6">
          <h2 className="text-title font-semibold text-[var(--ink)]">What we build around</h2>
          <Accordion
            multiple
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)]"
          >
            {PRINCIPLES.map((principle) => (
              <AccordionItem
                key={principle.value}
                value={principle.value}
                className="border-[var(--border)]"
              >
                <AccordionTrigger className="px-5 py-4 max-md:min-h-11 rounded-lg hover:no-underline hover:bg-[var(--surface-hover)] transition-colors cursor-pointer *:data-[slot=accordion-trigger-icon]:hidden items-center gap-4 text-[var(--ink)]">
                  <span className="text-sm font-semibold text-[var(--ink)] pr-2">
                    {principle.heading}
                  </span>
                  <PlusIcon
                    className="text-[var(--ink-muted)] ml-auto size-4 shrink-0 group-aria-expanded/accordion-trigger:hidden"
                    aria-hidden="true"
                  />
                  <MinusIcon
                    className="text-[var(--ink-muted)] ml-auto hidden size-4 shrink-0 group-aria-expanded/accordion-trigger:inline"
                    aria-hidden="true"
                  />
                </AccordionTrigger>
                <AccordionContent
                  keepMounted
                  className="px-5 pb-4 pt-0 text-sm text-[var(--ink-muted)] leading-relaxed"
                >
                  <p>{principle.body}</p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-6">
          <h2 className="text-title font-semibold text-[var(--ink)]">
            Frequently asked questions
          </h2>
          <Accordion
            multiple
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)]"
          >
            {FAQ_ITEMS.map((item) => (
              <AccordionItem
                key={item.value}
                value={item.value}
                className="border-[var(--border)]"
              >
                <AccordionTrigger className="px-5 py-4 max-md:min-h-11 rounded-lg hover:no-underline hover:bg-[var(--surface-hover)] transition-colors cursor-pointer *:data-[slot=accordion-trigger-icon]:hidden items-center gap-4 text-[var(--ink)]">
                  <span className="text-sm font-semibold text-[var(--ink)] pr-2">
                    {item.question}
                  </span>
                  <PlusIcon
                    className="text-[var(--ink-muted)] ml-auto size-4 shrink-0 group-aria-expanded/accordion-trigger:hidden"
                    aria-hidden="true"
                  />
                  <MinusIcon
                    className="text-[var(--ink-muted)] ml-auto hidden size-4 shrink-0 group-aria-expanded/accordion-trigger:inline"
                    aria-hidden="true"
                  />
                </AccordionTrigger>
                <AccordionContent
                  keepMounted
                  className="px-5 pb-4 pt-0 text-sm text-[var(--ink-muted)] leading-relaxed"
                >
                  <p>{item.answer}</p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>

          <div className="flex flex-wrap items-center gap-3 pt-4">
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 max-md:h-11 max-md:min-w-11 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out motion-reduce:transform-none" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('product')}
              onClick={handleLinkClick('product')}
              className="h-10 max-md:h-11 max-md:min-w-11 px-5 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer"
            >
              How it works
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
