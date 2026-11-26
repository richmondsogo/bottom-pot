import React, { useState, useMemo, useRef, useEffect, Suspense, lazy, useDeferredValue } from 'react';
import type {
  EligibilityFilterMode,
  JobListing,
  NormalizedJob,
  DoneMetrics,
  SearchParams,
  SortField,
} from './types';
import { normalizeJob } from './lib/normalize';
import { normalizeCountryCode } from './lib/countries';
import { readStorage, writeStorage } from './lib/storage';
import { markVisited } from './lib/visited';
import { filterJobs } from './lib/filter';
import { sortJobs } from './lib/sort';
import { isMockModeActive, getMockModeType, generateMockJobs, getMockMetrics } from './lib/mock';
import { downloadCsv, downloadJson } from './lib/export';
import {
  getSavedJobsMap,
  isJobSaved,
  toggleSavedJob,
  updateSavedJobStage,
  STAGE_LABELS,
  type ApplicationStage,
  type SavedJobEntry,
} from './lib/savedJobs';
import { matchesJobIdentity, upsertJobBatch } from './lib/identity';
import {
  getRecentSearches,
  recordRecentSearch,
  readStateFromUrl,
  syncStateToUrl,
  buildShareableSearchUrl,
  type RecentSearchPreset,
} from './lib/urlState';

import { ALL_PLATFORMS } from './lib/constants';
import { applyNgToPlatforms } from './lib/nigerianPlatforms';
import { migrateStoredPlatforms, CURRENT_PLATFORM_VERSION } from './lib/platformMigration';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { HomePage } from './pages/HomePage';
import { verifyAdminSession, logoutAdmin } from './lib/adminAuth';
import { resolveRoute, routeToPath, type AppRoute } from './lib/router';
import { runViewTransition } from './lib/viewTransition';
import { apiCredentials, apiUrl } from './lib/apiBase';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';

const ProductPage = lazy(() => import('./pages/ProductPage').then((m) => ({ default: m.ProductPage })));
const SourcesPage = lazy(() => import('./pages/SourcesPage').then((m) => ({ default: m.SourcesPage })));
const AboutPage = lazy(() => import('./pages/AboutPage').then((m) => ({ default: m.AboutPage })));
const Workspace = lazy(() => import('./components/Workspace').then((m) => ({ default: m.Workspace })));
const AdminLogin = lazy(() => import('./components/AdminLogin').then((m) => ({ default: m.AdminLogin })));
const CommandPalette = lazy(() => import('./components/CommandPalette').then((m) => ({ default: m.CommandPalette })));
const ShortcutsModal = lazy(() => import('./components/ShortcutsModal').then((m) => ({ default: m.ShortcutsModal })));
const BottomPotEasterEgg = lazy(() => import('./components/BottomPotEasterEgg').then((m) => ({ default: m.BottomPotEasterEgg })));

export function App() {
  // Admin route & authentication state ('checking' | 'anonymous' | 'authenticated')
  const [isAdminRoute, setIsAdminRoute] = useState<boolean>(() => {
    return typeof window !== 'undefined' && window.location.pathname === '/admin';
  });
  const [adminAuth, setAdminAuth] = useState<'checking' | 'anonymous' | 'authenticated'>(() => {
    if (typeof window !== 'undefined' && window.location.pathname === '/admin') {
      return 'checking';
    }
    return 'anonymous';
  });
  const autoSearchDecidedRef = useRef(false);
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

  // Command palette & 5% easter egg state
  const [commandOpen, setCommandOpen] = useState(false);
  const [easterEggOpen, setEasterEggOpen] = useState(false);

  // Initial URL state (if shared/bookmarked link was opened)
  const initialUrlState = useMemo(() => readStateFromUrl(), []);

  // Telemetry Deck disclosure state in workspace
  const [telemetryOpen, setTelemetryOpen] = useState(false);

  // Multi-page SPA router: 'home' | 'search' | 'product' | 'sources' | 'about' | 'admin'
  const [route, setRoute] = useState<AppRoute>(() => {
    if (typeof window !== 'undefined') {
      return resolveRoute(window.location.pathname, window.location.search);
    }
    return 'home';
  });
  const isWorkspaceRoute = route === 'search' || route === 'admin';

  // Native View Transition Helper with Reduced-Motion Fallback (ADR 0014)
  const navigateTo = (targetRoute: AppRoute, updateUrl = true) => {
    const applyRoute = () => {
      setRoute(targetRoute);
      if (updateUrl && typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        if (targetRoute === 'search') {
          if (url.pathname !== '/app' && url.pathname !== '/admin') {
            url.pathname = '/app';
          }
          url.searchParams.delete('view');
        } else if (targetRoute === 'admin') {
          url.pathname = '/admin';
          url.searchParams.delete('view');
        } else {
          url.pathname = routeToPath(targetRoute);
          for (const key of ['view', 'q', 'loc', 'wm', 'age', 'ng', 'cc', 'elig', 'flt', 'prov', 'rem', 'emp', 'sal', 'saved']) {
            url.searchParams.delete(key);
          }
        }
        setIsAdminRoute(url.pathname === '/admin');
        autoSearchDecidedRef.current = false;
        window.history.pushState({ route: targetRoute }, '', url.toString());
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    };

    runViewTransition(applyRoute);
  };

  // Popstate history listener for Back/Forward browser navigation
  useEffect(() => {
    const handlePopState = () => {
      const nextRoute = resolveRoute(window.location.pathname, window.location.search);
      const onAdmin = window.location.pathname === '/admin';
      setIsAdminRoute(onAdmin);
      autoSearchDecidedRef.current = false;
      setRoute(nextRoute);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // One admin session verification effect, keyed on isAdminRoute only
  useEffect(() => {
    if (!isAdminRoute) return;
    setAdminAuth('checking');
    let active = true;
    verifyAdminSession().then((isAuthed) => {
      if (active) {
        setAdminAuth(isAuthed ? 'authenticated' : 'anonymous');
      }
    });
    return () => {
      active = false;
    };
  }, [isAdminRoute]);

  // Persistence: search parameters
  const [searchParams, setSearchParams] = useState<SearchParams>(() => {
    const stored = readStorage<SearchParams>('bp.searchParams', {
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
    });
    return initialUrlState?.searchParams
      ? { ...stored, ...initialUrlState.searchParams }
      : stored;
  });

  // Platform selection state with versioned migration and select-none preservation
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(() => {
    const stored = readStorage<string[] | null>('bp.selectedPlatforms', null);
    const storedVersion = readStorage<string | null>('bp.platforms.version', null);
    const migration = migrateStoredPlatforms(stored, storedVersion);

    if (migration.migrated || storedVersion !== migration.version) {
      writeStorage('bp.selectedPlatforms', migration.platforms);
      writeStorage('bp.platforms.version', migration.version);
    }

    const urlNg = initialUrlState?.ngParam ?? null;
    return applyNgToPlatforms(migration.platforms, urlNg);
  });

  // Selectable applicant country ("Where can you work from?"): defaults unset (''), never inferred from network
  const [applicantCountry, setApplicantCountryState] = useState<string>(() => {
    if (initialUrlState?.applicantCountry !== undefined) {
      return initialUrlState.applicantCountry;
    }
    const stored = readStorage<string>('bp.applicantCountry', '');
    return normalizeCountryCode(stored) || '';
  });

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
  const [eligibilityFilter, setEligibilityFilter] = useState<EligibilityFilterMode>(
    () => initialUrlState?.eligibilityFilter ?? readStorage<EligibilityFilterMode>('bp.filter.eligibility', '')
  );
  const setApplicantCountry = (rawCode: string) => {
    const normalized = normalizeCountryCode(rawCode) || '';
    setApplicantCountryState(normalized);
    if (!normalized) {
      setEligibilityFilter('');
    }
  };
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
    runViewTransition(() => {
      setScreen(newScreen);
    });
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
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [, setVisitedVersion] = useState(0);

  const abortControllerRef = useRef<AbortController | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  const savedScrollYRef = useRef<number>(0);

  // Save changes to localStorage
  useEffect(() => { writeStorage('bp.searchParams', searchParams); }, [searchParams]);
  useEffect(() => {
    writeStorage('bp.selectedPlatforms', selectedPlatforms);
    writeStorage('bp.platforms.version', CURRENT_PLATFORM_VERSION);
  }, [selectedPlatforms]);
  useEffect(() => { writeStorage('bp.applicantCountry', applicantCountry); }, [applicantCountry]);
  useEffect(() => { writeStorage('bp.filter.search', tableSearch); }, [tableSearch]);
  useEffect(() => { writeStorage('bp.filter.provider', providerFilter); }, [providerFilter]);
  useEffect(() => { writeStorage('bp.filter.remote', remoteFilter); }, [remoteFilter]);
  useEffect(() => { writeStorage('bp.filter.employment', employmentFilter); }, [employmentFilter]);
  useEffect(() => { writeStorage('bp.filter.eligibility', eligibilityFilter); }, [eligibilityFilter]);
  useEffect(() => { writeStorage('bp.filter.salaryOnly', onlySalaryListed); }, [onlySalaryListed]);
  useEffect(() => { writeStorage('bp.sort.field', sortField); }, [sortField]);
  useEffect(() => { writeStorage('bp.sort.asc', sortAsc); }, [sortAsc]);

  // Sync active delivery search & filter state to URL query parameters
  useEffect(() => {
    if (!isWorkspaceRoute) {
      return;
    }
    if (isAdminRoute && adminAuth !== 'authenticated') {
      return;
    }
    syncStateToUrl(
      screen,
      {
        searchParams,
        selectedPlatforms,
        applicantCountry,
        eligibilityFilter,
        tableSearch,
        providerFilter,
        remoteFilter,
        employmentFilter,
        onlySalaryListed,
        onlySavedJobs,
      },
      isWorkspaceRoute
    );
  }, [
    isAdminRoute,
    adminAuth,
    screen,
    isWorkspaceRoute,
    searchParams,
    selectedPlatforms,
    applicantCountry,
    eligibilityFilter,
    tableSearch,
    providerFilter,
    remoteFilter,
    employmentFilter,
    onlySalaryListed,
    onlySavedJobs,
  ]);

  // If opened directly on /search, /app, or /admin with a search query and no saved results, trigger search
  useEffect(() => {
    if (autoSearchDecidedRef.current) return;
    if (isAdminRoute && adminAuth !== 'authenticated') {
      return;
    }
    autoSearchDecidedRef.current = true;
    if (
      isWorkspaceRoute &&
      initialUrlState?.searchParams?.keywords &&
      !savedResultsData?.rawResults?.length &&
      !isMockModeActive()
    ) {
      executeSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdminRoute, adminAuth]);


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

  const evaluatedEligibilityKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const evaluatedKeys = evaluatedEligibilityKeysRef.current;
    if (rawResults.length === 0) {
      evaluatedKeys.clear();
      return;
    }
    if (isMockModeActive()) return;
    const cc = normalizeCountryCode(applicantCountry);
    if (!cc) return;

    const pending = rawResults.filter((job) => {
      const existingCc = normalizeCountryCode(job.eligibility?.applicant_assessment?.applicant_country_code);
      if (existingCc === cc) return false;
      return !evaluatedKeys.has(`${cc}::${job.id}`);
    });
    if (pending.length === 0) return;

    for (const job of pending) {
      evaluatedKeys.add(`${cc}::${job.id}`);
    }

    let settled = false;
    const controller = new AbortController();
    fetch(apiUrl('/api/eligibility/evaluate'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        applicant_country: cc,
        jobs: pending.map((job) => ({
          id: job.id,
          eligibility: job.eligibility ?? null,
          work_model: job.work_model ?? null,
          location: job.location ?? null,
        })),
      }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        settled = true;
        const assessments = data?.assessments;
        if (!assessments || typeof assessments !== 'object') return;
        setRawResults((prev) => {
          let changed = false;
          const next = prev.map((job) => {
            const assessment = assessments[job.id];
            if (!assessment) return job;
            changed = true;
            return {
              ...job,
              eligibility: {
                ...(job.eligibility ?? {}),
                applicant_assessment: assessment,
              },
            };
          });
          return changed ? next : prev;
        });
      })
      .catch(() => {
        settled = true;
      });

    return () => {
      if (!settled) {
        for (const job of pending) {
          evaluatedKeys.delete(`${cc}::${job.id}`);
        }
      }
      controller.abort();
    };
  }, [applicantCountry, rawResults]);

  // Normalization (when onlySavedJobs is active, include any saved jobs not in rawResults)
  const normalizedList = useMemo(() => {
    const nowMs = Date.now();
    if (!onlySavedJobs) {
      return rawResults.map((job) => normalizeJob(job, nowMs, applicantCountry));
    }
    const byId = new Map<string, JobListing>();
    for (const job of rawResults) {
      if (isJobSaved(job, savedJobsMap)) {
        byId.set(job.id, job);
      }
    }
    for (const entry of Object.values(savedJobsMap)) {
      let alreadyPresent = false;
      for (const existing of byId.values()) {
        if (matchesJobIdentity(existing, entry.job)) {
          alreadyPresent = true;
          break;
        }
      }
      if (!alreadyPresent) {
        byId.set(entry.job.id, entry.job);
      }
    }
    return Array.from(byId.values()).map((job) => normalizeJob(job, nowMs, applicantCountry));
  }, [rawResults, onlySavedJobs, savedJobsMap, applicantCountry]);

  useEffect(() => {
    setSelectedJob((prev) => {
      if (!prev) return prev;
      const refreshed = normalizedList.find((item) => matchesJobIdentity(item, prev));
      return refreshed ?? normalizeJob(prev, Date.now(), applicantCountry);
    });
  }, [normalizedList, applicantCountry]);

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

  // Pure filtering with deferred text search for smooth keystrokes on large result lists
  const deferredTableSearch = useDeferredValue(tableSearch);
  const filteredResults = useMemo(() => {
    return filterJobs(normalizedList, {
      search: deferredTableSearch,
      provider: providerFilter,
      remote: remoteFilter,
      employment: employmentFilter,
      salaryOnly: onlySalaryListed,
      applicantCountry,
      eligibilityFilter,
    });
  }, [
    normalizedList,
    deferredTableSearch,
    providerFilter,
    remoteFilter,
    employmentFilter,
    onlySalaryListed,
    applicantCountry,
    eligibilityFilter,
  ]);

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

      // Ignore modifier keys (Cmd, Ctrl, Alt) for single-key navigation shortcuts
      if (e.metaKey || e.ctrlKey || e.altKey) {
        return;
      }

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

  // 5% Easter egg: typing "jollof" on /about outside text inputs
  useEffect(() => {
    if (route !== 'about') return;
    let typed = '';
    const onType = (e: KeyboardEvent) => {
      const target = document.activeElement;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.getAttribute('contenteditable') === 'true'
      ) {
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || e.key.length !== 1) return;
      typed = (typed + e.key.toLowerCase()).slice(-6);
      if (typed === 'jollof') {
        setEasterEggOpen(true);
        typed = '';
      }
    };
    window.addEventListener('keydown', onType);
    return () => window.removeEventListener('keydown', onType);
  }, [route]);

  // Search execution
  const executeSearch = async (customParams?: SearchParams, platformsOverride?: string[]) => {
    const paramsToUse = customParams || searchParams;
    const activePlatforms = platformsOverride ?? selectedPlatforms;
    setRecentSearches(recordRecentSearch(paramsToUse));
    setRawResults([]);
    setMetrics(null);
    setSelectedJob(null);
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setEligibilityFilter('');
    setOnlySalaryListed(false);
    setOnlySavedJobs(false);
    setSortField(null);
    setActiveRowIndex(-1);
    setIsRateLimited(false);
    setIsStreaming(true);
    switchScreen('loading');
    setLoadingMessage('Checking monitored boards and direct sources...');

    // If Mock Mode is active, simulate without network or live Serper credits
    if (isMockModeActive()) {
      const mode = getMockModeType();
      const delay = mode === 'slow' ? 3000 : 700;

      setTimeout(() => {
        setIsStreaming(false);
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
    });

    if (paramsToUse.location.trim()) {
      queryParams.set('location', paramsToUse.location.trim());
    }
    if (paramsToUse.workModel !== 'any') {
      queryParams.set('remote', String(paramsToUse.workModel === 'remote'));
    }
    if (activePlatforms.length === 0) {
      queryParams.set('platforms', '');
    } else if (activePlatforms.length < ALL_PLATFORMS.length) {
      queryParams.set('platforms', activePlatforms.join(','));
    }
    if (applicantCountry) {
      queryParams.set('applicant_country', applicantCountry);
    }

    let accumulatedResults: JobListing[] = [];
    let finalMetrics: DoneMetrics | null = null;
    let revealedDelivery = false;
    let switchedOnDone = false;

    try {
      const response = await fetch(apiUrl(`/search?${queryParams.toString()}`), {
        signal: controller.signal,
        credentials: apiCredentials(),
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
              const { results: updated } = upsertJobBatch(accumulatedResults, batch);
              accumulatedResults = updated;
              setRawResults(accumulatedResults);

              if (accumulatedResults.length > 0 && !revealedDelivery) {
                revealedDelivery = true;
                switchScreen('delivery');
              }

              // Preserve selection: if selectedJob matches an upgraded item, update it in place
              if (selectedJob) {
                for (const item of batch) {
                  if (matchesJobIdentity(item, selectedJob)) {
                    setSelectedJob(normalizeJob(item, Date.now(), applicantCountry));
                    break;
                  }
                }
              }

              setLoadingMessage(`Found ${accumulatedResults.length} open roles...`);
            } else if (eventName === 'done') {
              finalMetrics = payload as DoneMetrics;
              setMetrics(finalMetrics);
              persistResults(accumulatedResults, finalMetrics);
              setIsStreaming(false);
              if (!revealedDelivery) {
                switchScreen('delivery');
              }
              switchedOnDone = true;
            } else if (eventName === 'error') {
              throw new Error(payload.message || 'Search execution failed');
            }

            eventName = '';
            eventData = '';
          }
        }
      }

      if (!switchedOnDone && !revealedDelivery) {
        persistResults(accumulatedResults, finalMetrics);
        switchScreen('delivery');
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        if (!revealedDelivery) {
          switchScreen('form');
        } else {
          setMetrics((prev) => prev ?? { total: accumulatedResults.length, partial: true });
        }
      } else {
        const message = err instanceof Error ? err.message : String(err);
        setErrorMessage(message);
        switchScreen('error');
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch();
  };

  const handleCancelSearch = () => {
    setIsStreaming(false);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (screen !== 'delivery') {
      switchScreen('form');
    }
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
    setEligibilityFilter('');
    setOnlySalaryListed(false);
    setOnlySavedJobs(false);
  };

  const handleCopyShareLink = () => {
    const shareUrl = buildShareableSearchUrl(
      {
        searchParams,
        selectedPlatforms,
        applicantCountry,
        eligibilityFilter,
        tableSearch,
        providerFilter,
        remoteFilter,
        employmentFilter,
        onlySalaryListed,
        onlySavedJobs,
      },
      isAdminRoute ? '/app' : undefined
    );
    if (shareUrl && navigator.clipboard) {
      navigator.clipboard.writeText(shareUrl);
      toast.success('Copied shareable search link');
    }
  };

  const handleAdminLogout = async () => {
    if (screen === 'loading') {
      handleCancelSearch();
    }
    await logoutAdmin();
    setAdminAuth('anonymous');
  };

  const handleSelectRecentSearch = (preset: RecentSearchPreset) => {
    const updated: SearchParams = {
      ...searchParams,
      keywords: preset.keywords,
      location: preset.location,
      workModel: preset.workModel,
      postAge: preset.postAge,
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
    if (route !== 'search' && route !== 'admin') {
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.pathname = '/app';
        url.searchParams.delete('view');
        setIsAdminRoute(false);
        autoSearchDecidedRef.current = true;
        window.history.pushState({ route: 'search' }, '', url.toString());
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
      setRoute('search');
    }
    switchScreen('delivery');
  };

  const handleHeroSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchParams.keywords.trim()) return;
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.pathname = '/app';
      url.searchParams.delete('view');
      setIsAdminRoute(false);
      autoSearchDecidedRef.current = true;
      window.history.pushState({ route: 'search' }, '', url.toString());
      window.scrollTo({ top: 0, behavior: 'auto' });
    }
    setRoute('search');
    executeSearch(searchParams, selectedPlatforms);
  };

  const handleWidenDateRange = () => {
    const updated = { ...searchParams, postAge: '30' };
    setSearchParams(updated);
    executeSearch(updated);
  };

  const handleDownloadCsv = () => {
    downloadCsv(sortedResults, searchParams.keywords, mode);
    toast.success('Downloaded CSV export');
  };

  const handleDownloadJson = () => {
    downloadJson(sortedResults, searchParams.keywords, mode);
    toast.success('Downloaded JSON export');
  };

  const handleEditSearch = () => {
    savedScrollYRef.current = window.scrollY;
    switchScreen('form');
  };

  const handleNewSearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    const allPlatformIds = ALL_PLATFORMS.map((p) => p.id);
    setSelectedPlatforms(allPlatformIds);
    writeStorage('bp.selectedPlatforms', allPlatformIds);
    writeStorage('bp.platforms.version', CURRENT_PLATFORM_VERSION);
    setIsStreaming(false);
    setOnlySavedJobs(false);
    setSelectedJob(null);
    setSearchParams({
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
    });
    switchScreen('form');
  };

  const handleStartNewSearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    const allPlatformIds = ALL_PLATFORMS.map((p) => p.id);
    setSelectedPlatforms(allPlatformIds);
    writeStorage('bp.selectedPlatforms', allPlatformIds);
    writeStorage('bp.platforms.version', CURRENT_PLATFORM_VERSION);
    setIsStreaming(false);
    setOnlySavedJobs(false);
    setSelectedJob(null);
    setSearchParams({
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
    });
    runViewTransition(() => {
      setScreen('form');
      setRoute('search');
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.pathname = '/app';
        for (const key of ['view', 'q', 'loc', 'wm', 'age', 'ng', 'cc', 'elig', 'flt', 'prov', 'rem', 'emp', 'sal', 'saved']) {
          url.searchParams.delete(key);
        }
        setIsAdminRoute(false);
        autoSearchDecidedRef.current = true;
        window.history.pushState({ route: 'search' }, '', url.toString());
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    });
  };

  const handleSearchPlatforms = (platformIds: string[]) => {
    setSelectedPlatforms(platformIds);
    writeStorage('bp.selectedPlatforms', platformIds);
    writeStorage('bp.platforms.version', CURRENT_PLATFORM_VERSION);
    if (searchParams.keywords.trim()) {
      navigateTo('search');
      executeSearch(searchParams, platformIds);
      return;
    }
    setOnlySavedJobs(false);
    setSelectedJob(null);
    setScreen('form');
    navigateTo('search');
  };

  // Mode prop: 'admin' if on /admin and authenticated; else 'user'
  const mode: 'user' | 'admin' =
    isAdminRoute && adminAuth === 'authenticated' ? 'admin' : 'user';

  // Public Editorial & Info Pages (/, /product, /sources, /about)
  if (route === 'home' || route === 'product' || route === 'sources' || route === 'about') {
    return (
      <div className="app-container min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
        <Header
          activeRoute={route}
          onNavigate={navigateTo}
          onStartNewSearch={handleStartNewSearch}
          onOpenShortcuts={() => setShortcutsOpen(true)}
          onOpenCommand={() => setCommandOpen(true)}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          mode={mode}
        />

        <main className="flex-1">
          {route === 'home' && (
            <HomePage
              onNavigate={navigateTo}
              onStartNewSearch={handleStartNewSearch}
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSearchSubmit={handleHeroSearchSubmit}
              selectedPlatforms={selectedPlatforms}
              setSelectedPlatforms={setSelectedPlatforms}
              applicantCountry={applicantCountry}
              onChangeApplicantCountry={setApplicantCountry}
              savedCount={savedCount}
              onOpenSavedShortlist={handleOpenSavedShortlist}
            />
          )}
          <Suspense fallback={null}>
            {route === 'product' && (
              <ProductPage onNavigate={navigateTo} onStartNewSearch={handleStartNewSearch} />
            )}
            {route === 'sources' && (
              <SourcesPage
                onNavigate={navigateTo}
                onSearchPlatforms={handleSearchPlatforms}
                onStartNewSearch={handleStartNewSearch}
              />
            )}
            {route === 'about' && (
              <AboutPage onNavigate={navigateTo} onStartNewSearch={handleStartNewSearch} />
            )}
          </Suspense>
        </main>

        <Footer
          activeRoute={route}
          onNavigate={navigateTo}
          onNewSearch={handleStartNewSearch}
          onOpenShortcuts={() => setShortcutsOpen(true)}
          onLogoEasterEgg={() => setEasterEggOpen(true)}
        />

        {mode === 'admin' && (
          <Suspense fallback={null}>
            <CommandPalette
              open={commandOpen}
              onOpenChange={setCommandOpen}
              onNewSearch={handleStartNewSearch}
              onEditSearch={() => {
                navigateTo('search');
                handleEditSearch();
              }}
              onRunAgain={() => {
                navigateTo('search');
                executeSearch();
              }}
              onClearSaved={handleClearSavedResults}
              onDownloadCsv={handleDownloadCsv}
              onDownloadJson={handleDownloadJson}
              onFocusFilter={() => {
                navigateTo('search');
              }}
              onOpenShortcuts={() => setShortcutsOpen(true)}
              onSwitchToWorkspace={() => navigateTo('search')}
              theme={theme}
              onToggleTheme={handleToggleTheme}
              hasResults={rawResults.length > 0}
              hasSavedResults={Boolean(savedTimestamp)}
            />
          </Suspense>
        )}

        {shortcutsOpen && (
          <Suspense fallback={null}>
            <ShortcutsModal
              isOpen={shortcutsOpen}
              onClose={() => setShortcutsOpen(false)}
              mode={mode}
            />
          </Suspense>
        )}

        {easterEggOpen && (
          <Suspense fallback={null}>
            <BottomPotEasterEgg
              open={easterEggOpen}
              onClose={() => setEasterEggOpen(false)}
              theme={theme}
            />
          </Suspense>
        )}

        <Toaster theme={theme} />
      </div>
    );
  }

  if (isAdminRoute && adminAuth !== 'authenticated') {
    if (adminAuth === 'checking') {
      return (
        <div
          className="min-h-screen w-full transition-colors duration-150"
          style={{ backgroundColor: 'var(--bg)' }}
          aria-busy="true"
          aria-label="Verifying administrator session"
        />
      );
    }
    return (
      <Suspense fallback={null}>
        <AdminLogin
          onLoginSuccess={() => {
            setAdminAuth('authenticated');
          }}
        />
      </Suspense>
    );
  }

  // Deliverable B: Core Product Workspace (/app or ?view=app or ?mock=1 or authenticated /admin)
  return (
    <>
      <Suspense fallback={null}>
        <Workspace
        mode={mode}
        onLogout={handleAdminLogout}
        search={{
          searchParams,
          setSearchParams,
          handleSubmit,
          handleCancelSearch,
          handleEditSearch,
          handleNewSearch,
          executeSearch,
          selectedPlatforms,
          setSelectedPlatforms,
          applicantCountry,
          setApplicantCountry,
          recentSearches,
          handleSelectRecentSearch,
          savedCount,
          handleOpenSavedShortlist,
          handleWidenDateRange,
          loadingMessage,
          errorMessage,
          isRateLimited,
        }}
        filters={{
          tableSearch,
          setTableSearch,
          providerFilter,
          setProviderFilter,
          remoteFilter,
          setRemoteFilter,
          employmentFilter,
          setEmploymentFilter,
          eligibilityFilter,
          setEligibilityFilter,
          onlySalaryListed,
          setOnlySalaryListed,
          onlySavedJobs,
          setOnlySavedJobs,
          availableProviders,
          availableEmploymentTypes,
          handleClearFilters,
          searchInputRef,
        }}
        results={{
          rawResults,
          normalizedList,
          sortedResults,
          metrics,
          savedTimestamp,
          savedJobsMap,
          sortField,
          sortAsc,
          handleSort,
          selectedJob,
          setSelectedJob,
          activeRowIndex,
          handleMarkVisited,
          handleToggleSave,
          handleChangeStage,
          handleClearSavedResults,
          handleDownloadCsv,
          handleDownloadJson,
          handleCopyShareLink,
          resultsContainerRef,
        }}
        shell={{
          activeRoute: route,
          onNavigate: navigateTo,
          isStreaming,
          screen,
          switchScreen,
          theme,
          handleToggleTheme,
          telemetryOpen,
          setTelemetryOpen,
          commandOpen,
          setCommandOpen,
          shortcutsOpen,
          setShortcutsOpen,
          onLogoEasterEgg: () => setEasterEggOpen(true),
        }}
        />
      </Suspense>
      {easterEggOpen && (
        <Suspense fallback={null}>
          <BottomPotEasterEgg
            open={easterEggOpen}
            onClose={() => setEasterEggOpen(false)}
            theme={theme}
          />
        </Suspense>
      )}
    </>
  );
}

export default App;
