import React from 'react';
import type {
  JobListing,
  NormalizedJob,
  DoneMetrics,
  SearchParams,
  SortField,
} from '../types';
import type { SavedJobEntry, ApplicationStage } from '../lib/savedJobs';
import type { RecentSearchPreset } from '../lib/urlState';
import { Header } from './Header';
import { SearchForm } from './SearchForm';
import { LoadingState, ErrorState, NoResultsState } from './States';
import { SearchSummaryBar } from './SearchSummaryBar';
import { Toolbar } from './Toolbar';
import { ResultsTable } from './ResultsTable';
import { ResultsCards } from './ResultsCards';
import { DetailSheet } from './DetailSheet';
import { ShortcutsModal } from './ShortcutsModal';
import { CommandPalette } from './CommandPalette';
import { TelemetryDeck } from './TelemetryDeck';
import { ScrollButton } from './prompt-kit/scroll-button';
import { Toaster } from './ui/sonner';

export interface WorkspaceSearchProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  handleSubmit: (e: React.FormEvent) => void;
  handleCancelSearch: () => void;
  handleEditSearch: () => void;
  handleNewSearch: () => void;
  executeSearch: (customParams?: SearchParams) => Promise<void>;
  selectedPlatforms: string[];
  setSelectedPlatforms: React.Dispatch<React.SetStateAction<string[]>>;
  recentSearches: RecentSearchPreset[];
  handleSelectRecentSearch: (query: RecentSearchPreset) => void;
  savedCount: number;
  handleOpenSavedShortlist: () => void;
  handleWidenDateRange: () => void;
  loadingMessage: string;
  errorMessage: string;
  isRateLimited: boolean;
}

export interface WorkspaceFilterProps {
  tableSearch: string;
  setTableSearch: (val: string) => void;
  providerFilter: string;
  setProviderFilter: (val: string) => void;
  remoteFilter: string;
  setRemoteFilter: (val: string) => void;
  employmentFilter: string;
  setEmploymentFilter: (val: string) => void;
  onlySalaryListed: boolean;
  setOnlySalaryListed: (val: boolean) => void;
  onlySavedJobs: boolean;
  setOnlySavedJobs: (val: boolean) => void;
  availableProviders: string[];
  availableEmploymentTypes: string[];
  handleClearFilters: () => void;
  searchInputRef: React.RefObject<HTMLInputElement | null>;
}

export interface WorkspaceResultProps {
  rawResults: JobListing[];
  normalizedList: NormalizedJob[];
  sortedResults: NormalizedJob[];
  metrics: DoneMetrics | null;
  savedTimestamp: number | null;
  savedJobsMap: Record<string, SavedJobEntry>;
  sortField: SortField;
  sortAsc: boolean;
  handleSort: (field: SortField) => void;
  selectedJob: NormalizedJob | null;
  setSelectedJob: (job: NormalizedJob | null) => void;
  activeRowIndex: number;
  handleMarkVisited: (urlOrId: string) => void;
  handleToggleSave: (job: NormalizedJob) => void;
  handleChangeStage: (job: NormalizedJob, stage: ApplicationStage) => void;
  handleClearSavedResults: () => void;
  handleDownloadCsv: () => void;
  handleDownloadJson: () => void;
  handleCopyShareLink: () => void;
  resultsContainerRef: React.RefObject<HTMLDivElement | null>;
}

export interface WorkspaceShellProps {
  screen: 'form' | 'loading' | 'delivery' | 'error';
  switchScreen: (newScreen: 'form' | 'loading' | 'delivery' | 'error') => void;
  transitionView: (newView: 'marketing' | 'workspace') => void;
  theme: 'light' | 'dark';
  handleToggleTheme: () => void;
  telemetryOpen: boolean;
  setTelemetryOpen: React.Dispatch<React.SetStateAction<boolean>>;
  commandOpen: boolean;
  setCommandOpen: React.Dispatch<React.SetStateAction<boolean>>;
  shortcutsOpen: boolean;
  setShortcutsOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

export interface WorkspaceProps {
  search: WorkspaceSearchProps;
  filters: WorkspaceFilterProps;
  results: WorkspaceResultProps;
  shell: WorkspaceShellProps;
}

export function Workspace({ search, filters, results, shell }: WorkspaceProps) {
  const {
    searchParams,
    setSearchParams,
    handleSubmit,
    handleCancelSearch,
    handleEditSearch,
    handleNewSearch,
    executeSearch,
    selectedPlatforms,
    setSelectedPlatforms,
    recentSearches,
    handleSelectRecentSearch,
    savedCount,
    handleOpenSavedShortlist,
    handleWidenDateRange,
    loadingMessage,
    errorMessage,
    isRateLimited,
  } = search;

  const {
    tableSearch,
    setTableSearch,
    providerFilter,
    setProviderFilter,
    remoteFilter,
    setRemoteFilter,
    employmentFilter,
    setEmploymentFilter,
    onlySalaryListed,
    setOnlySalaryListed,
    onlySavedJobs,
    setOnlySavedJobs,
    availableProviders,
    availableEmploymentTypes,
    handleClearFilters,
    searchInputRef,
  } = filters;

  const {
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
  } = results;

  const {
    screen,
    switchScreen,
    transitionView,
    theme,
    handleToggleTheme,
    telemetryOpen,
    setTelemetryOpen,
    commandOpen,
    setCommandOpen,
    shortcutsOpen,
    setShortcutsOpen,
  } = shell;

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
export default Workspace;
