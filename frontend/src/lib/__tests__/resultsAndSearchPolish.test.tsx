import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ResultsTable } from '../../components/ResultsTable';
import { ResultsCards } from '../../components/ResultsCards';
import { SearchForm } from '../../components/SearchForm';
import { CountryCombobox } from '../../components/CountryCombobox';
import { formatSalaryParts, normalizeJob } from '../normalize';
import { buildMobileCardMeta, handleMobileQuickSaveClick } from '../mobileCardMeta';
import { ALL_PLATFORMS } from '../constants';
import type { JobListing } from '../../types';

function makeJob(overrides: Partial<JobListing> = {}): JobListing {
  return {
    id: 'job:1',
    title: 'Software Engineer',
    company: 'Acme Engineering',
    location: 'Madrid, Spain',
    work_model: null,
    employment_type: 'full_time',
    salary: null,
    posted_at: '2026-11-20T12:00:00Z',
    apply_url: 'https://jobs.lever.co/acme/1',
    source_url: 'https://jobs.lever.co/acme/1',
    provider: 'lever',
    data_source: 'api',
    ...overrides,
  };
}

describe('Run 1 search & results polish', () => {
  it('covers work_model x eligibility truth table across ResultsTable and ResultsCards', () => {
    const fixedNow = new Date('2026-11-25T12:00:00Z').getTime();

    const cases: Array<{
      name: string;
      job: JobListing;
      country: string;
      expectNotStated: boolean;
      expectedWorkBadge?: string;
      expectedEligText: string | null;
    }> = [
      {
        name: 'null work_model and null eligibility',
        job: makeJob({ id: 'c1', work_model: null, eligibility: null, location: null }),
        country: '',
        expectNotStated: true,
        expectedEligText: null,
      },
      {
        name: 'null work_model with allowed_codes=[ES] and no applicant country',
        job: makeJob({
          id: 'c2',
          work_model: null,
          eligibility: {
            classification: 'country_restricted',
            allowed_country_codes: ['ES'],
            residence_restriction_confirmed: true,
          },
        }),
        country: '',
        expectNotStated: true,
        expectedEligText: 'Spain only',
      },
      {
        name: 'null work_model with allowed_codes=[ES] evaluated for NG (restricted)',
        job: makeJob({
          id: 'c3',
          work_model: null,
          eligibility: {
            classification: 'country_restricted',
            allowed_country_codes: ['ES'],
            residence_restriction_confirmed: true,
          },
        }),
        country: 'NG',
        expectNotStated: true,
        expectedEligText: 'Restricted · Spain only',
      },
      {
        name: 'null work_model with allowed_codes=[ES] evaluated for ES (eligible)',
        job: makeJob({
          id: 'c4',
          work_model: null,
          eligibility: {
            classification: 'country_restricted',
            allowed_country_codes: ['ES'],
            residence_restriction_confirmed: true,
          },
        }),
        country: 'ES',
        expectNotStated: true,
        expectedEligText: 'Spain only',
      },
      {
        name: 'remote work_model with null eligibility and NG selected',
        job: makeJob({ id: 'c5', work_model: 'remote', eligibility: null, location: 'Remote' }),
        country: 'NG',
        expectNotStated: false,
        expectedWorkBadge: 'Remote',
        expectedEligText: 'Eligibility unverified',
      },
      {
        name: 'remote work_model with worldwide eligibility',
        job: makeJob({
          id: 'c6',
          work_model: 'remote',
          location: 'Remote (Worldwide)',
          eligibility: { classification: 'worldwide', global_remote_explicit: true },
        }),
        country: 'NG',
        expectNotStated: false,
        expectedWorkBadge: 'Remote',
        expectedEligText: 'Worldwide',
      },
      {
        name: 'hybrid work_model with NG local eligibility',
        job: makeJob({
          id: 'c7',
          work_model: 'hybrid',
          location: 'Lagos, Nigeria',
          eligibility: {
            classification: 'onsite_or_hybrid_local',
            physical_location_country: 'Nigeria',
            physical_location_country_code: 'NG',
            hybrid_attendance_confirmed: true,
          },
        }),
        country: 'NG',
        expectNotStated: false,
        expectedWorkBadge: 'Hybrid',
        expectedEligText: 'Lagos, Nigeria',
      },
      {
        name: 'in_person work_model with US local eligibility evaluated for NG',
        job: makeJob({
          id: 'c8',
          work_model: 'in_person',
          location: 'New York, NY',
          eligibility: {
            classification: 'onsite_or_hybrid_local',
            physical_location_country: 'United States',
            physical_location_country_code: 'US',
          },
        }),
        country: 'NG',
        expectNotStated: false,
        expectedWorkBadge: 'In-person',
        expectedEligText: 'Restricted · New York, NY',
      },
      {
        name: 'unrecognized work_model falls back to Not stated',
        job: makeJob({ id: 'c9', work_model: 'flexible', eligibility: null }),
        country: '',
        expectNotStated: true,
        expectedEligText: null,
      },
    ];

    for (const tc of cases) {
      const normalized = normalizeJob(tc.job, fixedNow, tc.country);
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

      for (const html of [tableHtml, cardsHtml]) {
        if (tc.expectNotStated) {
          expect(html, `${tc.name}`).toContain('data-testid="work-model-not-stated"');
          expect(html, `${tc.name}`).toContain('Not stated');
          expect(html, `${tc.name}`).toContain('text-[var(--ink-subtle)]');
          expect(html, `${tc.name}`).not.toContain('—');
        } else {
          expect(html, `${tc.name}`).not.toContain('data-testid="work-model-not-stated"');
          expect(html, `${tc.name}`).toContain(tc.expectedWorkBadge!);
        }

        if (tc.expectedEligText) {
          expect(html, `${tc.name}`).toContain(tc.expectedEligText);
        } else {
          expect(html, `${tc.name}`).not.toContain('Eligibility unverified');
          expect(html, `${tc.name}`).not.toContain('Restricted');
        }
      }
    }
  });

  it('splits structured salary into range + subtle period and wraps raw salary strings without dropping characters', () => {
    expect(formatSalaryParts({ minimum: 120000, maximum: 180000, currency: 'USD', period: 'year' })).toEqual({
      range: 'USD 120,000 – 180,000',
      period: '/ year',
      full: 'USD 120,000 – 180,000 / year',
    });
    expect(formatSalaryParts({ minimum: 90000, maximum: null, currency: 'EUR', period: null })).toEqual({
      range: 'EUR 90,000+',
      period: null,
      full: 'EUR 90,000+',
    });
    const rawSalary = 'NGN 1,200,000 - 1,800,000 / month + health allowance';
    expect(formatSalaryParts(rawSalary)).toEqual({
      range: rawSalary,
      period: null,
      full: rawSalary,
    });
    expect(formatSalaryParts(null)).toBeNull();
    expect(formatSalaryParts('Not listed')).toBeNull();

    const fixedNow = new Date('2026-11-25T12:00:00Z').getTime();
    const structuredJob = normalizeJob(
      makeJob({
        id: 'sal-1',
        company: 'Very Long International Infrastructure Holdings Limited Nigeria',
        provider: 'greenhouse',
        salary: { minimum: 210000, maximum: 285000, currency: 'USD', period: 'year' },
      }),
      fixedNow
    );
    const rawJob = normalizeJob(
      makeJob({
        id: 'sal-2',
        company: 'Acme Global',
        provider: 'jobberman',
        salary: rawSalary,
      }),
      fixedNow
    );

    const tableHtml = renderToStaticMarkup(
      <ResultsTable
        jobs={[structuredJob, rawJob]}
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
        jobs={[structuredJob, rawJob]}
        sortField={null}
        selectedJobId={null}
        onSelectJob={() => {}}
      />
    );

    for (const html of [tableHtml, cardsHtml]) {
      expect(html).toContain('USD 210,000 – 285,000');
      expect(html).toContain('/ year');
      expect(html).toContain('title="USD 210,000 – 285,000 / year"');
      expect(html).toContain(rawSalary);
      expect(html).toContain(`title="${rawSalary}"`);
      expect(html).toContain('line-clamp-2');
      expect(html).toContain('break-words');
      expect(html).toContain('Very Long International Infrastructure Holdings Limited Nigeria');
      expect(html).toContain('greenhouse');
    }
  });

  it('updates SearchForm heading, keeps submit button copy, and shows active filter summary + Reset filters', () => {
    const ninePlatforms = ALL_PLATFORMS.slice(0, 9).map((p) => p.id);
    const html = renderToStaticMarkup(
      <SearchForm
        searchParams={{ keywords: 'Engineer', location: '', workModel: 'any', postAge: '7' }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={ninePlatforms}
        setSelectedPlatforms={() => {}}
      />
    );

    expect(html).toContain('What role are you looking for?');
    expect(html).toContain('<span>Search jobs</span>');
    expect(html).toContain('data-testid="filters-active-summary"');
    expect(html).toContain(`Platforms: 9 of ${ALL_PLATFORMS.length}`);
    expect(html).toContain('Reset filters');

    const defaultHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{ keywords: '', location: '', workModel: 'any', postAge: '7' }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={ALL_PLATFORMS.map((p) => p.id)}
        setSelectedPlatforms={() => {}}
      />
    );
    expect(defaultHtml).toContain(`All ${ALL_PLATFORMS.length} platforms · Past 7 days`);
    expect(defaultHtml).not.toContain('Reset filters');
  });

  it('renders "Any country" instead of "Any country (not set)" in CountryCombobox', () => {
    const html = renderToStaticMarkup(
      <CountryCombobox value="" onChange={() => {}} />
    );
    expect(html).toContain('Any country');
    expect(html).not.toContain('Any country (not set)');
  });

  it('renders /app-only scope caption, conditional recent searches, and shortened placeholder on SearchForm', () => {
    const baseProps = {
      searchParams: { keywords: '', location: '', workModel: 'any', postAge: '7' },
      setSearchParams: () => {},
      onSubmit: () => {},
      selectedPlatforms: ALL_PLATFORMS.map((p) => p.id),
      setSelectedPlatforms: () => {},
      applicantCountry: '',
      onChangeApplicantCountry: () => {},
    };

    const standaloneEmpty = renderToStaticMarkup(
      <SearchForm
        {...baseProps}
        variant="default"
        recentSearches={[]}
        onSelectRecentSearch={() => {}}
        onClearRecentSearches={() => {}}
      />
    );
    expect(standaloneEmpty).toContain('placeholder="e.g. Backend, Product Designer"');
    expect(standaloneEmpty).toContain('data-testid="search-scope-caption"');
    expect(standaloneEmpty).toContain(`${ALL_PLATFORMS.length} company hiring boards`);
    expect(standaloneEmpty).not.toContain('data-testid="recent-searches-strip"');

    const presets = [
      { id: 'backend||remote', keywords: 'Backend', location: '', workModel: 'remote', postAge: '7', timestamp: 10 },
      { id: 'designer|lagos|any', keywords: 'Designer', location: 'Lagos', workModel: 'any', postAge: '7', timestamp: 9 },
    ];
    const standaloneWithRecent = renderToStaticMarkup(
      <SearchForm
        {...baseProps}
        variant="default"
        recentSearches={presets}
        onSelectRecentSearch={() => {}}
        onClearRecentSearches={() => {}}
      />
    );
    expect(standaloneWithRecent).toContain('data-testid="recent-searches-strip"');
    expect(standaloneWithRecent).toContain('Recent searches');
    expect(standaloneWithRecent).toContain('Backend · Remote');
    expect(standaloneWithRecent).toContain('Designer · Lagos');
    expect(standaloneWithRecent).toContain('aria-label="Clear recent searches"');

    const embeddedWithRecent = renderToStaticMarkup(
      <SearchForm
        {...baseProps}
        variant="embedded"
        recentSearches={presets}
        onSelectRecentSearch={() => {}}
        onClearRecentSearches={() => {}}
      />
    );
    expect(embeddedWithRecent).toContain('placeholder="e.g. Backend, Product Designer"');
    expect(embeddedWithRecent).not.toContain('data-testid="search-scope-caption"');
    expect(embeddedWithRecent).not.toContain('data-testid="recent-searches-strip"');
  });

  it('deduplicates mobile row metadata without hiding distinct restrictions and keeps quick-save isolated', () => {
    const fixedNow = new Date('2026-11-25T12:00:00Z').getTime();

    // 1. Remote + "Remote (United States)" + "US only" keeps US only and omits redundant location
    const usOnlyRemote = normalizeJob(
      makeJob({
        id: 'dedup-us',
        work_model: 'remote',
        location: 'Remote (United States)',
        eligibility: {
          classification: 'country_restricted',
          allowed_country_codes: ['US'],
          allowed_residence_countries: ['United States'],
          residence_restriction_confirmed: true,
        },
      }),
      fixedNow
    );
    const usMeta = buildMobileCardMeta(usOnlyRemote);
    expect(usMeta.locationText).toBeNull();
    expect(usMeta.eligibilityText).toBe('US only');
    expect(usMeta.combinedMetaParts.map((p) => p.text)).toEqual(['US only']);

    // 2. Remote + "Tokyo / Remote (Japan)" + "Japan only" preserves Tokyo and Japan only
    const japanCityRemote = normalizeJob(
      makeJob({
        id: 'dedup-jp',
        work_model: 'remote',
        location: 'Tokyo / Remote (Japan)',
        eligibility: {
          classification: 'country_restricted',
          allowed_country_codes: ['JP'],
          allowed_residence_countries: ['Japan'],
          residence_restriction_confirmed: true,
        },
      }),
      fixedNow
    );
    const jpMeta = buildMobileCardMeta(japanCityRemote);
    expect(jpMeta.combinedMetaParts.map((p) => p.text)).toEqual(['Tokyo', 'Japan only']);

    // 3. In-person "New York, NY" evaluated for NG shows "Restricted · New York, NY" once
    const nyRestricted = normalizeJob(
      makeJob({
        id: 'dedup-ny',
        work_model: 'in_person',
        location: 'New York, NY',
        eligibility: {
          classification: 'onsite_or_hybrid_local',
          physical_location_country: 'United States',
          physical_location_country_code: 'US',
        },
      }),
      fixedNow,
      'NG'
    );
    const nyMeta = buildMobileCardMeta(nyRestricted);
    expect(nyMeta.locationText).toBeNull();
    expect(nyMeta.combinedMetaParts.map((p) => p.text)).toEqual(['Restricted · New York, NY']);

    // 4. Bare "Remote" alongside Remote badge drops redundant location text while preserving eligibility state
    const bareRemote = normalizeJob(
      makeJob({ id: 'dedup-bare', work_model: 'remote', location: 'Remote', eligibility: null }),
      fixedNow
    );
    const bareMeta = buildMobileCardMeta(bareRemote);
    expect(bareMeta.locationText).toBeNull();
    expect(bareMeta.combinedMetaParts.map((p) => p.text)).toEqual(['Eligibility unverified']);

    // 5. ResultsCards renders 4-line anatomy: quick-save button, no trailing arrow icon, dedicated salary line
    const cardsHtml = renderToStaticMarkup(
      <ResultsCards
        jobs={[usOnlyRemote]}
        sortField={null}
        selectedJobId={null}
        onSelectJob={() => {}}
        savedJobsMap={{}}
        onToggleSave={() => {}}
      />
    );
    expect(cardsHtml).not.toContain('lucide-arrow-up-right');
    expect(cardsHtml).toContain('data-testid="mobile-save-toggle"');
    expect(cardsHtml).toContain('aria-label="Save job"');
    expect(cardsHtml).toContain('data-testid="mobile-meta-strip"');

    // Quick-save click stops propagation so DetailSheet never opens
    const stopPropagation = vi.fn();
    const onSelectJob = vi.fn();
    const onToggleSave = vi.fn();
    handleMobileQuickSaveClick({ stopPropagation }, usOnlyRemote, onToggleSave);
    expect(stopPropagation).toHaveBeenCalledTimes(1);
    expect(onToggleSave).toHaveBeenCalledWith(usOnlyRemote);
    expect(onSelectJob).not.toHaveBeenCalled();
  });
});
