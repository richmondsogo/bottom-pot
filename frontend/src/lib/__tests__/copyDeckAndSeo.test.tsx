import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it, expect, afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { HomePage } from '../../pages/HomePage';
import { ProductPage } from '../../pages/ProductPage';
import { SourcesPage } from '../../pages/SourcesPage';
import { AboutPage } from '../../pages/AboutPage';
import { ContactPage } from '../../pages/ContactPage';
import { Footer } from '../../components/Footer';
import { SearchForm } from '../../components/SearchForm';
import { Toolbar } from '../../components/Toolbar';
import { LoadingState, ErrorState, NoResultsState } from '../../components/States';
import { CompactSearchBar } from '../../components/CompactSearchBar';
import { ResultsTable } from '../../components/ResultsTable';
import { DetailSheet } from '../../components/DetailSheet';
import { CountryCombobox } from '../../components/CountryCombobox';
import { ShortcutsModal } from '../../components/ShortcutsModal';
import { BottomPotEasterEgg } from '../../components/BottomPotEasterEgg';
import { WorkspaceStatusBanners } from '../../components/Workspace';
import { ALL_PLATFORMS } from '../constants';
import { normalizeJob } from '../normalize';
import { getSafeErrorDescription } from '../errorMessage';
import {
  DEFAULT_SITE_ORIGIN,
  ROUTE_METADATA,
  buildRobotsTxt,
  buildSitemapXml,
  injectRouteMetadata,
  resolveSiteOrigin,
} from '../routeMetadata';
import { routeMetadataPlugin } from '../../../vite.config';
import appSrc from '../../App.tsx?raw';
import workspaceSrc from '../../components/Workspace.tsx?raw';
import toolbarSrc from '../../components/Toolbar.tsx?raw';

describe('Approved Copy Deck & Build-Time Route Metadata', () => {
  const tempDirs: string[] = [];

  afterEach(() => {
    while (tempDirs.length > 0) {
      const dir = tempDirs.pop();
      if (dir) {
        fs.rmSync(dir, { recursive: true, force: true });
      }
    }
  });

  it('renders approved copy across public pages and rejects prohibited/contradictory claims', () => {
    const homeHtml = renderToStaticMarkup(<HomePage onNavigate={() => {}} />);
    const productHtml = renderToStaticMarkup(<ProductPage onNavigate={() => {}} />);
    const sourcesHtml = renderToStaticMarkup(
      <SourcesPage onNavigate={() => {}} onSearchPlatforms={() => {}} />
    );
    const aboutHtml = renderToStaticMarkup(<AboutPage onNavigate={() => {}} />);
    const contactHtml = renderToStaticMarkup(<ContactPage onNavigate={() => {}} />);
    const footerHtml = renderToStaticMarkup(<Footer onNavigate={() => {}} />);

    // Homepage required copy (without removed pre-search intro heading/description)
    expect(homeHtml).toContain('Find jobs you can actually apply to.');
    expect(homeHtml).toContain(
      'Search company career pages and selected job boards in one place. Check the work setup and whether your country appears eligible before opening the original listing.'
    );
    expect(homeHtml).not.toContain('What role are you looking for?');
    expect(homeHtml).not.toContain('Search by job title, skill or keyword.');
    expect(homeHtml).toContain('How it works');
    expect(homeHtml).toContain(
      'No account needed. Save jobs and organise your shortlist in your browser.'
    );
    expect(homeHtml).toContain('Search with a purpose');
    expect(homeHtml).toContain('Know where you stand');
    expect(homeHtml).toContain('Go to the original listing');
    expect(homeHtml).toContain(
      'Posting dates and salary details appear when available. Missing information is left unknown, not guessed.'
    );
    expect(homeHtml).toContain('More places to search. One focused workspace.');
    expect(homeHtml).toContain('Explore our sources');
    expect(homeHtml).toContain('Make your next search count.');
    expect(homeHtml).toContain('Free to use. No account required.');

    // Product page required copy + consistent eligibility labels
    expect(productHtml).toContain('Find the role. Check the details. Apply at the source.');
    expect(productHtml).toContain('A clearer way to search');
    expect(productHtml).toContain('01 · Search');
    expect(productHtml).toContain('02 · Review');
    expect(productHtml).toContain('03 · Apply');
    expect(productHtml).toContain('Useful details, without the guesswork');
    expect(productHtml).toContain('Understand the eligibility labels');
    expect(productHtml).toContain(
      'The available listing information indicates that applicants in your selected country may apply. Confirm the requirements with the employer.'
    );
    expect(productHtml).toContain(
      'The available listing information indicates that your selected country is excluded.'
    );
    expect(productHtml).toContain(
      'There is not enough reliable information in the listing to determine whether your country is accepted.'
    );
    expect(productHtml).toContain('Keep promising roles close');
    expect(productHtml).toContain('Explore sources');

    // Sources page required copy + accurate 10 hiring platforms + 3 selected job boards distinction
    expect(sourcesHtml).toContain('Where Bottom Pot searches');
    expect(sourcesHtml).toContain(
      'Bottom Pot searches 10 hiring platforms and 3 selected job boards. Hiring platforms host career pages for individual employers, so one platform can connect to many different companies.'
    );
    expect(sourcesHtml).toContain('Company hiring platforms (9)');
    expect(sourcesHtml).toContain('Enterprise hiring portal (1)');
    expect(sourcesHtml).toContain('Selected job boards (3)');
    expect(sourcesHtml).toContain(
      'The number of hiring platforms is not the same as the number of employer career boards. We add supported employer boards as they are discovered and verified. Coverage and source availability can change over time.'
    );
    expect(sourcesHtml).toContain('Ready to search across these sources?');
    expect(sourcesHtml).toContain('Search Jobberman');
    expect(sourcesHtml).toContain('Search MyJobMag');
    expect(sourcesHtml).toContain('Search HotNigerianJobs');

    // Prohibited / contradictory claims absent everywhere in public marketing pages
    const prohibitedPatterns = [
      /No ghost jobs/i,
      /No aggregators/i,
      /13 company hiring boards/i,
      /Find live jobs/i,
      /100% accurate/i,
      /guaranteed eligibility/i,
      /all defeat is psychological/i,
      /diamondmeme\.jpg/i,
      /\(NG\)/,
    ];
    for (const html of [homeHtml, productHtml, sourcesHtml, aboutHtml, contactHtml, footerHtml]) {
      for (const pattern of prohibitedPatterns) {
        expect(html).not.toMatch(pattern);
      }
    }
  });

  it('renders approved workspace microcopy, toasts, shortcuts, and sanitizes user error messages', () => {
    const sampleJob = normalizeJob({
      id: 'greenhouse:acme:1',
      provider: 'greenhouse',
      title: 'Backend Engineer',
      company: 'Acme',
      location: 'Remote',
      work_model: 'remote',
      posted_at: '2026-11-20T12:00:00Z',
      last_verified_at: '2026-11-25T12:00:00Z',
      source_url: 'https://boards.greenhouse.io/acme/jobs/1',
      apply_url: 'https://boards.greenhouse.io/acme/jobs/1',
      data_source: 'live',
      eligibility: {
        classification: 'worldwide',
        global_remote_explicit: true,
        evidence_excerpt: 'Open worldwide.',
        evidence_url: 'https://boards.greenhouse.io/acme/jobs/1',
      },
    });

    const formHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{ keywords: '', location: '', workModel: 'any', postAge: '7' }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={ALL_PLATFORMS.map((p) => p.id)}
        setSelectedPlatforms={() => {}}
        savedCount={2}
        onOpenSavedShortlist={() => {}}
      />
    );
    expect(formHtml).toContain('Sources selected (13 of 13)');
    expect(formHtml).toContain('2</strong> saved jobs in your shortlist');
    expect(formHtml).toContain('Include Nigerian job boards');
    expect(formHtml).toContain('Leave blank to search across locations.');

    const toolbarProps = {
      tableSearch: '',
      setTableSearch: () => {},
      providerFilter: '',
      setProviderFilter: () => {},
      remoteFilter: '',
      setRemoteFilter: () => {},
      employmentFilter: '',
      setEmploymentFilter: () => {},
      applicantCountry: 'NG',
      onChangeApplicantCountry: () => {},
      eligibilityFilter: '' as const,
      setEligibilityFilter: () => {},
      onlySalaryListed: false,
      setOnlySalaryListed: () => {},
      availableProviders: ['greenhouse'],
      availableEmploymentTypes: ['full_time'],
      totalResults: 1,
      filteredCount: 1,
      onClearFilters: () => {},
      searchInputRef: { current: null },
    };
    const toolbarHtml = renderToStaticMarkup(<Toolbar {...toolbarProps} />);
    expect(toolbarHtml).toContain('placeholder="Filter these results…"');
    expect(toolbarHtml).toContain('All arrangements');
    expect(toolbarHtml).toContain('Country eligibility');
    expect(toolbarHtml).toContain('All statuses');
    expect(toolbarHtml).toContain('Eligible or unverified');
    expect(toolbarHtml).toContain('Eligible only');
    expect(toolbarHtml).toContain('Unverified only');
    expect(toolbarHtml).toContain('Restricted only');
    // PopoverContent is lazily mounted on open, so verify its source copy alongside E2E DOM coverage.
    expect(toolbarSrc).toContain('Salary available only');
    expect(toolbarSrc).toContain('All sources');
    expect(toolbarSrc).toContain('All job types');

    const loadingHtml = renderToStaticMarkup(<LoadingState onCancel={() => {}} mode="user" />);
    expect(loadingHtml).toContain('Searching for matching jobs');
    expect(loadingHtml).toContain(
      'Checking available sources for opportunities that match your search.'
    );
    expect(loadingHtml).toContain('Work arrangement &amp; eligibility');

    const streamingHtml = renderToStaticMarkup(
      <CompactSearchBar
        searchParams={{ keywords: 'Engineer', location: '', workModel: 'any', postAge: '7' }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={ALL_PLATFORMS.map((p) => p.id)}
        setSelectedPlatforms={() => {}}
        defaultEditing={true}
        isStreaming={true}
        onCancelSearch={() => {}}
        totalResults={1}
        metrics={{ total: 1, partial: true }}
        savedTimestamp={Date.now()}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onCopyShareLink={() => {}}
      />
    );
    expect(streamingHtml).toContain('Checking additional sources…');
    expect(streamingHtml).toContain('Results may be incomplete');
    expect(streamingHtml).toContain('Location (optional)');
    expect(streamingHtml).toContain('Any arrangement');

    const tableHtml = renderToStaticMarkup(
      <ResultsTable
        jobs={[sampleJob]}
        sortField={null}
        sortAsc={true}
        onSort={() => {}}
        selectedJobId={null}
        onSelectJob={() => {}}
        activeRowIndex={-1}
      />
    );
    expect(tableHtml).toContain('Work arrangement &amp; eligibility');
    expect(tableHtml).toContain('Last checked');

    const detailHtml = renderToStaticMarkup(
      <DetailSheet
        job={{ ...sampleJob, description: '', requirements: '' }}
        onClose={() => {}}
        onMarkVisited={() => {}}
        isSaved={true}
        savedStage="saved"
        onToggleSave={() => {}}
        onChangeStage={() => {}}
        applicantCountry="NG"
      />
    );
    expect(detailHtml).toContain('Open employer listing');
    expect(detailHtml).toContain('Remove from shortlist');
    expect(detailHtml).toContain('Copy listing link');
    expect(detailHtml).toContain('Application status');
    expect(detailHtml).toContain(
      'The full job details aren&#x27;t available here. Open the employer listing to read the complete posting.'
    );
    expect(detailHtml).toContain('Country eligibility');
    expect(detailHtml).toContain('Why this label?');
    expect(detailHtml).toContain('View source details');
    expect(detailHtml).toContain('Last checked');

    const comboboxHtml = renderToStaticMarkup(<CountryCombobox value="" onChange={() => {}} />);
    expect(comboboxHtml).toContain('Any country');

    const shortcutsHtml = renderToStaticMarkup(
      <ShortcutsModal isOpen={true} onClose={() => {}} mode="user" />
    );
    expect(shortcutsHtml).toContain('Focus the results filter.');
    expect(shortcutsHtml).toContain('Move to the next job.');
    expect(shortcutsHtml).toContain('Move to the previous job.');
    expect(shortcutsHtml).toContain('Open the selected job.');
    expect(shortcutsHtml).toContain('Save or remove the selected job from your shortlist.');
    expect(shortcutsHtml).toContain('Close a panel or dialog.');
    expect(shortcutsHtml).toContain('Show keyboard shortcuts.');
    expect(shortcutsHtml).not.toContain('Open command palette');

    const bannerHtml = renderToStaticMarkup(<WorkspaceStatusBanners budgetExhausted={true} />);
    expect(bannerHtml).toContain('TRACKED SOURCES ONLY');

    // App.tsx toasts & Workspace.tsx filtered empty state
    expect(appSrc).toContain("toast('Saved jobs cleared'");
    expect(appSrc).toContain("toast.success('Saved results restored')");
    expect(appSrc).toContain("toast(res.saved ? 'Added to shortlist' : 'Removed from shortlist')");
    expect(appSrc).toContain('toast.success(`Application status updated: ${STAGE_LABELS[stage]}`)');
    expect(appSrc).toContain("toast.success('Search link copied')");
    expect(appSrc).toContain("toast.success('CSV export downloaded')");
    expect(appSrc).toContain("toast.success('JSON export downloaded')");
    expect(workspaceSrc).toContain('No jobs match these filters.');
    expect(workspaceSrc).toContain(
      'Remove a filter or broaden your search to see more opportunities.'
    );

    // Error sanitization in user mode vs admin mode
    expect(
      getSafeErrorDescription('Simulation error: HTTP 500 downstream ATS indexing error.', false, 'user')
    ).toBe('Something went wrong while searching. Try again in a moment.');
    expect(
      getSafeErrorDescription('Load failed', false, 'user')
    ).toBe('Something went wrong while searching. Try again in a moment.');
    expect(
      getSafeErrorDescription('Unexpected token < in JSON at position 0', false, 'user')
    ).toBe('Something went wrong while searching. Try again in a moment.');
    expect(
      getSafeErrorDescription('The search took too long. Please try again.', false, 'user')
    ).toBe('The search took too long. Please try again.');
    expect(
      getSafeErrorDescription('HTTP 502 downstream ATS error', false, 'admin')
    ).toBe('HTTP 502 downstream ATS error');

    const sanitizedErrHtml = renderToStaticMarkup(
      <ErrorState
        message="The search service returned HTTP 500."
        isRateLimited={false}
        mode="user"
        onRetry={() => {}}
      />
    );
    expect(sanitizedErrHtml).toContain('We couldn&#x27;t load your results.');
    expect(sanitizedErrHtml).toContain(
      'Something went wrong while searching. Try again in a moment.'
    );
    expect(sanitizedErrHtml).toContain('Try again');
    expect(sanitizedErrHtml).not.toContain('HTTP 500');

    // Separate easter egg preserved intact
    const eggHtml = renderToStaticMarkup(
      <BottomPotEasterEgg open={true} onClose={() => {}} theme="light" />
    );
    expect(eggHtml).toContain('Bottom of the Pot');
    expect(eggHtml).toContain('You scraped all the way to the bottom.');

    // Ensure no-results does not use diamond meme
    const noResultsHtml = renderToStaticMarkup(
      <NoResultsState onWidenDateRange={() => {}} onClearFilters={() => {}} onNewSearch={() => {}} />
    );
    expect(noResultsHtml).not.toContain('diamondmeme');
  });

  it('resolves site origin precedence and generates built per-route HTML, robots.txt, and sitemap.xml hermetically', () => {
    expect(resolveSiteOrigin({})).toBe(DEFAULT_SITE_ORIGIN);
    expect(
      resolveSiteOrigin({
        VERCEL_PROJECT_PRODUCTION_URL: 'bottompot.example',
      })
    ).toBe('https://bottompot.example');
    expect(
      resolveSiteOrigin({
        VITE_SITE_URL: 'https://jobs.bottompot.example/extra-path',
        VERCEL_PROJECT_PRODUCTION_URL: 'ignored.example',
      })
    ).toBe('https://jobs.bottompot.example');

    const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bp-seo-build-'));
    tempDirs.push(outDir);

    const templatePath = path.resolve(process.cwd(), 'index.html');
    const templateHtml = fs.readFileSync(templatePath, 'utf-8');
    const plugin = routeMetadataPlugin('https://jobs.bottompot.example');

    const transformedRoot = (plugin.transformIndexHtml as (html: string) => string)(templateHtml);
    fs.writeFileSync(path.join(outDir, 'index.html'), transformedRoot, 'utf-8');
    (plugin.writeBundle as (opts: { dir?: string }) => void)({ dir: outDir });

    const expectedRoutes: Array<{ file: string; route: keyof typeof ROUTE_METADATA }> = [
      { file: 'index.html', route: 'home' },
      { file: 'product/index.html', route: 'product' },
      { file: 'about/index.html', route: 'about' },
      { file: 'sources/index.html', route: 'sources' },
      { file: 'contact/index.html', route: 'contact' },
      { file: 'privacy/index.html', route: 'privacy' },
      { file: 'terms/index.html', route: 'terms' },
      { file: 'app/index.html', route: 'search' },
      { file: 'admin/index.html', route: 'admin' },
    ];

    for (const item of expectedRoutes) {
      const html = fs.readFileSync(path.join(outDir, item.file), 'utf-8');
      const meta = ROUTE_METADATA[item.route];
      expect(html).toContain(`<title>${meta.title}</title>`);
      expect(html).toContain(`<meta name="description" content="${meta.description}" />`);
      expect(html).toContain(`<meta property="og:title" content="${meta.title}" />`);
      expect(html).toContain(`<meta property="og:description" content="${meta.description}" />`);
      expect(html).toContain(
        '<meta property="og:image" content="https://jobs.bottompot.example/og-image.png" />'
      );
      expect(html).toContain(`<meta name="twitter:title" content="${meta.title}" />`);
      expect(html).toContain(
        `<meta name="twitter:description" content="${meta.description}" />`
      );
      expect(html).toContain(
        '<meta name="twitter:image" content="https://jobs.bottompot.example/og-image.png" />'
      );
      expect(html).toContain(`<meta name="robots" content="${meta.robots}" />`);
      if (meta.omitCanonical) {
        expect(html).not.toContain('rel="canonical"');
      } else {
        const expectedCanonical =
          meta.path === '/'
            ? 'https://jobs.bottompot.example/'
            : `https://jobs.bottompot.example${meta.path}`;
        expect(html).toContain(`<link rel="canonical" href="${expectedCanonical}" />`);
      }
    }

    const robots = fs.readFileSync(path.join(outDir, 'robots.txt'), 'utf-8');
    expect(robots).toBe(buildRobotsTxt('https://jobs.bottompot.example'));
    expect(robots).toContain('Disallow: /admin');
    expect(robots).toContain('Sitemap: https://jobs.bottompot.example/sitemap.xml');

    const sitemap = fs.readFileSync(path.join(outDir, 'sitemap.xml'), 'utf-8');
    expect(sitemap).toBe(buildSitemapXml('https://jobs.bottompot.example'));
    expect(sitemap).toContain('<loc>https://jobs.bottompot.example/</loc>');
    expect(sitemap).toContain('<loc>https://jobs.bottompot.example/product</loc>');
    expect(sitemap).toContain('<loc>https://jobs.bottompot.example/terms</loc>');
    expect(sitemap).not.toContain('/app');
    expect(sitemap).not.toContain('/admin');
    expect(sitemap).not.toContain('/search');
    expect(sitemap).not.toMatch(/<loc>[^<]*\?/);

    // Verify marker safety
    expect(() => injectRouteMetadata('<html></html>', 'home', DEFAULT_SITE_ORIGIN)).toThrow();
  });
});
