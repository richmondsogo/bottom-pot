import React, { useState, useMemo, useRef, useEffect } from 'react';
import type { JobListing, NormalizedJob, DoneMetrics, SearchParams, SortField } from './types';
import { normalizeJob } from './lib/normalize';
import { readStorage, writeStorage } from './lib/storage';
import { markVisited } from './lib/visited';
import { filterJobs } from './lib/filter';
import { sortJobs } from './lib/sort';
import { isMockModeActive, getMockModeType, generateMockJobs, getMockMetrics } from './lib/mock';

import { Header } from './components/Header';
import { SearchForm } from './components/SearchForm';
import { ALL_PLATFORMS } from './lib/constants';
import { SearchSummaryBar } from './components/SearchSummaryBar';
import { StatusStrip } from './components/StatusStrip';
import { Toolbar } from './components/Toolbar';
import { ResultsTable } from './components/ResultsTable';
import { ResultsCards } from './components/ResultsCards';
import { DetailSheet } from './components/DetailSheet';
import { ShortcutsModal } from './components/ShortcutsModal';
import { LoadingState, NoResultsState, ErrorState } from './components/States';

export function App() {
  // Persistence: search parameters
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

  // Platform selection state
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(() =>
    readStorage<string[]>('bp.selectedPlatforms', ALL_PLATFORMS.map((p) => p.id))
  );

  // Filter persistence
  const [tableSearch, setTableSearch] = useState(() => readStorage<string>('bp.filter.search', ''));
  const [providerFilter, setProviderFilter] = useState(() => readStorage<string>('bp.filter.provider', ''));
  const [remoteFilter, setRemoteFilter] = useState(() => readStorage<string>('bp.filter.remote', ''));
  const [employmentFilter, setEmploymentFilter] = useState(() => readStorage<string>('bp.filter.employment', ''));
  const [onlySalaryListed, setOnlySalaryListed] = useState(() =>
    readStorage<boolean>('bp.filter.salaryOnly', false)
  );

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
    return savedResultsData?.rawResults || [];
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
    return savedResultsData && savedResultsData.rawResults.length > 0 ? 'delivery' : 'form';
  });

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
    try {
      localStorage.removeItem('bp.savedResults');
    } catch {}
    setSavedTimestamp(null);
    setRawResults([]);
    setMetrics(null);
    setSelectedJob(null);
    setScreen('form');
  };

  // Normalization
  const normalizedList = useMemo(() => {
    return rawResults.map((job) => normalizeJob(job));
  }, [rawResults]);

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
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [screen, sortedResults, activeRowIndex, selectedJob, shortcutsOpen]);

  // Search execution
  const executeSearch = async (customParams?: SearchParams) => {
    const paramsToUse = customParams || searchParams;
    setRawResults([]);
    setMetrics(null);
    setSelectedJob(null);
    setTableSearch('');
    setProviderFilter('');
    setRemoteFilter('');
    setEmploymentFilter('');
    setOnlySalaryListed(false);
    setSortField(null);
    setActiveRowIndex(-1);
    setIsRateLimited(false);
    setScreen('loading');
    setLoadingMessage('Initializing connection to ATS search pipeline...');

    // If Mock Mode is active, simulate without network or live Serper credits
    if (isMockModeActive()) {
      const mode = getMockModeType();
      const delay = mode === 'slow' ? 3000 : 700;

      setTimeout(() => {
        if (mode === 'error') {
          setErrorMessage('Simulated Search Failure: Upstream ATS service unreachable (HTTP 502).');
          setScreen('error');
          return;
        }
        if (mode === 'empty') {
          setRawResults([]);
          setMetrics(getMockMetrics(0));
          setScreen('delivery');
          return;
        }

        const mockJobs = generateMockJobs();
        setRawResults(mockJobs);
        const mockMetrics = getMockMetrics(mockJobs.length);
        setMetrics(mockMetrics);
        persistResults(mockJobs, mockMetrics);
        setScreen('delivery');
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
              setScreen('delivery');
            } else if (eventName === 'error') {
              throw new Error(payload.message || 'Search execution failed');
            }

            eventName = '';
            eventData = '';
          }
        }
      }

      persistResults(accumulatedResults, finalMetrics);
      setScreen('delivery');
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

  const handleCancelSearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setScreen('form');
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
  };

  const handleWidenDateRange = () => {
    const updated = { ...searchParams, postAge: '30' };
    setSearchParams(updated);
    executeSearch(updated);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <Header
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onResetSearch={() => setScreen('form')}
      />

      {/* Main Content Area */}
      <main style={{ flex: 1, paddingBottom: 'var(--space-16)' }}>
        {screen === 'form' && (
          <div className="content-max-width" style={{ paddingTop: 'var(--space-8)' }}>
            <SearchForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSubmit={handleSubmit}
              selectedPlatforms={selectedPlatforms}
              setSelectedPlatforms={setSelectedPlatforms}
            />
          </div>
        )}

        {screen === 'loading' && (
          <div className="content-max-width" style={{ paddingTop: 'var(--space-8)' }}>
            <LoadingState onCancel={handleCancelSearch} statusMessage={loadingMessage} />
          </div>
        )}

        {screen === 'error' && (
          <div className="content-max-width" style={{ paddingTop: 'var(--space-8)' }}>
            <ErrorState
              message={errorMessage}
              isRateLimited={isRateLimited}
              onRetry={() => executeSearch()}
              onEditSearch={() => setScreen('form')}
            />
          </div>
        )}

        {screen === 'delivery' && (
          <div>
            {/* Sticky Search Summary Bar: Collapses hero */}
            <SearchSummaryBar
              searchParams={searchParams}
              onEditSearch={() => setScreen('form')}
              onNewSearch={() => {
                setSearchParams({
                  keywords: '',
                  location: '',
                  workModel: 'any',
                  postAge: '7',
                  includeNigerian: true,
                  deepScrape: false,
                });
                setScreen('form');
              }}
              platformCount={metrics?.providers_searched?.length || selectedPlatforms.length}
            />

            <div className="content-max-width" ref={resultsContainerRef} style={{ paddingTop: 'var(--space-4)' }}>
              {/* Single Quiet Status Strip */}
              <StatusStrip
                totalResults={rawResults.length}
                metrics={metrics}
                savedTimestamp={savedTimestamp}
                onRunAgain={() => executeSearch()}
                onClearSaved={handleClearSavedResults}
              />

              {rawResults.length === 0 ? (
                <NoResultsState
                  onWidenDateRange={handleWidenDateRange}
                  onClearFilters={handleClearFilters}
                  onNewSearch={() => setScreen('form')}
                />
              ) : (
                <>
                  {/* Sticky Toolbar with / filter, selects, count */}
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
                    availableProviders={availableProviders}
                    availableEmploymentTypes={availableEmploymentTypes}
                    totalResults={rawResults.length}
                    filteredCount={sortedResults.length}
                    onClearFilters={handleClearFilters}
                    searchInputRef={searchInputRef}
                  />

                  {/* Results: Desktop Table & Mobile Cards */}
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    {sortedResults.length === 0 ? (
                      <div
                        style={{
                          background: 'var(--surface)',
                          border: '1px solid var(--border)',
                          padding: 'var(--space-8) var(--space-4)',
                          textAlign: 'center',
                          color: 'var(--ink-muted)',
                        }}
                      >
                        <p style={{ fontWeight: 600, fontSize: 'var(--text-body)', marginBottom: 'var(--space-2)' }}>
                          No postings match the active filters
                        </p>
                        <p style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                          Try clearing search keywords or platform filters.
                        </p>
                        <button type="button" className="btn btn-sm" onClick={handleClearFilters}>
                          Clear filters
                        </button>
                      </div>
                    ) : (
                      <>
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
                        />

                        <ResultsCards
                          jobs={sortedResults}
                          selectedJobId={selectedJob?.id || null}
                          onSelectJob={(job) => {
                            setSelectedJob(job);
                            handleMarkVisited(job.apply_url || job.id);
                          }}
                        />
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Detail Sheet Overlay */}
      <DetailSheet
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onMarkVisited={handleMarkVisited}
      />

      {/* Keyboard Shortcuts Modal */}
      <ShortcutsModal
        isOpen={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />
    </div>
  );
}

export default App;
