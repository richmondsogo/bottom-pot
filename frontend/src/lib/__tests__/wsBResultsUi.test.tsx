import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ResultsTable } from '../../components/ResultsTable';
import { ResultsCards } from '../../components/ResultsCards';
import { DetailSheet } from '../../components/DetailSheet';
import { CompactSearchBar } from '../../components/CompactSearchBar';
import { NoResultsState } from '../../components/States';
import { normalizeJob, EMPTY_VALUE } from '../normalize';
import { buildMobileCardMeta } from '../mobileCardMeta';
import type { JobListing } from '../../types';

function makeJob(overrides: Partial<JobListing> = {}): JobListing {
  return {
    id: 'greenhouse:acme:1',
    title: 'Backend Engineer',
    company: 'Acme Engineering',
    location: 'Lagos, Nigeria',
    work_model: 'remote',
    employment_type: 'full_time',
    salary: null,
    posted_at: '2026-11-20T12:00:00Z',
    apply_url: 'https://boards.greenhouse.io/acme/jobs/1',
    source_url: 'https://boards.greenhouse.io/acme/jobs/1',
    provider: 'greenhouse',
    data_source: 'api',
    ...overrides,
  };
}

describe('WS-B Results UI polish, source visibility, saved stamp, diamond-miner empty state, and Nigerian eligibility', () => {
  const fixedNow = new Date('2026-11-25T12:00:00Z').getTime();

  it('B1: hides source tags in user mode across ResultsTable, ResultsCards, and DetailSheet, while keeping them in admin mode', () => {
    const job = normalizeJob(makeJob(), fixedNow);

    // Default / user mode hides provider slugs and "via {provider}"
    const userTableDefault = renderToStaticMarkup(
      <ResultsTable
        jobs={[job]}
        sortField={null}
        sortAsc={true}
        onSort={() => {}}
        selectedJobId={null}
        onSelectJob={() => {}}
        activeRowIndex={-1}
      />
    );
    const userTableExplicit = renderToStaticMarkup(
      <ResultsTable
        jobs={[job]}
        sortField={null}
        sortAsc={true}
        onSort={() => {}}
        selectedJobId={null}
        onSelectJob={() => {}}
        activeRowIndex={-1}
        mode="user"
      />
    );
    const userCardsDefault = renderToStaticMarkup(
      <ResultsCards
        jobs={[job]}
        sortField={null}
        selectedJobId={null}
        onSelectJob={() => {}}
      />
    );
    const g = globalThis as { __BOTTOM_POT_REPORT_PROBLEM_URL__?: unknown };
    const prevReportUrl = g.__BOTTOM_POT_REPORT_PROBLEM_URL__;
    g.__BOTTOM_POT_REPORT_PROBLEM_URL__ = 'https://github.com/richmondsogo/bottom-pot/issues/new';
    let userDetail = '';
    let adminDetail = '';
    try {
      userDetail = renderToStaticMarkup(
        <DetailSheet
          job={job}
          onClose={() => {}}
          onMarkVisited={() => {}}
          mode="user"
        />
      );
      adminDetail = renderToStaticMarkup(
        <DetailSheet
          job={job}
          onClose={() => {}}
          onMarkVisited={() => {}}
          mode="admin"
        />
      );
    } finally {
      if (prevReportUrl === undefined) {
        delete g.__BOTTOM_POT_REPORT_PROBLEM_URL__;
      } else {
        g.__BOTTOM_POT_REPORT_PROBLEM_URL__ = prevReportUrl;
      }
    }

    for (const html of [userTableDefault, userTableExplicit, userCardsDefault]) {
      expect(html).not.toContain('greenhouse');
      expect(html).not.toContain('Source:');
    }
    expect(userDetail).not.toContain('via greenhouse');
    expect(userDetail).not.toContain('· boards.greenhouse.io');
    expect(userDetail).toContain('Open application');
    expect(userDetail).toContain('data-testid="report-problem-link"');

    // Admin mode preserves source tags and verification trace
    const adminTable = renderToStaticMarkup(
      <ResultsTable
        jobs={[job]}
        sortField={null}
        sortAsc={true}
        onSort={() => {}}
        selectedJobId={null}
        onSelectJob={() => {}}
        activeRowIndex={-1}
        mode="admin"
      />
    );
    const adminCards = renderToStaticMarkup(
      <ResultsCards
        jobs={[job]}
        sortField={null}
        selectedJobId={null}
        onSelectJob={() => {}}
        mode="admin"
      />
    );

    expect(adminTable).toContain('greenhouse');
    expect(adminTable).toContain('title="Source: greenhouse"');
    expect(adminCards).toContain('greenhouse');
    expect(adminDetail).toContain('via greenhouse');
    expect(adminDetail).toContain('boards.greenhouse.io');
  });

  it('B2: removes "Saved <time> ago" stamp from CompactSearchBar while keeping shortlist summary', () => {
    const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
    const baseProps = {
      searchParams: { keywords: 'Backend Engineer', location: '', workModel: 'any', postAge: '7' },
      setSearchParams: () => {},
      onSubmit: () => {},
      selectedPlatforms: ['greenhouse'],
      setSelectedPlatforms: () => {},
      totalResults: 3,
      filteredCount: 3,
      metrics: null,
      savedTimestamp: fiveMinutesAgo,
      onEditSearch: () => {},
      onNewSearch: () => {},
      onRunAgain: () => {},
      onClearSaved: () => {},
    };

    const userHtml = renderToStaticMarkup(
      <CompactSearchBar {...baseProps} mode="user" />
    );
    expect(userHtml).toContain('3 roles · Backend Engineer');
    expect(userHtml).not.toMatch(/Saved\s+\d+[mhd]\s+ago/i);

    const shortlistHtml = renderToStaticMarkup(
      <CompactSearchBar {...baseProps} mode="user" onlySavedJobs={true} />
    );
    expect(shortlistHtml).toContain('3 saved roles');
    expect(shortlistHtml).not.toMatch(/Saved\s+\d+[mhd]\s+ago/i);

    const adminHtml = renderToStaticMarkup(
      <CompactSearchBar {...baseProps} mode="admin" />
    );
    expect(adminHtml).not.toMatch(/Saved\s+\d+[mhd]\s+ago/i);
  });

  it('B3: renders diamond-miner empty state only for completed user searches with 0 results, and handles missing asset cleanly', () => {
    const baseHandlers = {
      onWidenDateRange: () => {},
      onClearFilters: () => {},
      onNewSearch: () => {},
    };

    const memeHtml = renderToStaticMarkup(
      <NoResultsState
        {...baseHandlers}
        mode="user"
        incomplete={false}
        budgetExhausted={false}
        hasMemeAsset={true}
      />
    );
    expect(memeHtml).toContain('data-testid="no-results-diamond-state"');
    expect(memeHtml).toContain('0 roles matched this search');
    expect(memeHtml).toContain('Until death,');
    expect(memeHtml).toContain('all defeat is psychological');
    expect(memeHtml).toContain('bg-[var(--surface-selected)]');
    expect(memeHtml).toContain('src="/easter/diamondmeme.jpg"');
    expect(memeHtml).toContain('alt="Miner turning back one swing away from a wall of diamonds"');
    expect(memeHtml).toContain('rounded-md border border-[var(--border)] bg-[var(--surface-subtle)]');
    expect(memeHtml).toContain('put the pickaxe down one swing before the diamonds. Broaden the title, clear filters, or try a nearby role.');
    expect(memeHtml).toContain('Widen date range');
    expect(memeHtml).toContain('Clear filters');
    expect(memeHtml).toContain('New search');
    expect(memeHtml).not.toContain('\u2014');

    // Missing asset renders text-only cleanly with zero <img>
    const missingAssetHtml = renderToStaticMarkup(
      <NoResultsState
        {...baseHandlers}
        mode="user"
        incomplete={false}
        budgetExhausted={false}
        hasMemeAsset={false}
      />
    );
    expect(missingAssetHtml).toContain('data-testid="no-results-diamond-state"');
    expect(missingAssetHtml).toContain('all defeat is psychological');
    expect(missingAssetHtml).not.toContain('<img');
    expect(missingAssetHtml).not.toContain('/easter/diamondmeme.jpg');

    // Busy, budget-exhausted, and admin states stay unchanged (no diamond meme)
    const busyHtml = renderToStaticMarkup(
      <NoResultsState {...baseHandlers} mode="user" incomplete={true} hasMemeAsset={true} />
    );
    expect(busyHtml).toContain('Search is busy right now');
    expect(busyHtml).not.toContain('diamondmeme.jpg');
    expect(busyHtml).not.toContain('all defeat is psychological');

    const budgetHtml = renderToStaticMarkup(
      <NoResultsState {...baseHandlers} mode="user" incomplete={false} budgetExhausted={true} hasMemeAsset={true} />
    );
    expect(budgetHtml).toContain('No open positions matched your search');
    expect(budgetHtml).not.toContain('diamondmeme.jpg');
    expect(budgetHtml).not.toContain('all defeat is psychological');

    const adminHtml = renderToStaticMarkup(
      <NoResultsState {...baseHandlers} mode="admin" incomplete={false} budgetExhausted={false} hasMemeAsset={true} />
    );
    expect(adminHtml).toContain('No job postings matched your criteria');
    expect(adminHtml).not.toContain('diamondmeme.jpg');
    expect(adminHtml).not.toContain('all defeat is psychological');
  });

  it('B4: displays backend Nigerian-board applicant_assessment eligibility cleanly without Eligibility unverified or restriction text', () => {
    const ngBoardJobs = [
      makeJob({
        id: 'jobberman:paystack:1',
        provider: 'jobberman',
        data_source: 'scrape',
        title: 'Operations Analyst',
        company: 'Paystack',
        location: 'Lagos, Nigeria',
        work_model: null,
        apply_url: 'https://www.jobberman.com/listings/ops-1',
        source_url: 'https://www.jobberman.com/listings/ops-1',
        eligibility: {
          objective_scope_label: 'Nigeria eligible',
          nigeria_eligible: true,
          applicant_assessment: {
            applicant_country_code: 'NG',
            applicant_country_name: 'Nigeria',
            status: 'eligible',
            reason: 'Listed on Nigerian job board without foreign residency restrictions.',
            work_arrangement: 'unknown',
            summary_label: 'Nigeria eligible',
          },
        },
      }),
      makeJob({
        id: 'myjobmag:moniepoint:2',
        provider: 'myjobmag',
        data_source: 'scrape',
        title: 'Remote Customer Engineer',
        company: 'Moniepoint',
        location: 'Nigeria',
        work_model: 'remote',
        apply_url: 'https://www.myjobmag.com/job/remote-ce-2',
        source_url: 'https://www.myjobmag.com/job/remote-ce-2',
        eligibility: {
          objective_scope_label: 'Nigeria eligible',
          nigeria_eligible: true,
          applicant_assessment: {
            applicant_country_code: 'NG',
            applicant_country_name: 'Nigeria',
            status: 'eligible',
            reason: 'Remote role listed on Nigerian job board.',
            work_arrangement: 'remote',
            summary_label: 'Remote · Nigeria eligible',
          },
        },
      }),
    ];

    for (const raw of ngBoardJobs) {
      const normalized = normalizeJob(raw, fixedNow, 'NG');
      const tableHtml = renderToStaticMarkup(
        <ResultsTable
          jobs={[normalized]}
          sortField={null}
          sortAsc={true}
          onSort={() => {}}
          selectedJobId={null}
          onSelectJob={() => {}}
          activeRowIndex={-1}
        />
      );
      const cardsHtml = renderToStaticMarkup(
        <ResultsCards
          jobs={[normalized]}
          sortField={null}
          selectedJobId={null}
          onSelectJob={() => {}}
        />
      );
      const detailHtml = renderToStaticMarkup(
        <DetailSheet
          job={normalized}
          onClose={() => {}}
          onMarkVisited={() => {}}
          applicantCountry="NG"
          mode="user"
        />
      );
      const meta = buildMobileCardMeta(normalized);

      expect(meta.eligibilityText).toBe('Nigeria eligible');
      for (const html of [tableHtml, cardsHtml, detailHtml]) {
        expect(html).toContain('Nigeria eligible');
        expect(html).not.toContain('Eligibility unverified');
        expect(html).not.toContain('Restricted');
        expect(html).not.toContain('Not eligible');
      }
      expect(detailHtml).toContain('Eligible from Nigeria');
    }
  });

  it('B5: preserves normalize.ts unknown-value behavior and renders consistent unknown/work-model values across views and DetailSheet', () => {
    const unknownJob = normalizeJob(
      makeJob({
        id: 'unknown:1',
        location: null,
        work_model: null,
        salary: null,
        employment_type: null,
        posted_at: null,
        eligibility: null,
      }),
      fixedNow
    );
    expect(unknownJob.displayLocation).toBe(EMPTY_VALUE);
    expect(unknownJob.displayWorkModel).toBeNull();

    const unknownDetailHtml = renderToStaticMarkup(
      <DetailSheet
        job={unknownJob}
        onClose={() => {}}
        onMarkVisited={() => {}}
        mode="user"
      />
    );
    const metaHeaderMatch = unknownDetailHtml.match(
      /<div data-testid="detail-meta-header"[^>]*>([\s\S]*?)<\/div>/
    );
    expect(metaHeaderMatch).not.toBeNull();
    const metaHeaderHtml = metaHeaderMatch?.[1] || '';
    expect(metaHeaderHtml).not.toContain('data-testid="detail-location"');
    expect(metaHeaderHtml).not.toContain('lucide-map-pin');
    expect(metaHeaderHtml).not.toContain(EMPTY_VALUE);
    expect(metaHeaderHtml).toContain('data-testid="detail-work-model-not-stated"');
    expect(metaHeaderHtml).toContain('Not stated');

    // All three views agree on every work_model spelling including onsite / on-site / in person
    const spellingCases: Array<[string | null, string]> = [
      ['remote', 'Remote'],
      ['REMOTE', 'Remote'],
      ['hybrid', 'Hybrid'],
      ['in_person', 'In-person'],
      ['in person', 'In-person'],
      ['in-person', 'In-person'],
      ['onsite', 'In-person'],
      ['on-site', 'In-person'],
      ['on site', 'In-person'],
      ['unknown', 'Not stated'],
      [null, 'Not stated'],
    ];

    for (const [rawModel, expectedLabel] of spellingCases) {
      const normalized = normalizeJob(makeJob({ id: `wm:${rawModel}`, work_model: rawModel }), fixedNow);
      const tHtml = renderToStaticMarkup(
        <ResultsTable
          jobs={[normalized]}
          sortField={null}
          sortAsc={true}
          onSort={() => {}}
          selectedJobId={null}
          onSelectJob={() => {}}
          activeRowIndex={-1}
        />
      );
      const cHtml = renderToStaticMarkup(
        <ResultsCards
          jobs={[normalized]}
          sortField={null}
          selectedJobId={null}
          onSelectJob={() => {}}
        />
      );
      const dHtml = renderToStaticMarkup(
        <DetailSheet job={normalized} onClose={() => {}} onMarkVisited={() => {}} />
      );
      for (const html of [tHtml, cHtml, dHtml]) {
        expect(html).toContain(expectedLabel);
      }
    }
  });
});
