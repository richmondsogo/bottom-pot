import React, { useState, useMemo, useRef, useEffect } from 'react';
import type { JobListing, NormalizedJob, DoneMetrics, SearchParams, SortField } from './types';
import { normalizeJob } from './lib/normalize';
import { readStorage, writeStorage } from './lib/storage';
import { markVisited } from './lib/visited';
import { filterJobs } from './lib/filter';
import { sortJobs } from './lib/sort';
import { isMockModeActive, getMockModeType, generateMockJobs, getMockMetrics } from './lib/mock';
import { downloadCsv, downloadJson } from './lib/export';
import {
  getSavedJobsMap,
  toggleSavedJob,
  updateSavedJobStage,
  STAGE_LABELS,
  type ApplicationStage,
  type SavedJobEntry,
} from './lib/savedJobs';
import {
  getRecentSearches,
  recordRecentSearch,
  readStateFromUrl,
  syncStateToUrl,
  buildShareableSearchUrl,
  type RecentSearchPreset,
} from './lib/urlState';

import { Header } from './components/Header';
import { CommandPalette } from './components/CommandPalette';
import { SearchForm } from './components/SearchForm';
import { ALL_PLATFORMS } from './lib/constants';
import { SearchSummaryBar } from './components/SearchSummaryBar';
import { Toolbar } from './components/Toolbar';
import { ResultsTable } from './components/ResultsTable';
import { ResultsCards } from './components/ResultsCards';
import { DetailSheet } from './components/DetailSheet';
import { ShortcutsModal } from './components/ShortcutsModal';
import { LoadingState, NoResultsState, ErrorState } from './components/States';
import { MarketingLanding } from './components/marketing/MarketingLanding';
import { TelemetryDeck } from './components/TelemetryDeck';
import { ScrollButton } from './components/prompt-kit/scroll-button';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';

export function App() {
  // Theme state: light or dark, synced with document.documentElement
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('bp.theme');
      if (saved === 'light' || saved === 'dark') return saved;
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    }
    return 'light';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      localStorage.setItem('bp.theme', next);
      if (next === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      return next;
    });
  };

  // Command palette state
  const [commandOpen, setCommandOpen] = useState(false);

  // Initial URL state (if shared/bookmarked link was opened)
  const initialUrlState = useMemo(() => readStateFromUrl(), []);

  // Telemetry Deck disclosure state in workspace
  const [telemetryOpen, setTelemetryOpen] = useState(false);

  // SPA View Switcher: 'marketing' (default at /) vs 'workspace' (active at /search or /app or ?view=workspace or ?mock=1)
  const [viewMode, setViewMode] = useState<'marketing' | 'workspace'>(() => {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const params = new URLSearchParams(window.location.search);
      if (
        path === '/search' ||
        path === '/app' ||
        params.get('view') === 'workspace' ||
        params.get('view') === 'search' ||
        params.get('view') === 'app' ||
        params.get('mock') !== null ||
        params.get('q') ||
        params.get('role') ||
        params.get('k') ||
        params.get('saved') === '1' ||
        Boolean(initialUrlState?.searchParams?.keywords)
      ) {
        return 'workspace';
      }
    }
    return 'marketing';
  });

  // Native View Transition Helper with Reduced-Motion Fallback (ADR 0014)
  const transitionView = (targetView: 'marketing' | 'workspace', updateUrl = true) => {
    const applyView = () => {
      setViewMode(targetView);
      if (updateUrl && typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        if (targetView === 'workspace') {
          if (url.pathname !== '/search' && url.pathname !== '/app') {
            url.pathname = '/search';
          }
          url.searchParams.delete('view');
        } else {
          url.pathname = '/';
          url.searchParams.delete('view');
          url.searchParams.delete('q');
          url.searchParams.delete('loc');
          url.searchParams.delete('wm');
          url.searchParams.delete('age');
          url.searchParams.delete('ng');
          url.searchParams.delete('flt');
          url.searchParams.delete('prov');
          url.searchParams.delete('rem');
          url.searchParams.delete('emp');
          url.searchParams.delete('sal');
          url.searchParams.delete('saved');
        }
        window.history.pushState({ view: targetView }, '', url.toString());
      }
    };

    if (
      typeof document !== 'undefined' &&
      'startViewTransition' in document &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      (document as unknown as { startViewTransition: (cb: () => void) => void }).startViewTransition(() => {
        applyView();
      });
    } else {
      applyView();
    }
  };

  // Popstate history listener for Back/Forward browser navigation
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      const params = new URLSearchParams(window.location.search);
      if (
        path === '/search' ||
        path === '/app' ||
        params.get('view') === 'workspace' ||
        params.get('view') === 'search' ||
        params.get('view') === 'app' ||
        params.get('mock') !== null ||
        params.get('q') ||
        params.get('role') ||
        params.get('k') ||
        params.get('saved') === '1'
      ) {
        setViewMode('workspace');
      } else {
        setViewMode('marketing');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Persistence: search parameters
  const [searchParams, setSearchParams] = useState<SearchParams>(() => {
    const stored = readStorage<SearchParams>('bp.searchParams', {
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
      includeNigerian: true,
      deepScrape: false,
    });
    return initialUrlState?.searchParams
      ? { ...stored, ...initialUrlState.searchParams }
      : stored;
  });

  // Platform selection state
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(() =>
    readStorage<string[]>('bp.selectedPlatforms', ALL_PLATFORMS.map((p) => p.id))
  );

  // Filter persistence
  const [tableSearch, setTableSearch] = useState(
    () => initialUrlState?.tableSearch ?? readStorage<string>('bp.filter.search', '')
  );
  const [providerFilter, setProviderFilter] = useState(
    () => initialUrlState?.providerFilter ?? readStorage<string>('bp.filter.provider', '')
  );
  const [remoteFilter, setRemoteFilter] = useState(
    () => initialUrlState?.remoteFilter ?? readStorage<string>('bp.filter.remote', '')
  );
  const [employmentFilter, setEmploymentFilter] = useState(
    () => initialUrlState?.employmentFilter ?? readStorage<string>('bp.filter.employment', '')
  );
  const [onlySalaryListed, setOnlySalaryListed] = useState(
    () => initialUrlState?.onlySalaryListed ?? readStorage<boolean>('bp.filter.salaryOnly', false)
  );
  const [onlySavedJobs, setOnlySavedJobs] = useState<boolean>(
    () => initialUrlState?.onlySavedJobs ?? false
  );

  // Saved jobs shortlist & recent searches state
  const [savedJobsMap, setSavedJobsMap] = useState<Record<string, SavedJobEntry>>(() =>
    getSavedJobsMap()
  );
  const [recentSearches, setRecentSearches] = useState<RecentSearchPreset[]>(() =>
    getRecentSearches()
  );
  const savedCount = useMemo(() => Object.keys(savedJobsMap).length, [savedJobsMap]);

  // Sort persistence
  const [sortField, setSortField] = useState<SortField>(() => readStorage<SortField>('bp.sort.field', null));
  const [sortAsc, setSortAsc] = useState<boolean>(() => readStorage<boolean>('bp.sort.asc', true));

  // Persistence: saved results restoration
  const savedResultsData = useMemo(() => {
    try {
      const raw = localStorage.getItem('bp.savedResults');
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.rawResults) && parsed.rawResults.length > 0) {
        return parsed as {
          rawResults: JobListing[];
          metrics: DoneMetrics | null;
          savedAt: number;
        };
      }
    } catch {
      // Ignore corrupt local data
    }
    return null;
  }, []);

  const [rawResults, setRawResults] = useState<JobListing[]>(() => {
    if (isMockModeActive()) {
      const mode = getMockModeType();
      if (mode === 'default' || mode === 'slow') {
        return generateMockJobs();
      }
      return [];
    }
    if (savedResultsData?.rawResults && savedResultsData.rawResults.length > 0) {
      return savedResultsData.rawResults;
    }
    if (initialUrlState?.onlySavedJobs) {
      const savedEntries = Object.values(getSavedJobsMap());
      if (savedEntries.length > 0) {
        return savedEntries.map((e) => e.job);
      }
    }
    return [];
  });

  const [metrics, setMetrics] = useState<DoneMetrics | null>(() => {
    if (isMockModeActive()) {
      const mode = getMockModeType();
      if (mode === 'default' || mode === 'slow') {
        return getMockMetrics(150);
      }
      if (mode === 'empty') {
        return getMockMetrics(0);
      }
      return null;
    }
    return savedResultsData?.metrics || null;
  });

  const [savedTimestamp, setSavedTimestamp] = useState<number | null>(
    () => savedResultsData?.savedAt || null
  );

  // Screen state: 'form' | 'loading' | 'delivery' | 'error'
  const [screen, setScreen] = useState<'form' | 'loading' | 'delivery' | 'error'>(() => {
    if (isMockModeActive()) {
      const mode = getMockModeType();
      if (mode === 'error') return 'error';
      if (mode === 'empty') return 'delivery';
      return 'delivery';
    }
    if (savedResultsData && savedResultsData.rawResults.length > 0) {
      return 'delivery';
    }
    if (initialUrlState?.onlySavedJobs && Object.keys(getSavedJobsMap()).length > 0) {
      return 'delivery';
    }
    return 'form';
  });

  // Native View Transitions helper
  const switchScreen = (newScreen: 'form' | 'loading' | 'delivery' | 'error') => {
    if (
      typeof document !== 'undefined' &&
      'startViewTransition' in document &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      (document as unknown as { startViewTransition: (cb: () => void) => void }).startViewTransition(() => {
        setScreen(newScreen);
      });
    } else {
      setScreen(newScreen);
    }
  };

  // Details sheet & keyboard selection state
  const [selectedJob, setSelectedJob] = useState<NormalizedJob | null>(null);
  const [activeRowIndex, setActiveRowIndex] = useState<number>(-1);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>(() => {
    if (isMockModeActive() && getMockModeType() === 'error') {
      return 'Simulation error: HTTP 500 downstream ATS indexing error.';
    }
    return '';
  });
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [, setVisitedVersion] = useState(0);

  const abortControllerRef = useRef<AbortController | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  const savedScrollYRef = useRef<number>(0);

  // Save changes to localStorage
  useEffect(() => { writeStorage('bp.searchParams', searchParams); }, [searchParams]);
  useEffect(() => { writeStorage('bp.selectedPlatforms', selectedPlatforms); }, [selectedPlatforms]);
  useEffect(() => { writeStorage('bp.filter.search', tableSearch); }, [tableSearch]);
  useEffect(() => { writeStorage('bp.filter.provider', providerFilter); }, [providerFilter]);
  useEffect(() => { writeStorage('bp.filter.remote', remoteFilter); }, [remoteFilter]);
  useEffect(() => { writeStorage('bp.filter.employment', employmentFilter); }, [employmentFilter]);
  useEffect(() => { writeStorage('bp.filter.salaryOnly', onlySalaryListed); }, [onlySalaryListed]);
  useEffect(() => { writeStorage('bp.sort.field', sortField); }, [sortField]);
  useEffect(() => { writeStorage('bp.sort.asc', sortAsc); }, [sortAsc]);

  // Sync active delivery search & filter state to URL query parameters
  useEffect(() => {
    syncStateToUrl(
      screen,
      {
        searchParams,
        tableSearch,
        providerFilter,
        remoteFilter,
        employmentFilter,
        onlySalaryListed,
        onlySavedJobs,
      },
      viewMode === 'workspace'
    );
  }, [
    screen,
    viewMode,
    searchParams,
    tableSearch,
    providerFilter,
    remoteFilter,
    employmentFilter,
    onlySalaryListed,
    onlySavedJobs,
  ]);

  // If opened directly on /search or /app with a search query and no saved results, trigger search
  useEffect(() => {
    if (
      viewMode === 'workspace' &&
      initialUrlState?.searchParams?.keywords &&
      !savedResultsData?.rawResults?.length &&
      !isMockModeActive()
    ) {
      executeSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // Scroll restoration when returning to delivery
  useEffect(() => {
    if (screen === 'delivery' && savedScrollYRef.current > 0) {
      requestAnimationFrame(() => {
        window.scrollTo({
          top: savedScrollYRef.current,
          behavior: 'instant' as ScrollBehavior,
        });
      });
    }
  }, [screen]);

  // Persist results safely
  const persistResults = (results: JobListing[], currentMetrics: DoneMetrics | null) => {
    try {
      const timestamp = Date.now();
      const payload = JSON.stringify({
        rawResults: results,
        metrics: currentMetrics,
        savedAt: timestamp,
      });
      if (payload.length <= 3 * 1024 * 1024) {
        localStorage.setItem('bp.savedResults', payload);
        setSavedTimestamp(timestamp);
      }
    } catch {
      // Ignore QuotaExceededError
    }
  };

  const handleClearSavedResults = () => {
    const previousData = localStorage.getItem('bp.savedResults');
    const oldRaw = rawResults;
    const oldMetrics = metrics;
    const oldTimestamp = savedTimestamp;

    try {
      localStorage.removeItem('bp.savedResults');
    } catch {
      // Ignore storage errors
    }

    setSavedTimestamp(null);
    setRawResults([]);
    setMetrics(null);
    setSelectedJob(null);
    switchScreen('form');

    toast('Saved results cleared', {
      action: {
        label: 'Undo',
        onClick: () => {
          if (previousData) {
            try {
              localStorage.setItem('bp.savedResults', previousData);
              setRawResults(oldRaw);
              setMetrics(oldMetrics);
              setSavedTimestamp(oldTimestamp);
              switchScreen('delivery');
              toast.success('Restored saved results');
            } catch {
              // Ignore
            }
          }
        },
      },
    });
  };

  // Normalization (when onlySavedJobs is active, include any saved jobs not in rawResults)
  const normalizedList = useMemo(() => {
    if (!onlySavedJobs) {
      return rawResults.map((job) => normalizeJob(job));
    }
    const byId = new Map<string, JobListing>();
    for (const job of rawResults) {
      if (savedJobsMap[job.id]) {
        byId.set(job.id, job);
      }
    }
    for (const entry of Object.values(savedJobsMap)) {
      if (!byId.has(entry.job.id)) {
        byId.set(entry.job.id, entry.job);
      }
    }
    return Array.from(byId.values()).map((job) => normalizeJob(job));
  }, [rawResults, onlySavedJobs, savedJobsMap]);

  // Provider and Employment options
  const availableProviders = useMemo(() => {
    const set = new Set(normalizedList.map((job) => job.provider).filter(Boolean));
    return Array.from(set).sort();
  }, [normalizedList]);

  const availableEmploymentTypes = useMemo(() => {
    const set = new Set(
      normalizedList
        .map((job) => job.displayEmployment)
        .filter((val) => val && val !== '—' && val !== 'Unknown')
    );
    return Array.from(set).sort();
  }, [normalizedList]);

  // Pure filtering
  const filteredResults = useMemo(() => {
    return filterJobs(normalizedList, {
      search: tableSearch,
      provider: providerFilter,
      remote: remoteFilter,
      employment: employmentFilter,
      salaryOnly: onlySalaryListed,
    });
  }, [normalizedList, tableSearch, providerFilter, remoteFilter, employmentFilter, onlySalaryListed]);

  // Pure sorting
  const sortedResults = useMemo(() => {
    return sortJobs(filteredResults, sortField, sortAsc);
  }, [filteredResults, sortField, sortAsc]);

  const handleToggleSave = (job: NormalizedJob) => {
    const res = toggleSavedJob(job);
    setSavedJobsMap(res.map);
    toast(res.saved ? 'Saved to shortlist' : 'Removed from shortlist');
  };

  const handleChangeStage = (job: NormalizedJob, stage: ApplicationStage) => {
    const nextMap = updateSavedJobStage(job, stage);
    setSavedJobsMap(nextMap);
    toast.success(`Stage updated to ${STAGE_LABELS[stage]}`);
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = document.activeElement;
      const isInput =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.getAttribute('contenteditable') === 'true';

      if (e.key === 'Escape') {
        if (commandOpen) {
          setCommandOpen(false);
          return;
        }
        if (shortcutsOpen) {
          setShortcutsOpen(false);
          return;
        }
        if (selectedJob) {
          setSelectedJob(null);
          return;
        }
      }

      if (isInput) return;

      if (e.key === '/') {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      if (e.key === '?') {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
        return;
      }

      if (screen === 'delivery' && sortedResults.length > 0) {
        if (e.key === 'j' || e.key === 'ArrowDown') {
          e.preventDefault();
          setActiveRowIndex((prev) => Math.min(sortedResults.length - 1, prev + 1));
        } else if (e.key === 'k' || e.key === 'ArrowUp') {
          e.preventDefault();
          setActiveRowIndex((prev) => Math.max(0, prev - 1));
        } else if (e.key === 'Enter' || e.key === 'o') {
          if (activeRowIndex >= 0 && activeRowIndex < sortedResults.length) {
            e.preventDefault();
            const targetJob = sortedResults[activeRowIndex];
            setSelectedJob((prev) => (prev?.id === targetJob.id ? null : targetJob));
          }
        } else if (e.key === 's' || e.key === 'S') {
          const targetJob =
            selectedJob ||
            (activeRowIndex >= 0 && activeRowIndex < sortedResults.length
              ? sortedResults[activeRowIndex]
              : null);
          if (targetJob) {
            e.preventDefault();
            handleToggleSave(targetJob);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [screen, sortedResults, activeRowIndex, selectedJob, shortcutsOpen, commandOpen]);

  // Search execution
  const executeSearch = async (customParams?: SearchParams) => {
    const paramsToUse = customParams || searchParams;
    setRecentSearches(recordRecentSearch(paramsToUse));
    setRawResults([]);
    setMetrics(null);
    setSelectedJob(null);
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setOnlySavedJobs(false);
    setSortField(null);
    setActiveRowIndex(-1);
    setIsRateLimited(false);
    switchScreen('loading');
    setLoadingMessage('Connecting to ATS search pipeline...');

    // If Mock Mode is active, simulate without network or live Serper credits
    if (isMockModeActive()) {
      const mode = getMockModeType();
      const delay = mode === 'slow' ? 3000 : 700;

      setTimeout(() => {
        if (mode === 'error') {
          setErrorMessage('Simulated Search Failure: Upstream ATS service unreachable (HTTP 502).');
          switchScreen('error');
          return;
        }
        if (mode === 'empty') {
          setRawResults([]);
          setMetrics(getMockMetrics(0));
          switchScreen('delivery');
          return;
        }

        const mockJobs = generateMockJobs();
        setRawResults(mockJobs);
        const mockMetrics = getMockMetrics(mockJobs.length);
        setMetrics(mockMetrics);
        persistResults(mockJobs, mockMetrics);
        switchScreen('delivery');
      }, delay);
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const queryParams = new URLSearchParams({
      q: paramsToUse.keywords.trim(),
      days_back: paramsToUse.postAge,
      include_nigerian: String(paramsToUse.includeNigerian),
    });

    if (paramsToUse.location.trim()) {
      queryParams.set('location', paramsToUse.location.trim());
    }
    if (paramsToUse.workModel !== 'any') {
      queryParams.set('remote', String(paramsToUse.workModel === 'remote'));
    }
    if (selectedPlatforms.length > 0 && selectedPlatforms.length < ALL_PLATFORMS.length) {
      queryParams.set('platforms', selectedPlatforms.join(','));
    }
    if (paramsToUse.deepScrape) {
      queryParams.set('deep_scrape', 'true');
    }

    try {
      const response = await fetch(`/search?${queryParams.toString()}`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      });

      if (response.status === 429) {
        setIsRateLimited(true);
        throw new Error('Rate limit exceeded (HTTP 429). Too many searches in a short window. Please wait a bit before retrying.');
      }

      if (!response.ok || !response.body) {
        throw new Error(`The search service returned HTTP ${response.status}.`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventName = '';
      let eventData = '';
      let accumulatedResults: JobListing[] = [];
      let finalMetrics: DoneMetrics | null = null;
      let switchedOnDone = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            eventData += line.slice(5).trim();
          } else if (line === '' && eventName && eventData) {
            const payload = JSON.parse(eventData);

            if (eventName === 'results') {
              const batch = (payload.batch || []) as JobListing[];
              accumulatedResults = [...accumulatedResults, ...batch];
              setRawResults(accumulatedResults);
              setLoadingMessage(`Discovered ${accumulatedResults.length} postings across ATS platforms...`);
            } else if (eventName === 'done') {
              finalMetrics = payload as DoneMetrics;
              setMetrics(finalMetrics);
              persistResults(accumulatedResults, finalMetrics);
              switchScreen('delivery');
              switchedOnDone = true;
            } else if (eventName === 'error') {
              throw new Error(payload.message || 'Search execution failed');
            }

            eventName = '';
            eventData = '';
          }
        }
      }

      if (!switchedOnDone) {
        persistResults(accumulatedResults, finalMetrics);
        switchScreen('delivery');
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        switchScreen('form');
      } else {
        const message = err instanceof Error ? err.message : String(err);
        setErrorMessage(message);
        switchScreen('error');
      }
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch();
  };

  const handleCancelSearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    switchScreen('form');
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const handleMarkVisited = (urlOrId: string) => {
    markVisited(urlOrId);
    setVisitedVersion((v) => v + 1);
  };

  const handleClearFilters = () => {
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setOnlySavedJobs(false);
  };

  const handleCopyShareLink = () => {
    const shareUrl = buildShareableSearchUrl({
      searchParams,
      tableSearch,
      providerFilter,
      remoteFilter,
      employmentFilter,
      onlySalaryListed,
      onlySavedJobs,
    });
    if (shareUrl && navigator.clipboard) {
      navigator.clipboard.writeText(shareUrl);
      toast.success('Copied shareable search link');
    }
  };

  const handleSelectRecentSearch = (preset: RecentSearchPreset) => {
    const updated: SearchParams = {
      ...searchParams,
      keywords: preset.keywords,
      location: preset.location,
      workModel: preset.workModel,
      postAge: preset.postAge,
      includeNigerian: preset.includeNigerian,
    };
    setSearchParams(updated);
    executeSearch(updated);
  };

  const handleOpenSavedShortlist = () => {
    const savedEntries = Object.values(savedJobsMap);
    if (savedEntries.length === 0) return;
    if (rawResults.length === 0) {
      setRawResults(savedEntries.map((e) => e.job));
    }
    setOnlySavedJobs(true);
    switchScreen('delivery');
  };

  const handleWidenDateRange = () => {
    const updated = { ...searchParams, postAge: '30' };
    setSearchParams(updated);
    executeSearch(updated);
  };

  const handleDownloadCsv = () => {
    downloadCsv(sortedResults, searchParams.keywords);
    toast.success('Downloaded CSV export');
  };

  const handleDownloadJson = () => {
    downloadJson(sortedResults, searchParams.keywords);
    toast.success('Downloaded JSON export');
  };

  const handleEditSearch = () => {
    savedScrollYRef.current = window.scrollY;
    switchScreen('form');
  };

  const handleNewSearch = () => {
    setSearchParams({
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
      includeNigerian: true,
      deepScrape: false,
    });
    switchScreen('form');
  };

  const handleLaunchWorkspace = () => {
    transitionView('workspace');
  };

  const handleLaunchMock = () => {
    const mockJobs = generateMockJobs();
    const mockMet = getMockMetrics(150);
    setRawResults(mockJobs);
    setMetrics(mockMet);
    setSavedTimestamp(Date.now());
    setScreen('delivery');
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.pathname = '/app';
      url.searchParams.set('mock', '1');
      window.history.pushState({ view: 'workspace' }, '', url.toString());
    }
    transitionView('workspace', false);
  };

  const handleQuickSearch = (keyword: string, workModel: 'any' | 'remote' | 'hybrid' | 'in_person' = 'any', location = '') => {
    const targetModel = workModel === 'in_person' ? 'onsite' : workModel;
    const newParams: SearchParams = {
      ...searchParams,
      keywords: keyword,
      workModel: targetModel,
      location: location || searchParams.location,
    };
    setSearchParams(newParams);
    transitionView('workspace');
    setScreen('loading');
    setTimeout(() => {
      executeSearch(newParams);
    }, 40);
  };

  const handleSearchPlatforms = (platformIds: string[]) => {
    setSelectedPlatforms(platformIds);
    writeStorage('bp.selectedPlatforms', platformIds);
    transitionView('workspace');
    if (searchParams.keywords) {
      setTimeout(() => {
        executeSearch();
      }, 40);
    }
  };

  // Deliverable A: Marketing View (Midday.ai-inspired marketing experience at /)
  if (viewMode === 'marketing') {
    return (
      <div className="app-container min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
        <MarketingLanding
          theme={theme}
          onToggleTheme={handleToggleTheme}
          onLaunchWorkspace={handleLaunchWorkspace}
          onLaunchMock={handleLaunchMock}
          onQuickSearch={handleQuickSearch}
          onSearchPlatforms={handleSearchPlatforms}
          onOpenCommand={() => setCommandOpen(true)}
          searchParams={searchParams}
          setSearchParams={setSearchParams}
          selectedPlatforms={selectedPlatforms}
          setSelectedPlatforms={setSelectedPlatforms}
          onSubmit={(e) => {
            e.preventDefault();
            transitionView('workspace');
            executeSearch();
          }}
          recentSearches={recentSearches}
          onSelectRecentSearch={handleSelectRecentSearch}
        />

        {/* Command Palette */}
        <CommandPalette
          open={commandOpen}
          onOpenChange={setCommandOpen}
          onNewSearch={() => {
            transitionView('workspace');
            handleNewSearch();
          }}
          onEditSearch={() => {
            transitionView('workspace');
            handleEditSearch();
          }}
          onRunAgain={() => {
            transitionView('workspace');
            executeSearch();
          }}
          onClearSaved={handleClearSavedResults}
          onDownloadCsv={handleDownloadCsv}
          onDownloadJson={handleDownloadJson}
          onFocusFilter={() => {
            transitionView('workspace');
          }}
          onOpenShortcuts={() => setShortcutsOpen(true)}
          onSwitchToWorkspace={() => transitionView('workspace')}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          hasResults={rawResults.length > 0}
          hasSavedResults={Boolean(savedTimestamp)}
        />

        {/* Keyboard Shortcuts Modal */}
        <ShortcutsModal
          isOpen={shortcutsOpen}
          onClose={() => setShortcutsOpen(false)}
        />

        {/* Toast notifications */}
        <Toaster theme={theme} />
      </div>
    );
  }

  // Deliverable B: Core Product Workspace (/app or ?view=app or ?mock=1)
  return (
    <div className="app-container min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
      {/* Header with single shell alignment and Overview return link */}
      <Header
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onOpenCommand={() => setCommandOpen(true)}
        onResetSearch={() => switchScreen('form')}
        onBackToMarketing={() => transitionView('marketing')}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        {screen === 'form' && (
          <div className="page-shell py-8 sm:py-12">
            <SearchForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSubmit={handleSubmit}
              selectedPlatforms={selectedPlatforms}
              setSelectedPlatforms={setSelectedPlatforms}
              recentSearches={recentSearches}
              onSelectRecentSearch={handleSelectRecentSearch}
              savedCount={savedCount}
              onOpenSavedShortlist={handleOpenSavedShortlist}
            />
          </div>
        )}

        {screen === 'loading' && (
          <div className="page-shell py-8 sm:py-12 space-y-4">
            <TelemetryDeck
              metrics={metrics}
              totalResults={rawResults.length}
              isStreaming={true}
              streamingMessage={loadingMessage}
              onCancelStream={handleCancelSearch}
              showSummaryStrip={false}
            />
            <LoadingState onCancel={handleCancelSearch} statusMessage={loadingMessage} />
          </div>
        )}

        {screen === 'error' && (
          <div className="page-shell py-8 sm:py-12">
            <ErrorState
              message={errorMessage}
              isRateLimited={isRateLimited}
              onRetry={() => executeSearch()}
              onEditSearch={handleEditSearch}
            />
          </div>
        )}

        {screen === 'delivery' && (
          <div>
            {/* Sticky Search Summary Bar: Single quiet line with popover details */}
            <SearchSummaryBar
              searchParams={searchParams}
              totalResults={rawResults.length}
              metrics={metrics}
              savedTimestamp={savedTimestamp}
              isTelemetryOpen={telemetryOpen}
              onToggleTelemetry={() => setTelemetryOpen((prev) => !prev)}
              onEditSearch={handleEditSearch}
              onNewSearch={handleNewSearch}
              onRunAgain={() => executeSearch()}
              onClearSaved={handleClearSavedResults}
              onDownloadCsv={handleDownloadCsv}
              onDownloadJson={handleDownloadJson}
              onCopyShareLink={handleCopyShareLink}
            />

            {/* Filter Toolbar with Kbd hint, Selects, Toggles, and Count */}
            {(rawResults.length > 0 || onlySavedJobs) && (
              <Toolbar
                tableSearch={tableSearch}
                setTableSearch={setTableSearch}
                providerFilter={providerFilter}
                setProviderFilter={setProviderFilter}
                remoteFilter={remoteFilter}
                setRemoteFilter={setRemoteFilter}
                employmentFilter={employmentFilter}
                setEmploymentFilter={setEmploymentFilter}
                onlySalaryListed={onlySalaryListed}
                setOnlySalaryListed={setOnlySalaryListed}
                onlySavedJobs={onlySavedJobs}
                setOnlySavedJobs={setOnlySavedJobs}
                savedCount={savedCount}
                availableProviders={availableProviders}
                availableEmploymentTypes={availableEmploymentTypes}
                totalResults={onlySavedJobs ? normalizedList.length : rawResults.length}
                filteredCount={sortedResults.length}
                onClearFilters={handleClearFilters}
                searchInputRef={searchInputRef}
                onDownloadCsv={handleDownloadCsv}
                onDownloadJson={handleDownloadJson}
              />
            )}

            <div className="page-shell py-4" ref={resultsContainerRef}>
              {/* Collapsible Prompt Kit Telemetry Deck */}
              {metrics && (
                <TelemetryDeck
                  metrics={metrics}
                  totalResults={rawResults.length}
                  isStreaming={false}
                  savedTimestamp={savedTimestamp}
                  isOpen={telemetryOpen}
                  onToggleOpen={() => setTelemetryOpen((prev) => !prev)}
                  showSummaryStrip={false}
                  onRunAgain={() => executeSearch()}
                  onClearSaved={handleClearSavedResults}
                />
              )}
              {rawResults.length === 0 && !onlySavedJobs ? (
                <NoResultsState
                  onWidenDateRange={handleWidenDateRange}
                  onClearFilters={handleClearFilters}
                  onNewSearch={handleNewSearch}
                />
              ) : (
                <div className="mt-2">
                  {sortedResults.length === 0 ? (
                    <div className="border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-[var(--ink-muted)]">
                      <p className="font-semibold text-body text-[var(--ink)] mb-2">
                        No postings match the active filters
                      </p>
                      <p className="text-small mb-4 text-[var(--ink-muted)]">
                        Try clearing search keywords, remote status, or platform filters.
                      </p>
                      <button
                        type="button"
                        className="h-9 px-3 text-small font-medium border border-[var(--border-strong)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors"
                        onClick={handleClearFilters}
                      >
                        Clear filters
                      </button>
                    </div>
                  ) : (
                    <>
                      {/* Desktop fixed-layout table */}
                      <div className="table-desktop-view hidden md:block">
                        <ResultsTable
                          jobs={sortedResults}
                          sortField={sortField}
                          sortAsc={sortAsc}
                          onSort={handleSort}
                          selectedJobId={selectedJob?.id || null}
                          onSelectJob={(job) => {
                            setSelectedJob(job);
                            handleMarkVisited(job.apply_url || job.id);
                          }}
                          activeRowIndex={activeRowIndex}
                          savedJobsMap={savedJobsMap}
                        />
                      </div>

                      {/* Mobile cards */}
                      <div className="block md:hidden">
                        <ResultsCards
                          jobs={sortedResults}
                          selectedJobId={selectedJob?.id || null}
                          onSelectJob={(job) => {
                            setSelectedJob(job);
                            handleMarkVisited(job.apply_url || job.id);
                          }}
                          savedJobsMap={savedJobsMap}
                        />
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Floating Scroll Button for seamless return-to-top */}
        <ScrollButton />
      </main>

      {/* Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        onNewSearch={handleNewSearch}
        onEditSearch={handleEditSearch}
        onRunAgain={() => executeSearch()}
        onClearSaved={handleClearSavedResults}
        onDownloadCsv={handleDownloadCsv}
        onDownloadJson={handleDownloadJson}
        onFocusFilter={() => {
          if (screen === 'delivery') {
            searchInputRef.current?.focus();
          }
        }}
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onSwitchToMarketing={() => transitionView('marketing')}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        hasResults={rawResults.length > 0}
        hasSavedResults={Boolean(savedTimestamp)}
      />

      {/* Detail Sheet Overlay */}
      <DetailSheet
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onMarkVisited={handleMarkVisited}
        isSaved={Boolean(selectedJob && savedJobsMap[selectedJob.id])}
        savedStage={selectedJob ? savedJobsMap[selectedJob.id]?.stage || null : null}
        onToggleSave={handleToggleSave}
        onChangeStage={handleChangeStage}
      />

      {/* Keyboard Shortcuts Modal */}
      <ShortcutsModal
        isOpen={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      {/* Toast notifications */}
      <Toaster theme={theme} />
    </div>
  );
}

export default App;
