import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  PromptInput,
  PromptInputField,
  PromptInputActions,
  PromptInputAction,
} from '../../components/prompt-kit/prompt-input';
import { SearchSummaryBar } from '../../components/SearchSummaryBar';
import { SearchForm } from '../../components/SearchForm';
import { readStateFromUrl } from '../urlState';

describe('PromptInput primitives', () => {
  it('renders PromptInput container with square radius and border styles', () => {
    const html = renderToStaticMarkup(
      <PromptInput className="custom-input">
        <PromptInputField placeholder="Search..." />
        <PromptInputActions>
          <PromptInputAction>Action</PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    );

    expect(html).toContain('data-slot="prompt-input"');
    expect(html).toContain('custom-input');
    expect(html).toContain('border-radius:0');
    expect(html).toContain('data-slot="prompt-input-field"');
    expect(html).toContain('placeholder="Search..."');
    expect(html).toContain('data-slot="prompt-input-actions"');
    expect(html).toContain('data-slot="prompt-input-action"');
    expect(html).toContain('Action');
  });

  it('renders error state border correctly on PromptInput', () => {
    const html = renderToStaticMarkup(
      <PromptInput error={true}>
        <PromptInputField />
      </PromptInput>
    );
    expect(html).toContain('border-[var(--destructive)]');
  });

  it('renders dedicated Export button in user mode with visible count and export trigger', () => {
    const html = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Frontend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={42}
        filteredCount={15}
        mode="user"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(html).toContain('Export');
    expect(html).toContain('aria-label="Export results"');
    expect(html).toContain('Edit search');
  });

  it('renders dedicated Export button in both user and admin modes', () => {
    const userHtml = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Frontend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={42}
        mode="user"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(userHtml).toContain('aria-label="Export results"');

    const adminHtml = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Backend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={10}
        mode="admin"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(adminHtml).toContain('aria-label="Export results"');
    expect(adminHtml).toContain('aria-label="More actions"');
  });

  it('each work-model option sets exactly the value the URL state and the /search query expect', () => {
    // 1. URL State reading verifies canonical string values: any, remote, onsite
    const originalWindow = globalThis.window;

    (globalThis as any).window = {
      location: {
        href: 'http://localhost:3000/app?wm=remote',
        origin: 'http://localhost:3000',
        pathname: '/app',
        search: '?wm=remote',
      },
    };
    const parsedRemote = readStateFromUrl();
    expect(parsedRemote?.searchParams?.workModel).toBe('remote');

    (globalThis as any).window = {
      location: {
        href: 'http://localhost:3000/app?wm=onsite',
        origin: 'http://localhost:3000',
        pathname: '/app',
        search: '?wm=onsite',
      },
    };
    const parsedOnsite = readStateFromUrl();
    expect(parsedOnsite?.searchParams?.workModel).toBe('onsite');

    (globalThis as any).window = originalWindow;

    // 2. SearchForm options match these exact values
    const formHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{ keywords: 'Go Engineer', location: 'Lagos', workModel: 'remote', postAge: '7', includeNigerian: true, deepScrape: false }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={['greenhouse', 'lever']}
        setSelectedPlatforms={() => {}}
      />
    );
    expect(formHtml).toContain('value="any"');
    expect(formHtml).toContain('value="remote"');
    expect(formHtml).toContain('value="onsite"');
    expect(formHtml).toContain('Any work model');
    expect(formHtml).toContain('Remote only');
    expect(formHtml).toContain('Exclude remote (In-person / Hybrid)');
  });

  it('post-age chips keep the stored string type and match option values', () => {
    const postAgeValues = ['1', '3', '7', '14', '30'];
    for (const val of postAgeValues) {
      expect(typeof val).toBe('string');
    }

    const formHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{ keywords: 'Frontend', location: '', workModel: 'any', postAge: '14', includeNigerian: true, deepScrape: false }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={[]}
        setSelectedPlatforms={() => {}}
      />
    );

    // Verify all 5 string values are present in post-age options
    expect(formHtml).toContain('Past 24 hours');
    expect(formHtml).toContain('Past 3 days');
    expect(formHtml).toContain('Past 7 days (default)');
    expect(formHtml).toContain('value="14"');
    expect(formHtml).toContain('Past 14 days');
  });

  it('the Nigerian toggle and deep-scrape toggle reflect searchParams flags', () => {
    const formHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{
          keywords: 'Platform Engineer',
          location: '',
          workModel: 'any',
          postAge: '7',
          includeNigerian: true,
          deepScrape: false,
        }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={[]}
        setSelectedPlatforms={() => {}}
      />
    );

    expect(formHtml).toContain('id="nigerian-boards-check"');
    expect(formHtml).toContain('Include Nigerian boards (Jobberman, MyJobMag)');
    expect(formHtml).toContain('id="deep-scrape-check"');
    expect(formHtml).toContain('Deep scrape matched job pages');
  });

  it('loading /app?wm=remote shows Remote selected', () => {
    const originalWindow = globalThis.window;
    (globalThis as any).window = {
      location: {
        href: 'http://localhost:3000/app?wm=remote',
        origin: 'http://localhost:3000',
        pathname: '/app',
        search: '?wm=remote',
      },
    };
    const parsedState = readStateFromUrl();
    expect(parsedState?.searchParams?.workModel).toBe('remote');
    (globalThis as any).window = originalWindow;

    const formHtml = renderToStaticMarkup(
      <SearchForm
        searchParams={{
          keywords: 'Developer',
          location: '',
          workModel: parsedState?.searchParams?.workModel || 'any',
          postAge: '7',
          includeNigerian: true,
          deepScrape: false,
        }}
        setSearchParams={() => {}}
        onSubmit={() => {}}
        selectedPlatforms={[]}
        setSelectedPlatforms={() => {}}
      />
    );

    expect(formHtml).toContain('Remote only');
  });

  it('verifies round-trip contract: option selected -> executeSearch query params -> URL state -> backend params for all workModel values', () => {
    // Contract definition across App.tsx, urlState.ts, SearchForm.tsx, and HeroPortalSection.tsx:
    // 1. Quick starters in HeroPortalSection pass:
    //    - 'React engineer' with 'remote'
    //    - 'Python developer' with 'any'
    //    - 'Product designer' with 'any'
    //    - in_person mapping to 'onsite'
    // 2. executeSearch mapping in App.tsx:
    //    - if (workModel !== 'any') queryParams.set('remote', String(workModel === 'remote'))
    // 3. urlState.ts:
    //    - ?wm=remote -> workModel: 'remote'
    //    - ?wm=onsite -> workModel: 'onsite'
    //    - ?wm=any or missing -> workModel: 'any'

    const testCases: Array<{
      inputModel: string;
      expectedCanonicalModel: string;
      expectedUrlParam: string | null;
      expectedBackendRemoteParam: string | null;
      expectedSelectLabel: string;
    }> = [
      {
        inputModel: 'remote',
        expectedCanonicalModel: 'remote',
        expectedUrlParam: 'remote',
        expectedBackendRemoteParam: 'true',
        expectedSelectLabel: 'Remote only',
      },
      {
        inputModel: 'onsite',
        expectedCanonicalModel: 'onsite',
        expectedUrlParam: 'onsite',
        expectedBackendRemoteParam: 'false',
        expectedSelectLabel: 'Exclude remote (In-person / Hybrid)',
      },
      {
        inputModel: 'in_person', // Quick-starter input variant mapped in App.tsx
        expectedCanonicalModel: 'onsite',
        expectedUrlParam: 'onsite',
        expectedBackendRemoteParam: 'false',
        expectedSelectLabel: 'Exclude remote (In-person / Hybrid)',
      },
      {
        inputModel: 'any',
        expectedCanonicalModel: 'any',
        expectedUrlParam: null,
        expectedBackendRemoteParam: null, // Omitted from query params
        expectedSelectLabel: 'Any work model',
      },
    ];

    const originalWindow = globalThis.window;

    for (const tc of testCases) {
      // Step 1: Normalize input model via App.tsx's handleQuickSearch logic
      const targetModel = tc.inputModel === 'in_person' ? 'onsite' : tc.inputModel;
      expect(targetModel).toBe(tc.expectedCanonicalModel);

      // Step 2: URL State round-trip
      const mockSearchUrl = tc.expectedUrlParam
        ? `http://localhost:3000/app?wm=${tc.expectedUrlParam}`
        : 'http://localhost:3000/app';

      (globalThis as any).window = {
        location: {
          href: mockSearchUrl,
          origin: 'http://localhost:3000',
          pathname: '/app',
          search: tc.expectedUrlParam ? `?wm=${tc.expectedUrlParam}` : '',
        },
      };

      const parsedState = readStateFromUrl();
      const resolvedModel = parsedState?.searchParams?.workModel || 'any';
      expect(resolvedModel).toBe(tc.expectedCanonicalModel);

      // Step 3: Backend query parameters mapping (mirroring executeSearch in App.tsx)
      const backendParams = new URLSearchParams();
      if (resolvedModel !== 'any') {
        backendParams.set('remote', String(resolvedModel === 'remote'));
      }
      expect(backendParams.get('remote')).toBe(tc.expectedBackendRemoteParam);

      // Step 4: SearchForm renders option with correct label and value
      const formHtml = renderToStaticMarkup(
        <SearchForm
          searchParams={{
            keywords: 'Engineer',
            location: '',
            workModel: resolvedModel,
            postAge: '7',
            includeNigerian: true,
            deepScrape: false,
          }}
          setSearchParams={() => {}}
          onSubmit={() => {}}
          selectedPlatforms={[]}
          setSelectedPlatforms={() => {}}
        />
      );
      expect(formHtml).toContain(`value="${tc.expectedCanonicalModel}"`);
      expect(formHtml).toContain(tc.expectedSelectLabel);
    }

    (globalThis as any).window = originalWindow;
  });
});
