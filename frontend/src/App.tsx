import React, { useState, useMemo, useRef, useEffect } from 'react';
import type { JobListing, DoneMetrics, SearchParams, SortField, ColumnDef } from './types';
import { normalizeJob } from './lib/normalize';
import { downloadCsv, downloadJson } from './lib/export';
import { readStorage, writeStorage } from './lib/storage';
import { SearchForm } from './components/SearchForm';
import { StatusBanner } from './components/StatusBanner';
import { Toolbar } from './components/Toolbar';
import { SearchInfo } from './components/SearchInfo';
import { FilterBar } from './components/FilterBar';
import { ResultsTable } from './components/ResultsTable';

const DEFAULT_COLUMNS: ColumnDef[] = [
  { id: 'role', label: 'Role', defaultWidth: 300, sortField: 'title' },
  { id: 'company', label: 'Company', defaultWidth: 190, sortField: 'company' },
  { id: 'location', label: 'Location', defaultWidth: 180 },
  { id: 'salary', label: 'Salary', defaultWidth: 110, sortField: 'salary' },
  { id: 'job_type', label: 'Job type', defaultWidth: 110 },
  { id: 'work_model', label: 'Work model', defaultWidth: 120 },
  { id: 'posted', label: 'Posted date', defaultWidth: 110, sortField: 'date' },
  { id: 'source', label: 'Source', defaultWidth: 110 },
  { id: 'actions', label: '', defaultWidth: 150 },
];

const MIN_COL_WIDTH = 70;

export function App() {
  // Persistence: form params
  const [searchParams, setSearchParams] = useState<SearchParams>(() =>
    readStorage<SearchParams>('bp.searchParams', {
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
      includeNigerian: true,
      deepScrape: false,
    })
  );

  // Persistence: density
  const [density, setDensity] = useState<'comfortable' | 'compact'>(() =>
    readStorage<'comfortable' | 'compact'>('bp.density', 'comfortable')
  );

  // Persistence: filters
  const [tableSearch, setTableSearch] = useState(() => readStorage<string>('bp.filter.search', ''));
  const [providerFilter, setProviderFilter] = useState(() => readStorage<string>('bp.filter.provider', ''));
  const [remoteFilter, setRemoteFilter] = useState(() => readStorage<string>('bp.filter.remote', ''));
  const [employmentFilter, setEmploymentFilter] = useState(() => readStorage<string>('bp.filter.employment', ''));
  const [onlySalaryListed, setOnlySalaryListed] = useState(() =>
    readStorage<boolean>('bp.filter.salaryOnly', false)
  );
  const [onlyNigerianBoards, setOnlyNigerianBoards] = useState(() =>
    readStorage<boolean>('bp.filter.nigerianOnly', false)
  );

  // Persistence: sort & pagination
  const [sortField, setSortField] = useState<SortField>(() => readStorage<SortField>('bp.sort.field', null));
  const [sortAsc, setSortAsc] = useState<boolean>(() => readStorage<boolean>('bp.sort.asc', true));
  const [currentPage, setCurrentPage] = useState<number>(() => readStorage<number>('bp.page.current', 1));
  const [pageSize, setPageSize] = useState<number>(() => readStorage<number>('bp.page.size', 20));

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
          extractionSummary: string;
          savedAt: number;
        };
      }
    } catch {
      // ignore corrupt data
    }
    return null;
  }, []);

  const [rawResults, setRawResults] = useState<JobListing[]>(() => savedResultsData?.rawResults || []);
  const [metrics, setMetrics] = useState<DoneMetrics | null>(() => savedResultsData?.metrics || null);
  const [extractionSummary, setExtractionSummary] = useState<string>(
    () => savedResultsData?.extractionSummary || ''
  );
  const [savedTimestamp, setSavedTimestamp] = useState<number | null>(
    () => savedResultsData?.savedAt || null
  );

  const [screen, setScreen] = useState<'form' | 'processing' | 'delivery' | 'error'>(() =>
    savedResultsData && savedResultsData.rawResults.length > 0 ? 'delivery' : 'form'
  );

  // Streaming & error state
  const [liveConsoleMessage, setLiveConsoleMessage] = useState('Connecting to the search pipeline...');
  const [activeSources, setActiveSources] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [isRateLimited, setIsRateLimited] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Details, copy feedback & keyboard navigation
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeRowIndex, setActiveRowIndex] = useState<number>(-1);

  // Column widths
  const [colWidths, setColWidths] = useState<Record<string, number>>(() => {
    const defaults = Object.fromEntries(DEFAULT_COLUMNS.map((c) => [c.id, c.defaultWidth]));
    try {
      const raw = localStorage.getItem('bp.colWidths');
      if (!raw) return defaults;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        const merged: Record<string, number> = { ...defaults };
        for (const col of DEFAULT_COLUMNS) {
          if (typeof parsed[col.id] === 'number' && parsed[col.id] >= MIN_COL_WIDTH) {
            merged[col.id] = parsed[col.id];
          }
        }
        return merged;
      }
    } catch {}
    return defaults;
  });

  const resultsWrapRef = useRef<HTMLDivElement>(null);
  const detailPanelRef = useRef<HTMLDivElement | null>(null);
  const tableSearchInputRef = useRef<HTMLInputElement | null>(null);
  const [visibleWrapWidth, setVisibleWrapWidth] = useState<number>(0);

  // Save changes to localStorage
  useEffect(() => writeStorage('bp.searchParams', searchParams), [searchParams]);
  useEffect(() => writeStorage('bp.density', density), [density]);
  useEffect(() => writeStorage('bp.filter.search', tableSearch), [tableSearch]);
  useEffect(() => writeStorage('bp.filter.provider', providerFilter), [providerFilter]);
  useEffect(() => writeStorage('bp.filter.remote', remoteFilter), [remoteFilter]);
  useEffect(() => writeStorage('bp.filter.employment', employmentFilter), [employmentFilter]);
  useEffect(() => writeStorage('bp.filter.salaryOnly', onlySalaryListed), [onlySalaryListed]);
  useEffect(() => writeStorage('bp.filter.nigerianOnly', onlyNigerianBoards), [onlyNigerianBoards]);
  useEffect(() => writeStorage('bp.sort.field', sortField), [sortField]);
  useEffect(() => writeStorage('bp.sort.asc', sortAsc), [sortAsc]);
  useEffect(() => writeStorage('bp.page.current', currentPage), [currentPage]);
  useEffect(() => writeStorage('bp.page.size', pageSize), [pageSize]);
  useEffect(() => writeStorage('bp.colWidths', colWidths), [colWidths]);

  // Smooth scroll helper
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (screen === 'delivery') {
      const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      resultsWrapRef.current?.scrollIntoView({
        behavior: prefersReduced ? 'auto' : 'smooth',
        block: 'start',
      });
    }
  }, [currentPage]);

  // Persist results (guarded by ~3MB cap)
  const persistResults = (
    results: JobListing[],
    currentMetrics: DoneMetrics | null,
    summary: string
  ) => {
    try {
      const timestamp = Date.now();
      const payload = JSON.stringify({
        rawResults: results,
        metrics: currentMetrics,
        extractionSummary: summary,
        savedAt: timestamp,
      });
      if (payload.length <= 3 * 1024 * 1024) {
        localStorage.setItem('bp.savedResults', payload);
        setSavedTimestamp(timestamp);
      } else {
        localStorage.removeItem('bp.savedResults');
        setSavedTimestamp(null);
      }
    } catch {
      // ignore QuotaExceededError
    }
  };

  const handleClearSavedResults = () => {
    try {
      localStorage.removeItem('bp.savedResults');
    } catch {}
    setSavedTimestamp(null);
    setRawResults([]);
    setMetrics(null);
    setExpandedJobId(null);
    setScreen('form');
  };

  // ResizeObserver for table width
  useEffect(() => {
    const el = resultsWrapRef.current;
    if (!el) return;
    const updateWidth = () => setVisibleWrapWidth(el.clientWidth);
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, [screen]);

  // Scroll detail panel into view when opened (respecting prefers-reduced-motion)
  useEffect(() => {
    if (expandedJobId && detailPanelRef.current) {
      const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      detailPanelRef.current.scrollIntoView({
        behavior: prefersReduced ? 'auto' : 'smooth',
        block: 'nearest',
      });
    }
  }, [expandedJobId]);

  const totalTableWidth = useMemo(
    () => Object.values(colWidths).reduce((a, b) => a + b, 0),
    [colWidths]
  );

  const extraRoleWidth = useMemo(
    () => Math.max(0, (visibleWrapWidth || 0) - totalTableWidth),
    [visibleWrapWidth, totalTableWidth]
  );

  const normalizedList = useMemo(() => {
    return rawResults.map(normalizeJob);
  }, [rawResults]);

  const availableProviders = useMemo(() => {
    const set = new Set(normalizedList.map((job) => job.provider).filter(Boolean));
    return Array.from(set).sort();
  }, [normalizedList]);

  const availableEmploymentTypes = useMemo(() => {
    const set = new Set(
      normalizedList
        .map((job) => job.displayEmployment)
        .filter((val) => val && val !== 'Unknown' && val !== 'Not specified')
    );
    return Array.from(set).sort();
  }, [normalizedList]);

  // Client-side filtering
  const filteredResults = useMemo(() => {
    const searchLower = tableSearch.trim().toLowerCase();
    const nigerianSources = new Set(['jobberman', 'myjobmag', 'hotnigerianjobs', 'ngcareers']);

    return normalizedList.filter((job) => {
      const searchable = [
        job.displayTitle,
        job.company,
        job.displayLocation,
        job.displaySalary,
        job.displayEmployment,
        job.displayLocationType,
        job.displayPostedDate,
        job.provider,
      ]
        .join(' ')
        .toLowerCase();

      const matchesSearch = !searchLower || searchable.includes(searchLower);
      const matchesProvider = !providerFilter || job.provider === providerFilter;

      let matchesRemote = true;
      if (remoteFilter === 'remote') {
        matchesRemote = job.work_model === 'remote';
      } else if (remoteFilter === 'hybrid') {
        matchesRemote = job.work_model === 'hybrid';
      } else if (remoteFilter === 'in_person') {
        matchesRemote = job.work_model === 'in_person';
      } else if (remoteFilter === 'onsite') {
        matchesRemote = job.work_model !== 'remote';
      } else if (remoteFilter === 'not_specified') {
        matchesRemote = !job.work_model;
      }

      const matchesEmployment = !employmentFilter || job.displayEmployment === employmentFilter;
      const matchesSalaryOnly = !onlySalaryListed || job.displaySalary !== 'Not listed';
      const matchesNigerianOnly =
        !onlyNigerianBoards || nigerianSources.has(job.provider.toLowerCase());

      return (
        matchesSearch &&
        matchesProvider &&
        matchesRemote &&
        matchesEmployment &&
        matchesSalaryOnly &&
        matchesNigerianOnly
      );
    });
  }, [
    normalizedList,
    tableSearch,
    providerFilter,
    remoteFilter,
    employmentFilter,
    onlySalaryListed,
    onlyNigerianBoards,
  ]);

  // Sorting logic
  const sortedResults = useMemo(() => {
    if (!sortField) return filteredResults;
    const sorted = [...filteredResults].sort((a, b) => {
      let valA = '';
      let valB = '';
      if (sortField === 'title') {
        valA = a.displayTitle.toLowerCase();
        valB = b.displayTitle.toLowerCase();
      } else if (sortField === 'company') {
        valA = a.company.toLowerCase();
        valB = b.company.toLowerCase();
      } else if (sortField === 'salary') {
        valA = a.displaySalary === 'Not listed' ? '' : a.displaySalary.toLowerCase();
        valB = b.displaySalary === 'Not listed' ? '' : b.displaySalary.toLowerCase();
      } else if (sortField === 'date') {
        valA = a.posted_at || '';
        valB = b.posted_at || '';
      }
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [filteredResults, sortField, sortAsc]);

  // Paginated results
  const totalPages = Math.max(1, Math.ceil(sortedResults.length / pageSize));
  const paginatedResults = useMemo(() => {
    if (pageSize >= sortedResults.length) return sortedResults;
    const start = (currentPage - 1) * pageSize;
    return sortedResults.slice(start, start + pageSize);
  }, [sortedResults, currentPage, pageSize]);

  // Keyboard navigation: j/k active row, Enter toggle, Esc close, / focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName || '').toUpperCase();
      const isInput =
        activeTag === 'INPUT' ||
        activeTag === 'TEXTAREA' ||
        activeTag === 'SELECT' ||
        (document.activeElement as HTMLElement)?.isContentEditable;

      if (e.key === 'Escape') {
        setExpandedJobId(null);
        return;
      }

      if (isInput) return;

      if (e.key === '/') {
        e.preventDefault();
        tableSearchInputRef.current?.focus();
        return;
      }

      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveRowIndex((prev) => Math.min(paginatedResults.length - 1, Math.max(0, prev + 1)));
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveRowIndex((prev) => Math.max(0, prev - 1));
      } else if (e.key === 'Enter') {
        if (activeRowIndex >= 0 && activeRowIndex < paginatedResults.length) {
          e.preventDefault();
          const targetJob = paginatedResults[activeRowIndex];
          setExpandedJobId((prev) => (prev === targetJob.id ? null : targetJob.id));
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [paginatedResults, activeRowIndex]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const handleResetColumns = () => {
    const defaults = Object.fromEntries(DEFAULT_COLUMNS.map((c) => [c.id, c.defaultWidth]));
    setColWidths(defaults);
  };

  const handleResetSingleColumn = (colId: string) => {
    const def = DEFAULT_COLUMNS.find((c) => c.id === colId);
    if (def) {
      setColWidths((prev) => ({ ...prev, [colId]: def.defaultWidth }));
    }
  };

  const handleResizePointerDown = (colId: string, e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);

    const startX = e.clientX;
    const startWidth = colWidths[colId] || DEFAULT_COLUMNS.find((c) => c.id === colId)?.defaultWidth || 100;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX;
      const newWidth = Math.max(MIN_COL_WIDTH, startWidth + delta);
      setColWidths((prev) => ({ ...prev, [colId]: newWidth }));
    };

    const onPointerUp = (upEvent: PointerEvent) => {
      try {
        target.releasePointerCapture(upEvent.pointerId);
      } catch {}
      target.removeEventListener('pointermove', onPointerMove);
      target.removeEventListener('pointerup', onPointerUp);
      target.removeEventListener('pointercancel', onPointerUp);
    };

    target.addEventListener('pointermove', onPointerMove);
    target.addEventListener('pointerup', onPointerUp);
    target.addEventListener('pointercancel', onPointerUp);
  };

  const copyApplyUrl = (url: string, id: string) => {
    navigator.clipboard?.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const executeSearch = async (customParams?: SearchParams) => {
    const paramsToUse = customParams || searchParams;
    setRawResults([]);
    setMetrics(null);
    setExpandedJobId(null);
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setOnlyNigerianBoards(false);
    setSortField(null);
    setCurrentPage(1);
    setActiveRowIndex(-1);
    setScreen('processing');
    setLiveConsoleMessage('Connecting to the search pipeline...');
    setActiveSources([]);
    setIsRateLimited(false);

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
      let accumulatedCount = 0;
      let finalResults: JobListing[] = [];
      let finalMetrics: DoneMetrics | null = null;
      let finalSummary = '';

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
              finalResults = [...finalResults, ...batch];
              setRawResults(finalResults);
              accumulatedCount += batch.length;

              const sourcesInBatch = Array.from(new Set(batch.map((j) => j.provider)));
              setActiveSources((prev) => {
                const combined = Array.from(new Set([...prev, ...sourcesInBatch]));
                setLiveConsoleMessage(
                  `${accumulatedCount} results so far · ${combined.length} of 18 platforms`
                );
                return combined;
              });
            } else if (eventName === 'done') {
              finalMetrics = payload as DoneMetrics;
              setMetrics(finalMetrics);
              finalSummary = finalMetrics.cached
                ? 'Loaded from the recent search cache.'
                : 'Fresh results compiled from the selected ATS platforms.';
              setExtractionSummary(finalSummary);
              persistResults(finalResults, finalMetrics, finalSummary);
              setScreen('delivery');
            } else if (eventName === 'error') {
              throw new Error(payload.message || 'Search execution failed');
            }

            eventName = '';
            eventData = '';
          }
        }
      }

      persistResults(finalResults, finalMetrics, finalSummary);
      setScreen('delivery');

      // Smooth scroll to results
      setTimeout(() => {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        resultsWrapRef.current?.scrollIntoView({
          behavior: prefersReduced ? 'auto' : 'smooth',
          block: 'start',
        });
      }, 50);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setScreen('form');
      } else {
        const message = err instanceof Error ? err.message : String(err);
        setErrorMessage(message);
        setScreen('error');
      }
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch();
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setScreen('form');
  };

  const handleReset = () => {
    handleCancel();
    setRawResults([]);
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setOnlyNigerianBoards(false);
    setExpandedJobId(null);
    setCurrentPage(1);
    setActiveRowIndex(-1);
    setScreen('form');
  };

  const handleClearFilters = () => {
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setOnlyNigerianBoards(false);
    setCurrentPage(1);
  };

  return (
    <>
      <header className="topbar">
        <a className="brand" href="/" aria-label="Bottom Pot home">
          <span className="brand-mark" aria-hidden="true">BP</span>
          <span>Bottom Pot <small>ATS SEARCH</small></span>
        </a>
        <div className="status-chip">
          <span className="status-dot"></span> Live search infrastructure
        </div>
      </header>

      <main className="workspace">
        <section className="intro">
          <p className="eyebrow">Direct from the source</p>
          <h1>Find the signal<br /><em>behind the noise.</em></h1>
          <p className="intro-copy">
            Search public applicant tracking systems and turn fresh job postings into a clean, useful shortlist.
          </p>
        </section>

        <section className="panel" aria-labelledby="search-heading">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Search parameters</p>
              <h2 id="search-heading">Build a targeted query</h2>
            </div>
            <span className="mono">GET /search</span>
          </div>

          {screen === 'form' && (
            <SearchForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSubmit={handleSubmit}
            />
          )}

          {screen === 'processing' && (
            <div id="processingScreen" className="state-screen" aria-live="polite">
              <div className="spinner" aria-hidden="true"></div>
              <div>
                <p className="state-title">Compiling live results...</p>
                <p id="liveConsole" className="console-line">
                  {liveConsoleMessage}
                </p>
                {activeSources.length > 0 && (
                  <div className="active-sources-list">
                    {activeSources.map((s) => (
                      <span key={s} className="badge badge-source">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                id="cancelBtn"
                className="btn btn-text"
                type="button"
                onClick={handleCancel}
              >
                Cancel search
              </button>

              {/* Streaming progress line & skeleton table */}
              <div className="streaming-wrap">
                <div className="streaming-progress-bar" role="progressbar" aria-label="Loading results">
                  <div className="streaming-progress-indicator"></div>
                </div>

                <div className="results-wrap" style={{ width: '100%' }}>
                  <table style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        {DEFAULT_COLUMNS.map((col) => (
                          <th key={col.id}>{col.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[1, 2, 3, 4, 5, 6].map((i) => (
                        <tr key={i} className="skeleton-row">
                          <td><div className="skeleton-line" style={{ width: '85%' }}></div></td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <div className="skeleton-avatar"></div>
                              <div className="skeleton-line" style={{ width: '60%' }}></div>
                            </div>
                          </td>
                          <td><div className="skeleton-line" style={{ width: '70%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '50%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '65%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '55%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '50%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '45%' }}></div></td>
                          <td><div className="skeleton-line" style={{ width: '60%' }}></div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {screen === 'delivery' && (
            <div id="deliveryScreen" aria-live="polite">
              <StatusBanner
                savedTimestamp={savedTimestamp}
                metrics={metrics}
                onRunAgain={() => executeSearch()}
                onClearSaved={handleClearSavedResults}
              />

              <div className="search-header-row">
                <div>
                  <p className="eyebrow">Search complete</p>
                  <h2 id="resultTitle">Results are ready</h2>
                  <p id="extractionSummary" className="muted">
                    {extractionSummary}
                  </p>
                </div>
                <button
                  id="resetBtn"
                  className="btn btn-text"
                  type="button"
                  onClick={handleReset}
                >
                  New search
                </button>
              </div>

              <SearchInfo
                metrics={metrics}
                totalRawResults={rawResults.length}
              />

              <FilterBar
                tableSearchInputRef={tableSearchInputRef}
                tableSearch={tableSearch}
                setTableSearch={setTableSearch}
                providerFilter={providerFilter}
                setProviderFilter={setProviderFilter}
                availableProviders={availableProviders}
                remoteFilter={remoteFilter}
                setRemoteFilter={setRemoteFilter}
                employmentFilter={employmentFilter}
                setEmploymentFilter={setEmploymentFilter}
                availableEmploymentTypes={availableEmploymentTypes}
                onlySalaryListed={onlySalaryListed}
                setOnlySalaryListed={setOnlySalaryListed}
                onlyNigerianBoards={onlyNigerianBoards}
                setOnlyNigerianBoards={setOnlyNigerianBoards}
                onClearFilters={handleClearFilters}
                setCurrentPage={setCurrentPage}
              />

              <Toolbar
                totalRawCount={rawResults.length}
                filteredCount={filteredResults.length}
                currentPage={currentPage}
                totalPages={totalPages}
                density={density}
                onSetDensity={setDensity}
                onResetColumns={handleResetColumns}
                onDownloadCsv={() => downloadCsv(sortedResults, searchParams.keywords)}
                onDownloadJson={() => downloadJson(sortedResults, searchParams.keywords)}
              />

              <ResultsTable
                density={density}
                resultsWrapRef={resultsWrapRef}
                detailPanelRef={detailPanelRef}
                totalTableWidth={totalTableWidth}
                columns={DEFAULT_COLUMNS}
                colWidths={colWidths}
                extraRoleWidth={extraRoleWidth}
                sortField={sortField}
                sortAsc={sortAsc}
                onSort={handleSort}
                onResizePointerDown={handleResizePointerDown}
                onResetSingleColumn={handleResetSingleColumn}
                paginatedResults={paginatedResults}
                expandedJobId={expandedJobId}
                onToggleExpand={(id) => setExpandedJobId((prev) => (prev === id ? null : id))}
                activeRowIndex={activeRowIndex}
                onSetActiveRowIndex={setActiveRowIndex}
                copiedId={copiedId}
                onCopyApplyUrl={copyApplyUrl}
                visibleWrapWidth={visibleWrapWidth}
                filteredResultsCount={filteredResults.length}
                rawResultsCount={rawResults.length}
                onClearFilters={handleClearFilters}
                totalPages={totalPages}
                currentPage={currentPage}
                onSetCurrentPage={(updater) => setCurrentPage(updater)}
                pageSize={pageSize}
                onSetPageSize={setPageSize}
                totalSortedCount={sortedResults.length}
              />
            </div>
          )}

          {screen === 'error' && (
            <div id="errorScreen" className="error-screen" role="alert">
              <strong>{isRateLimited ? 'Rate limit exceeded (HTTP 429)' : 'Search could not be completed.'}</strong>
              <p id="errorMessage">{errorMessage}</p>
              <div className="error-actions">
                <button
                  id="errorRetryBtn"
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => executeSearch()}
                >
                  Retry search
                </button>
                <button
                  id="errorResetBtn"
                  className="btn btn-text"
                  type="button"
                  onClick={handleReset}
                >
                  Return to search
                </button>
              </div>
            </div>
          )}
        </section>
      </main>

      <footer>
        <span>Bottom Pot</span> &middot; Direct ATS discovery, without the feed.
      </footer>
    </>
  );
}

export default App;
