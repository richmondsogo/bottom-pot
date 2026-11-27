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

const RULES = [
  {
    value: 'direct-apply',
    name: 'Direct apply links',
    detail: 'Every listing sends you straight to the company career page without middleman portals.',
    expansion:
      'Bottom Pot reads openings directly from employer hiring pages and strips aggregator referral parameters from outgoing links. You land straight on the company application form with no sign-up wall or redirect wrapper.',
  },
  {
    value: 'blank-beats-guessed',
    name: 'Blank beats guessed',
    detail: 'If a company leaves out salary or work policy, the field stays empty instead of showing an estimate.',
    expansion:
      'When a posting omits pay, location, or employment type, those cells remain empty rather than showing invented ranges. When work style is unstated in the listing, it is marked "Not stated" instead of being guessed as remote or on-site.',
  },
  {
    value: 'clear-country-rules',
    name: 'Clear country rules',
    detail: 'Location limits stay separate from remote badges and update for whichever country you pick.',
    expansion:
      'Pick any country in the search bar to check residence, visa, payroll, and hybrid attendance rules separately from how the team works. Listings from Nigerian job boards are treated as workable from Nigeria unless the posting explicitly excludes Nigeria. When a listing omits country rules, it stays marked unverified.',
  },
  {
    value: 'no-account-needed',
    name: 'No account needed',
    detail: 'Your shortlist, application stages, filters, and CSV or JSON exports stay private in your browser.',
    expansion:
      'Bottom Pot has no user accounts, login walls, or server-side candidate profiles. Your saved roles, application stages, active filters, and CSV or JSON exports are stored locally in your browser.',
  },
  {
    value: 'reliable-sources',
    name: 'Reliable sources only',
    detail: 'We maintain 13 dependable career platforms and Nigerian boards instead of padding the count with stale feeds.',
    expansion:
      'Searches query 10 company hiring platforms and 3 Nigerian job boards chosen for working apply links and verifiable dates. Listings older than 90 days move beneath an "Older postings" divider so older openings never appear newly posted.',
  },
];

const FAQ_ITEMS: Array<{
  value: string;
  question: string;
  answer: string;
  linkLabel?: string;
  linkRoute?: AppRoute;
}> = [
  {
    value: 'sources',
    question: 'Where do listings come from?',
    answer:
      'Listings come from 10 company hiring platforms (Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Teamtailor, Personio, Pinpoint, and Workday) and 3 Nigerian job boards (Jobberman, MyJobMag, and HotNigerianJobs). Alongside 28 curated tracked company boards, live search runs as a fallback when tracked boards return too few matches.',
  },
  {
    value: 'account',
    question: 'Do I need an account to use Bottom Pot?',
    answer:
      'No account is needed. Your saved shortlist, application stages, search filters, and CSV or JSON exports stay locally in your browser.',
  },
  {
    value: 'freshness',
    question: 'How fresh are the results?',
    answer:
      'Tracked company boards are polled on a 30-minute schedule alongside a daily scheduled refresh. Searches use a 5-minute in-memory result cache, a 12-hour search query cache, and a 24-hour listing detail cache, while roles older than 90 days move under an "Older postings" divider.',
  },
  {
    value: 'local-storage',
    question: 'What is stored locally in my browser?',
    answer:
      'Your browser stores your theme preference, search parameters, selected platforms, chosen country, active filters, sort order, up to 5 recent searches, clicked listing history (up to 1,000 entries), saved shortlist with application stages, and your last result snapshot (up to 3 MB).',
  },
  {
    value: 'analytics',
    question: 'What does analytics collect?',
    answer:
      'In production, Bottom Pot runs page analytics through Vercel to count visits to public pages. It is turned off in development, mock mode, automated test runs, and the admin area.',
    linkLabel: 'Read our privacy policy',
    linkRoute: 'privacy',
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
            Built for people tired of dead job links.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Looking for work already takes enough energy. You should not have to check if a posting
            is still open, guess what &ldquo;remote&rdquo; means, or click through three portals
            before reaching the application form.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-5 text-body text-[var(--ink-muted)] leading-relaxed">
          <p>
            Most job sites copy listings from the same company career pages. Along the way, pay
            bands disappear, posting dates get fuzzy, and country-locked jobs stay labeled remote
            until page two of the form.
          </p>
          <p>
            Bottom Pot reads straight from company hiring pages and Nigerian job boards instead.
            Work style stays separate from country rules, posting dates stay honest, and every apply
            button takes you directly to the employer.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-6">
          <h2 className="text-title font-semibold text-[var(--ink)]">Five rules we stick to</h2>
          <Accordion
            multiple
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)]"
          >
            {RULES.map((rule) => (
              <AccordionItem
                key={rule.value}
                value={rule.value}
                className="border-[var(--border)]"
              >
                <AccordionTrigger className="px-5 py-4 max-md:min-h-11 rounded-lg hover:no-underline hover:bg-[var(--surface-hover)] transition-colors cursor-pointer *:data-[slot=accordion-trigger-icon]:hidden items-center gap-4 text-[var(--ink)]">
                  <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-6 pr-2 flex-1 min-w-0">
                    <span className="text-sm font-semibold text-[var(--ink)] sm:w-48 shrink-0">
                      {rule.name}
                    </span>
                    <span className="text-sm font-normal text-[var(--ink-muted)] leading-relaxed">
                      {rule.detail}
                    </span>
                  </div>
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
                  <p className="sm:pl-54">{rule.expansion}</p>
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
                  {item.linkRoute && item.linkLabel && (
                    <p className="mt-2">
                      <a
                        href={routeToPath(item.linkRoute)}
                        onClick={handleLinkClick(item.linkRoute)}
                        className="underline underline-offset-4 decoration-[var(--border-strong)] text-[var(--ink)] hover:text-[var(--ink-muted)] transition-colors"
                      >
                        {item.linkLabel}
                      </a>
                    </p>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>

          <div className="flex flex-wrap items-center gap-3 pt-4">
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 max-md:h-11 max-md:min-w-11 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('product')}
              onClick={handleLinkClick('product')}
              className="h-10 max-md:h-11 max-md:min-w-11 px-5 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
            >
              How it works
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
