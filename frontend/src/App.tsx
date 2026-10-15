import React, { useState, useMemo, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { JobListing, DoneMetrics, SearchParams } from './types';
import { normalizeJob } from './lib/normalize';
import { downloadCsv, downloadJson } from './lib/export';

const ROLE_SUGGESTIONS = [
  'Backend Engineer',
  'Full-Stack Developer',
  'Python / FastAPI',
  'Frontend React',
  'DevOps / Cloud',
  'Product Designer',
];

const LOCATION_SUGGESTIONS = ['Nigeria', 'Lagos', 'Remote', 'London'];

type SortField = 'title' | 'company' | 'salary' | 'date' | null;

interface ColumnDef {
  id: string;
  label: string;
  defaultWidth: number;
  sortField?: SortField;
}

const DEFAULT_COLUMNS: ColumnDef[] = [
  { id: 'role', label: 'Role', defaultWidth: 300, sortField: 'title' },
  { id: 'company', label: 'Company', defaultWidth: 170, sortField: 'company' },
  { id: 'location', label: 'Location', defaultWidth: 190 },
  { id: 'salary', label: 'Salary', defaultWidth: 110, sortField: 'salary' },
  { id: 'job_type', label: 'Job type', defaultWidth: 110 },
  { id: 'work_model', label: 'Work model', defaultWidth: 120 },
  { id: 'posted', label: 'Posted date', defaultWidth: 110, sortField: 'date' },
  { id: 'source', label: 'Source', defaultWidth: 110 },
  { id: 'actions', label: '', defaultWidth: 150 },
];

const STORAGE_KEY = 'bp.colWidths';
const MIN_COL_WIDTH = 70;

function loadInitialColWidths(): Record<string, number> {
  const defaults = Object.fromEntries(DEFAULT_COLUMNS.map((c) => [c.id, c.defaultWidth]));
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
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
  } catch {
    // ignore
  }
  return defaults;
}

export function App() {
  const [screen, setScreen] = useState<'form' | 'processing' | 'delivery' | 'error'>('form');

  const [searchParams, setSearchParams] = useState<SearchParams>({
    keywords: '',
    location: '',
    workModel: 'any',
    postAge: '7',
    includeNigerian: true,
    deepScrape: false,
  });

  const [rawResults, setRawResults] = useState<JobListing[]>([]);
  const [liveConsoleMessage, setLiveConsoleMessage] = useState('Connecting to the search pipeline...');
  const [activeSources, setActiveSources] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<DoneMetrics | null>(null);
  const [extractionSummary, setExtractionSummary] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const abortControllerRef = useRef<AbortController | null>(null);

  // Table filters & controls
  const [tableSearch, setTableSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState('');
  const [remoteFilter, setRemoteFilter] = useState('');
  const [employmentFilter, setEmploymentFilter] = useState('');
  const [onlySalaryListed, setOnlySalaryListed] = useState(false);
  const [onlyNigerianBoards, setOnlyNigerianBoards] = useState(false);

  // Sorting
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortAsc, setSortAsc] = useState(true);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // Details & clipboard feedback
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Column widths & resizing
  const [colWidths, setColWidths] = useState<Record<string, number>>(loadInitialColWidths);
  const resultsWrapRef = useRef<HTMLDivElement>(null);
  const [visibleWrapWidth, setVisibleWrapWidth] = useState<number>(0);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(colWidths));
    } catch {
      // ignore
    }
  }, [colWidths]);

  useEffect(() => {
    const el = resultsWrapRef.current;
    if (!el) return;
    const updateWidth = () => {
      setVisibleWrapWidth(el.clientWidth);
    };
    updateWidth();
    const observer = new ResizeObserver(() => {
      updateWidth();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [screen]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setExpandedJobId(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

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
    const nigerianSources = new Set(['jobberman', 'myjobmag', 'hotnigerianJobs', 'ngcareers']);

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
      const matchesRemote =
        !remoteFilter ||
        (remoteFilter === 'remote'
          ? job.work_model === 'remote'
          : job.work_model !== 'remote');
      const matchesEmployment = !employmentFilter || job.displayEmployment === employmentFilter;
      const matchesSalaryOnly = !onlySalaryListed || job.displaySalary !== 'Not listed';
      const matchesNigerianOnly = !onlyNigerianBoards || nigerianSources.has(job.provider.toLowerCase());

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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const copyApplyUrl = (url: string, id: string) => {
    navigator.clipboard?.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
    setScreen('processing');
    setLiveConsoleMessage('Connecting to the search pipeline...');
    setActiveSources([]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const params = new URLSearchParams({
      q: searchParams.keywords.trim(),
      days_back: searchParams.postAge,
      include_nigerian: String(searchParams.includeNigerian),
    });

    if (searchParams.location.trim()) {
      params.set('location', searchParams.location.trim());
    }
    if (searchParams.workModel !== 'any') {
      params.set('remote', String(searchParams.workModel === 'remote'));
    }
    if (searchParams.deepScrape) {
      params.set('deep_scrape', 'true');
    }

    try {
      const response = await fetch(`/search?${params.toString()}`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      });

      if (!response.ok || !response.body) {
        throw new Error(`The search service returned HTTP ${response.status}.`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventName = '';
      let eventData = '';
      let accumulatedCount = 0;

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
              setRawResults((prev) => [...prev, ...batch]);
              accumulatedCount += batch.length;
              
              const sourcesInBatch = Array.from(new Set(batch.map((j) => j.provider)));
              setActiveSources((prev) => Array.from(new Set([...prev, ...sourcesInBatch])));

              setLiveConsoleMessage(
                `Received ${accumulatedCount} result${accumulatedCount === 1 ? '' : 's'}...`
              );
            } else if (eventName === 'done') {
              const donePayload = payload as DoneMetrics;
              setMetrics(donePayload);
              setExtractionSummary(
                donePayload.cached
                  ? 'Loaded from the recent search cache.'
                  : 'Fresh results compiled from the selected ATS platforms.'
              );
              setScreen('delivery');
            } else if (eventName === 'error') {
              throw new Error(payload.message || 'Search execution failed');
            }

            eventName = '';
            eventData = '';
          }
        }
      }

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
            <form id="queryForm" onSubmit={handleSubmit}>
              <label className="field field-wide">
                <span>Role or keyword <b>*</b></span>
                <input
                  id="keywords"
                  name="keywords"
                  type="text"
                  required
                  minLength={2}
                  maxLength={100}
                  placeholder="e.g. Backend Software Engineer"
                  autoComplete="off"
                  value={searchParams.keywords}
                  onChange={(e) => setSearchParams({ ...searchParams, keywords: e.target.value })}
                />
              </label>

              {/* 1-Click Role Suggestions */}
              <div className="chips-row">
                <span className="chips-label">Quick search:</span>
                {ROLE_SUGGESTIONS.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className={`chip-btn ${searchParams.keywords === role ? 'active' : ''}`}
                    onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  >
                    {role}
                  </button>
                ))}
              </div>

              <div className="field-grid">
                <label className="field">
                  <span>Location</span>
                  <input
                    id="location"
                    name="location"
                    type="text"
                    maxLength={100}
                    placeholder="Anywhere"
                    value={searchParams.location}
                    onChange={(e) => setSearchParams({ ...searchParams, location: e.target.value })}
                  />
                </label>

                <label className="field">
                  <span>Work model</span>
                  <select
                    id="workModel"
                    name="workModel"
                    value={searchParams.workModel}
                    onChange={(e) => setSearchParams({ ...searchParams, workModel: e.target.value })}
                  >
                    <option value="any">Any model</option>
                    <option value="remote">Remote only</option>
                    <option value="onsite">Exclude remote</option>
                  </select>
                </label>

                <label className="field">
                  <span>Posted within</span>
                  <select
                    id="postAge"
                    name="postAge"
                    value={searchParams.postAge}
                    onChange={(e) => setSearchParams({ ...searchParams, postAge: e.target.value })}
                  >
                    <option value="3">3 days</option>
                    <option value="7">7 days</option>
                    <option value="14">14 days</option>
                    <option value="30">30 days</option>
                    <option value="90">90 days</option>
                  </select>
                </label>
              </div>

              {/* Location Suggestions */}
              <div className="chips-row">
                <span className="chips-label">Popular:</span>
                {LOCATION_SUGGESTIONS.map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    className={`chip-btn ${searchParams.location === loc ? 'active' : ''}`}
                    onClick={() => setSearchParams({ ...searchParams, location: loc })}
                  >
                    {loc}
                  </button>
                ))}
              </div>

              <label className="check-field">
                <input
                  id="includeNigerian"
                  type="checkbox"
                  checked={searchParams.includeNigerian}
                  onChange={(e) =>
                    setSearchParams({ ...searchParams, includeNigerian: e.target.checked })
                  }
                />
                <span>Include Nigerian job boards</span>
              </label>

              <label className="check-field">
                <input
                  id="deepScrape"
                  type="checkbox"
                  checked={searchParams.deepScrape}
                  onChange={(e) =>
                    setSearchParams({ ...searchParams, deepScrape: e.target.checked })
                  }
                />
                <span>Deep scrape matched job pages</span>
              </label>

              <button className="primary-button" type="submit">
                <span>Search ATS platforms</span>
                <span aria-hidden="true">&#8599;</span>
              </button>
            </form>
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
                  <div style={{ display: 'flex', gap: '6px', justifyContent: 'center', marginTop: '10px' }}>
                    {activeSources.map((s) => (
                      <span key={s} className="badge-source">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                id="cancelBtn"
                className="text-button"
                type="button"
                onClick={handleCancel}
              >
                Cancel search
              </button>
            </div>
          )}

          {screen === 'delivery' && (
            <div id="deliveryScreen" aria-live="polite">
              <div className="result-toolbar">
                <div>
                  <p className="eyebrow">Search complete</p>
                  <h2 id="resultTitle">Results are ready</h2>
                  <p id="extractionSummary" className="muted">
                    {extractionSummary}
                  </p>
                </div>
                <div className="toolbar-actions">
                  <button
                    id="downloadBtn"
                    className="secondary-button"
                    type="button"
                    onClick={() => downloadCsv(sortedResults, searchParams.keywords)}
                  >
                    Download CSV
                  </button>
                  <button
                    id="downloadJsonBtn"
                    className="secondary-button secondary-button-muted"
                    type="button"
                    onClick={() => downloadJson(sortedResults, searchParams.keywords)}
                  >
                    Download JSON
                  </button>
                  <button
                    id="resetBtn"
                    className="text-button"
                    type="button"
                    onClick={handleReset}
                  >
                    New search
                  </button>
                </div>
              </div>

              <div id="metrics" className="metrics">
                <div className="metric">
                  <strong>{metrics?.total ?? rawResults.length}</strong>
                  <span>Results</span>
                </div>
                <div className="metric">
                  <strong>{metrics ? `${metrics.search_time_ms} ms` : '-'}</strong>
                  <span>Search time</span>
                </div>
                <div className="metric">
                  <strong>{metrics?.providers_searched.length ?? 0}</strong>
                  <span>Providers</span>
                </div>
                <div className="metric">
                  <strong>{metrics?.serper_queries_used ?? 0}</strong>
                  <span>Serper queries</span>
                </div>
              </div>

              {/* Standard Filter Controls */}
              <div className="table-controls" aria-label="Filter controls">
                <label className="filter-field filter-search">
                  <span>Filter results</span>
                  <input
                    id="tableSearch"
                    type="search"
                    placeholder="Role, company, location..."
                    autoComplete="off"
                    value={tableSearch}
                    onChange={(e) => {
                      setTableSearch(e.target.value);
                      setCurrentPage(1);
                    }}
                  />
                </label>
                <label className="filter-field">
                  <span>Provider</span>
                  <select
                    id="providerFilter"
                    value={providerFilter}
                    onChange={(e) => {
                      setProviderFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                  >
                    <option value="">All providers</option>
                    {availableProviders.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="filter-field">
                  <span>Work model</span>
                  <select
                    id="remoteFilter"
                    value={remoteFilter}
                    onChange={(e) => {
                      setRemoteFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                  >
                    <option value="">Any model</option>
                    <option value="remote">Remote</option>
                    <option value="onsite">On-site / unspecified</option>
                  </select>
                </label>
                <label className="filter-field">
                  <span>Job type</span>
                  <select
                    id="employmentFilter"
                    value={employmentFilter}
                    onChange={(e) => {
                      setEmploymentFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                  >
                    <option value="">All types</option>
                    {availableEmploymentTypes.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  id="clearFiltersBtn"
                  className="text-button"
                  type="button"
                  onClick={handleClearFilters}
                >
                  Clear filters
                </button>
                <button
                  id="resetColsBtn"
                  className="text-button"
                  type="button"
                  onClick={handleResetColumns}
                  title="Reset column widths to default"
                >
                  Reset columns
                </button>
              </div>

              {/* Quick Filter Badges Bar */}
              <div className="quick-filters-bar">
                <button
                  type="button"
                  className={`quick-filter-pill ${remoteFilter === 'remote' ? 'active' : ''}`}
                  onClick={() => {
                    setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote');
                    setCurrentPage(1);
                  }}
                >
                  🌐 Remote Only
                </button>
                <button
                  type="button"
                  className={`quick-filter-pill ${onlySalaryListed ? 'active' : ''}`}
                  onClick={() => {
                    setOnlySalaryListed(!onlySalaryListed);
                    setCurrentPage(1);
                  }}
                >
                  💰 Salary Disclosed
                </button>
                <button
                  type="button"
                  className={`quick-filter-pill ${onlyNigerianBoards ? 'active' : ''}`}
                  onClick={() => {
                    setOnlyNigerianBoards(!onlyNigerianBoards);
                    setCurrentPage(1);
                  }}
                >
                  🇳🇬 Nigerian Boards
                </button>
              </div>

              <div className="filter-summary">
                <p id="filterSummary" aria-live="polite" style={{ margin: 0 }}>
                  {rawResults.length === filteredResults.length
                    ? `${rawResults.length} result${rawResults.length === 1 ? '' : 's'}`
                    : `Showing ${filteredResults.length} of ${rawResults.length} results`}
                </p>
                {totalPages > 1 && (
                  <span className="page-info">
                    Page {currentPage} of {totalPages}
                  </span>
                )}
              </div>

              <div className="results-wrap" ref={resultsWrapRef}>
                <table style={{ width: `max(100%, ${totalTableWidth}px)` }}>
                  <colgroup>
                    {DEFAULT_COLUMNS.map((col) => {
                      const width =
                        col.id === 'role' ? colWidths[col.id] + extraRoleWidth : colWidths[col.id];
                      return <col key={col.id} style={{ width: `${width}px` }} />;
                    })}
                  </colgroup>
                  <thead>
                    <tr>
                      {DEFAULT_COLUMNS.map((col) => {
                        const isSortable = !!col.sortField;
                        const isSorted = isSortable && sortField === col.sortField;
                        return (
                          <th
                            key={col.id}
                            className={isSortable ? `sortable ${isSorted ? 'sorted' : ''}` : ''}
                            onClick={isSortable ? () => handleSort(col.sortField!) : undefined}
                          >
                            <div className="th-content" title={col.label}>
                              <span>{col.label}</span>
                              {isSortable && (
                                <span className="sort-arrow">
                                  {isSorted ? (sortAsc ? '↑' : '↓') : '↕'}
                                </span>
                              )}
                            </div>
                            <div
                              className="col-resize-handle"
                              role="separator"
                              aria-orientation="vertical"
                              title="Drag to resize, double-click to reset"
                              onPointerDown={(e) => handleResizePointerDown(col.id, e)}
                              onDoubleClick={(e) => {
                                e.stopPropagation();
                                handleResetSingleColumn(col.id);
                              }}
                            />
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody id="resultsBody">
                    {paginatedResults.map((job) => {
                      const isExpanded = expandedJobId === job.id;
                      const modelClass =
                        job.work_model === 'remote'
                          ? 'badge-model-remote'
                          : job.work_model === 'hybrid'
                            ? 'badge-model-hybrid'
                            : job.work_model === 'in_person'
                              ? 'badge-model-onsite'
                              : 'badge-model-unspecified';
                      const tooltip = job.work_model_source
                        ? `Source: ${job.work_model_source}${job.work_model_evidence ? ` (${job.work_model_evidence})` : ''}`
                        : undefined;

                      return (
                        <React.Fragment key={job.id}>
                          <tr>
                            <td title={job.displayTitle}>
                              <span className="cell-role">{job.displayTitle}</span>
                            </td>
                            <td title={job.company}>
                              <span className="cell-ellipsis">{job.company}</span>
                            </td>
                            <td title={job.displayLocation}>
                              <span className="cell-ellipsis">{job.displayLocation}</span>
                            </td>
                            <td title={job.displaySalary}>
                              <span className="cell-ellipsis">
                                <span
                                  className={`salary-text ${job.displaySalary !== 'Not listed' ? 'salary-listed' : ''}`}
                                >
                                  {job.displaySalary}
                                </span>
                              </span>
                            </td>
                            <td title={job.displayEmployment}>
                              <span className="cell-ellipsis">{job.displayEmployment}</span>
                            </td>
                            <td title={tooltip}>
                              <span className="cell-ellipsis">
                                <span className={`badge-model ${modelClass}`}>
                                  {job.displayLocationType}
                                </span>
                              </span>
                            </td>
                            <td title={job.displayPostedDate}>
                              <span className="cell-ellipsis">{job.displayPostedDate}</span>
                            </td>
                            <td title={job.provider}>
                              <span className="cell-ellipsis">
                                <span className="badge-source">{job.provider}</span>
                              </span>
                            </td>
                            <td>
                              <div className="row-actions">
                                <button
                                  className="text-button detail-toggle"
                                  type="button"
                                  aria-expanded={isExpanded}
                                  onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                                >
                                  {isExpanded ? 'Hide details' : 'Details'}
                                </button>
                                <a
                                  href={job.apply_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  Apply -&gt;
                                </a>
                              </div>
                            </td>
                          </tr>

                          {isExpanded && (
                            <tr className="detail-row">
                              <td colSpan={DEFAULT_COLUMNS.length}>
                                <article
                                  className="job-detail-panel"
                                  aria-label={`${job.displayTitle} details`}
                                  style={{
                                    width: visibleWrapWidth ? `${visibleWrapWidth}px` : '100%',
                                  }}
                                >
                                  <header className="detail-panel-header">
                                    <div className="detail-panel-title-area">
                                      <h3 className="detail-panel-title">{job.displayTitle}</h3>
                                      <div className="detail-panel-sub">
                                        <span className="detail-panel-company">{job.company}</span>
                                        {job.displayLocation && (
                                          <>
                                            <span className="detail-panel-sep">·</span>
                                            <span>{job.displayLocation}</span>
                                          </>
                                        )}
                                        <span className={`badge-model ${modelClass}`} title={tooltip}>
                                          {job.displayLocationType}
                                        </span>
                                      </div>
                                    </div>
                                    <div className="detail-panel-actions">
                                      <a
                                        href={job.apply_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="primary-button detail-apply-btn"
                                      >
                                        Apply ↗
                                      </a>
                                      <button
                                        type="button"
                                        className="copy-btn"
                                        onClick={() => copyApplyUrl(job.apply_url, job.id)}
                                      >
                                        {copiedId === job.id ? '✓ Link Copied' : '📋 Copy Link'}
                                      </button>
                                      <a
                                        href={job.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-button"
                                      >
                                        Open source posting ↗
                                      </a>
                                    </div>
                                  </header>

                                  <div className="detail-panel-body">
                                    <div className="detail-panel-main">
                                      <section className="detail-section">
                                        <h4>Job Description</h4>
                                        <div className="markdown-content">
                                          <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            rehypePlugins={[rehypeSanitize]}
                                          >
                                            {job.description ||
                                              job.summary ||
                                              'No description was returned for this posting.'}
                                          </ReactMarkdown>
                                        </div>
                                      </section>
                                      {job.requirements && (
                                        <section className="detail-section">
                                          <h4>Requirements</h4>
                                          <div className="markdown-content">
                                            <ReactMarkdown
                                              remarkPlugins={[remarkGfm]}
                                              rehypePlugins={[rehypeSanitize]}
                                            >
                                              {job.requirements}
                                            </ReactMarkdown>
                                          </div>
                                        </section>
                                      )}
                                    </div>

                                    <aside className="detail-panel-aside">
                                      <div className="aside-group">
                                        <span className="aside-label">Salary</span>
                                        <strong
                                          className={
                                            job.displaySalary !== 'Not listed' ? 'salary-listed' : ''
                                          }
                                        >
                                          {job.displaySalary}
                                        </strong>
                                      </div>
                                      <div className="aside-group">
                                        <span className="aside-label">Job type</span>
                                        <strong>{job.displayEmployment}</strong>
                                      </div>
                                      <div className="aside-group">
                                        <span className="aside-label">Posted date</span>
                                        <strong>{job.displayPostedDate}</strong>
                                      </div>
                                      <div className="aside-group">
                                        <span className="aside-label">Provider / Data source</span>
                                        <strong>
                                          {job.provider}
                                          {job.data_source ? ` - ${job.data_source}` : ''}
                                        </strong>
                                      </div>
                                      <div className="aside-group">
                                        <span className="aside-label">Work model</span>
                                        <div className="aside-work-model">
                                          <span className={`badge-model ${modelClass}`}>
                                            {job.displayLocationType}
                                          </span>
                                          {job.work_model_source && (
                                            <div className="aside-evidence">
                                              <span className="evidence-source">
                                                Source: {job.work_model_source}
                                              </span>
                                              {job.work_model_evidence && (
                                                <span className="evidence-snippet">
                                                  "{job.work_model_evidence}"
                                                </span>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </aside>
                                  </div>
                                </article>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
                {filteredResults.length === 0 && (
                  <p id="emptyState" className="empty-state">
                    No matching postings were returned. Try a broader role or date range.
                  </p>
                )}
              </div>

              {/* Pagination Bar */}
              {totalPages > 1 && (
                <div className="pagination-bar">
                  <div className="pagination-controls">
                    <button
                      type="button"
                      className="page-btn"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      &larr; Previous
                    </button>
                    <span className="page-info">
                      Page {currentPage} of {totalPages} ({sortedResults.length} items)
                    </span>
                    <button
                      type="button"
                      className="page-btn"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next &rarr;
                    </button>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="page-info">Show per page:</span>
                    {[20, 50, 100].map((size) => (
                      <button
                        key={size}
                        type="button"
                        className={`chip-btn ${pageSize === size ? 'active' : ''}`}
                        onClick={() => {
                          setPageSize(size);
                          setCurrentPage(1);
                        }}
                      >
                        {size}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {screen === 'error' && (
            <div id="errorScreen" className="error-screen" role="alert">
              <strong>Search could not be completed.</strong>
              <p id="errorMessage">{errorMessage}</p>
              <button
                id="errorResetBtn"
                className="text-button"
                type="button"
                onClick={handleReset}
              >
                Return to search
              </button>
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
