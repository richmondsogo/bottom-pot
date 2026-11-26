import React, { Suspense, lazy } from 'react';
import type {
  JobListing,
  NormalizedJob,
  DoneMetrics,
  SearchParams,
  SortField,
  EligibilityFilterMode,
} from '../types';
import { isJobSaved, getJobStage, type SavedJobEntry, type ApplicationStage } from '../lib/savedJobs';
import type { RecentSearchPreset } from '../lib/urlState';
import type { AppRoute } from '../lib/router';
import { Header } from './Header';
import { Footer } from './Footer';
import { SearchForm } from './SearchForm';
import { LoadingState, ErrorState, NoResultsState } from './States';
import { CompactSearchBar } from './CompactSearchBar';
import { Toolbar } from './Toolbar';
import { ResultsTable } from './ResultsTable';
import { ResultsCards } from './ResultsCards';
import { ScrollButton } from './prompt-kit/scroll-button';
import { Toaster } from './ui/sonner';

const DetailSheet = lazy(() => import('./DetailSheet').then((m) => ({ default: m.DetailSheet })));
const ShortcutsModal = lazy(() => import('./ShortcutsModal').then((m) => ({ default: m.ShortcutsModal })));
const CommandPalette = lazy(() => import('./CommandPalette').then((m) => ({ default: m.CommandPalette })));
const TelemetryDeck = lazy(() => import('./TelemetryDeck').then((m) => ({ default: m.TelemetryDeck })));

interface WorkspaceStatusBannersProps {
  budgetExhausted?: boolean;
}

export const WorkspaceStatusBanners: React.FC<WorkspaceStatusBannersProps> = ({
  budgetExhausted = false,
}) => (
  <>
    {budgetExhausted && (
      <div
        role="status"
        data-testid="budget-exhausted-notice"
        className="mb-3 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-subtle)] px-3.5 py-2.5 text-small text-[var(--ink)] flex flex-wrap items-center justify-between gap-2"
      >
        <span>
          Live web search is paused until UTC midnight. Showing roles from tracked company boards.
        </span>
        <span className="font-mono text-xs text-[var(--ink-muted)] shrink-0">LIMITED LIVE SEARCH</span>
      </div>
    )}
  </>
);

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
  applicantCountry: string;
  setApplicantCountry: (code: string) => void;
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
  eligibilityFilter: EligibilityFilterMode;
  setEligibilityFilter: (val: EligibilityFilterMode) => void;
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
  activeRoute: AppRoute;
  onNavigate: (route: AppRoute) => void;
  isStreaming: boolean;
  screen: 'form' | 'loading' | 'delivery' | 'error';
  switchScreen: (newScreen: 'form' | 'loading' | 'delivery' | 'error') => void;
  theme: 'light' | 'dark';
  handleToggleTheme: () => void;
  telemetryOpen: boolean;
  setTelemetryOpen: React.Dispatch<React.SetStateAction<boolean>>;
  commandOpen: boolean;
  setCommandOpen: React.Dispatch<React.SetStateAction<boolean>>;
  shortcutsOpen: boolean;
  setShortcutsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  onLogoEasterEgg?: () => void;
}

export interface WorkspaceProps {
  mode?: 'user' | 'admin';
  onLogout?: () => void;
  search: WorkspaceSearchProps;
  filters: WorkspaceFilterProps;
  results: WorkspaceResultProps;
  shell: WorkspaceShellProps;
}

export function Workspace({ mode = 'user', onLogout, search, filters, results, shell }: WorkspaceProps) {
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
    activeRoute,
    onNavigate,
    isStreaming,
    screen,
    theme,
    handleToggleTheme,
    telemetryOpen,
    setTelemetryOpen,
    commandOpen,
    setCommandOpen,
    shortcutsOpen,
    setShortcutsOpen,
    onLogoEasterEgg,
  } = shell;

  return (
    <div className="app-container min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
      <Header
        activeRoute={activeRoute}
        onNavigate={onNavigate}
        onStartNewSearch={handleNewSearch}
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onOpenCommand={() => setCommandOpen(true)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        mode={mode}
        onLogout={onLogout}
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
              applicantCountry={applicantCountry}
              onChangeApplicantCountry={setApplicantCountry}
              recentSearches={recentSearches}
              onSelectRecentSearch={handleSelectRecentSearch}
              savedCount={savedCount}
              onOpenSavedShortlist={handleOpenSavedShortlist}
              mode={mode}
            />
          </div>
        )}

        {screen === 'loading' && (
          <div className="page-shell py-8 sm:py-12 space-y-4">
            {mode === 'admin' ? (
              <>
                <Suspense fallback={null}>
                  <TelemetryDeck
                    metrics={metrics}
                    totalResults={rawResults.length}
                    isStreaming={true}
                    streamingMessage={loadingMessage}
                    onCancelStream={handleCancelSearch}
                    showSummaryStrip={false}
                  />
                </Suspense>
                <LoadingState onCancel={handleCancelSearch} statusMessage={loadingMessage} mode={mode} />
              </>
            ) : (
              <LoadingState onCancel={handleCancelSearch} statusMessage={loadingMessage} mode={mode} />
            )}
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
            {/* Sticky Compact Re-Query Bar + Quiet Summary Line */}
            <CompactSearchBar
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSubmit={handleSubmit}
              selectedPlatforms={selectedPlatforms}
              setSelectedPlatforms={setSelectedPlatforms}
              isStreaming={isStreaming}
              onCancelSearch={handleCancelSearch}
              totalResults={onlySavedJobs ? normalizedList.length : rawResults.length}
              filteredCount={sortedResults.length}
              onlySavedJobs={onlySavedJobs}
              mode={mode}
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
                applicantCountry={applicantCountry}
                onChangeApplicantCountry={setApplicantCountry}
                eligibilityFilter={eligibilityFilter}
                setEligibilityFilter={setEligibilityFilter}
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
              {/* Collapsible Prompt Kit Telemetry Deck (Admin only) */}
              {mode === 'admin' && (metrics || isStreaming) && (
                <Suspense fallback={null}>
                  <TelemetryDeck
                    metrics={metrics}
                    totalResults={rawResults.length}
                    isStreaming={isStreaming}
                    streamingMessage={isStreaming ? loadingMessage : undefined}
                    onCancelStream={isStreaming ? handleCancelSearch : undefined}
                    savedTimestamp={savedTimestamp}
                    isOpen={telemetryOpen}
                    onToggleOpen={() => setTelemetryOpen((prev) => !prev)}
                    showSummaryStrip={false}
                    onRunAgain={() => executeSearch()}
                    onClearSaved={handleClearSavedResults}
                  />
                </Suspense>
              )}
              <WorkspaceStatusBanners
                budgetExhausted={Boolean(metrics?.budget_exhausted || metrics?.incomplete)}
              />
              {rawResults.length === 0 && !onlySavedJobs ? (
                <NoResultsState
                  onWidenDateRange={handleWidenDateRange}
                  onClearFilters={handleClearFilters}
                  onNewSearch={handleNewSearch}
                  mode={mode}
                  incomplete={metrics?.incomplete}
                />
              ) : (
                <div className="mt-2">
                  {sortedResults.length === 0 ? (
                    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-[var(--ink-muted)]">
                      <p className="font-semibold text-body text-[var(--ink)] mb-2">
                        No postings match the active filters
                      </p>
                      <p className="text-small mb-4 text-[var(--ink-muted)]">
                        Try clearing search keywords, remote status, or platform filters.
                      </p>
                      <button
                        type="button"
                        className="h-9 max-md:h-11 px-3 rounded-md text-small font-medium border border-[var(--border-strong)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors"
                        onClick={handleClearFilters}
                      >
                        Clear filters
                      </button>
                    </div>
                  ) : (
                    <>
                      {/* Desktop quiet shortcut cue & fixed-layout table */}
                      <div className="table-desktop-view hidden md:block">
                        <div className="flex justify-end pb-1.5 text-[11px] text-[var(--ink-subtle)] select-none">
                          <span>j/k navigate · s save · / filter</span>
                        </div>
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
                          sortField={sortField}
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

      <Footer
        activeRoute={activeRoute}
        onNavigate={onNavigate}
        onNewSearch={handleNewSearch}
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onLogoEasterEgg={onLogoEasterEgg}
      />

      {/* Command Palette (Cmd+K / Ctrl+K) (Admin only) */}
      {mode === 'admin' && (
        <Suspense fallback={null}>
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
            onSwitchToMarketing={() => onNavigate('home')}
            theme={theme}
            onToggleTheme={handleToggleTheme}
            hasResults={rawResults.length > 0}
            hasSavedResults={Boolean(savedTimestamp)}
          />
        </Suspense>
      )}

      {/* Detail Sheet Overlay (lazy chunk loaded on demand) */}
      {selectedJob && (
        <Suspense fallback={null}>
          <DetailSheet
            job={selectedJob}
            onClose={() => setSelectedJob(null)}
            onMarkVisited={handleMarkVisited}
            isSaved={Boolean(selectedJob && isJobSaved(selectedJob, savedJobsMap))}
            savedStage={selectedJob ? getJobStage(selectedJob, savedJobsMap) : null}
            onToggleSave={handleToggleSave}
            onChangeStage={handleChangeStage}
            applicantCountry={applicantCountry}
            mode={mode}
          />
        </Suspense>
      )}

      {/* Keyboard Shortcuts Modal */}
      {shortcutsOpen && (
        <Suspense fallback={null}>
          <ShortcutsModal
            isOpen={shortcutsOpen}
            onClose={() => setShortcutsOpen(false)}
            mode={mode}
          />
        </Suspense>
      )}

      {/* Toast notifications */}
      <Toaster theme={theme} />
    </div>
  );
}
export default Workspace;
