import type { SearchParams } from '../types';
import { readStorage, writeStorage } from './storage';

export interface RecentSearchPreset {
  id: string;
  keywords: string;
  location: string;
  workModel: string;
  postAge: string;
  includeNigerian: boolean;
  timestamp: number;
}

const RECENT_SEARCHES_KEY = 'bp.recentSearches.v1';
const MAX_RECENT_SEARCHES = 5;

export function getRecentSearches(): RecentSearchPreset[] {
  return readStorage<RecentSearchPreset[]>(RECENT_SEARCHES_KEY, []);
}

export function recordRecentSearch(params: SearchParams): RecentSearchPreset[] {
  const kw = params.keywords.trim();
  if (!kw) return getRecentSearches();

  const loc = params.location.trim();
  const id = `${kw.toLowerCase()}|${loc.toLowerCase()}|${params.workModel}`;
  const existing = getRecentSearches().filter((item) => item.id !== id);
  const next: RecentSearchPreset[] = [
    {
      id,
      keywords: kw,
      location: loc,
      workModel: params.workModel || 'any',
      postAge: params.postAge || '7',
      includeNigerian: params.includeNigerian,
      timestamp: Date.now(),
    },
    ...existing,
  ].slice(0, MAX_RECENT_SEARCHES);

  writeStorage(RECENT_SEARCHES_KEY, next);
  return next;
}

export interface UrlSyncedState {
  searchParams?: Partial<SearchParams>;
  tableSearch?: string;
  providerFilter?: string;
  remoteFilter?: string;
  employmentFilter?: string;
  onlySalaryListed?: boolean;
  onlySavedJobs?: boolean;
}

export interface WorkspaceUrlState {
  searchParams: SearchParams;
  tableSearch: string;
  providerFilter: string;
  remoteFilter: string;
  employmentFilter: string;
  onlySalaryListed: boolean;
  onlySavedJobs: boolean;
}

export function readStateFromUrl(): UrlSyncedState | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  const hasAny =
    params.has('q') ||
    params.has('loc') ||
    params.has('wm') ||
    params.has('age') ||
    params.has('ng') ||
    params.has('flt') ||
    params.has('prov') ||
    params.has('rem') ||
    params.has('emp') ||
    params.has('sal') ||
    params.has('saved');

  if (!hasAny) return null;

  const searchParams: Partial<SearchParams> = {};
  if (params.has('q')) searchParams.keywords = params.get('q') || '';
  if (params.has('loc')) searchParams.location = params.get('loc') || '';
  if (params.has('wm')) searchParams.workModel = params.get('wm') || 'any';
  if (params.has('age')) searchParams.postAge = params.get('age') || '7';
  if (params.has('ng')) searchParams.includeNigerian = params.get('ng') !== '0';

  return {
    searchParams: Object.keys(searchParams).length > 0 ? searchParams : undefined,
    tableSearch: params.get('flt') || undefined,
    providerFilter: params.get('prov') || undefined,
    remoteFilter: params.get('rem') || undefined,
    employmentFilter: params.get('emp') || undefined,
    onlySalaryListed: params.has('sal') ? params.get('sal') === '1' : undefined,
    onlySavedJobs: params.has('saved') ? params.get('saved') === '1' : undefined,
  };
}

export function buildShareableSearchUrl(state: WorkspaceUrlState): string {
  if (typeof window === 'undefined') return '';
  const url = new URL(window.location.href);
  const currentMock = url.searchParams.get('mock');
  const nextParams = new URLSearchParams();

  if (currentMock) {
    nextParams.set('mock', currentMock);
  }
  if (state.searchParams.keywords.trim()) {
    nextParams.set('q', state.searchParams.keywords.trim());
  }
  if (state.searchParams.location.trim()) {
    nextParams.set('loc', state.searchParams.location.trim());
  }
  if (state.searchParams.workModel && state.searchParams.workModel !== 'any') {
    nextParams.set('wm', state.searchParams.workModel);
  }
  if (state.searchParams.postAge && state.searchParams.postAge !== '7') {
    nextParams.set('age', state.searchParams.postAge);
  }
  if (!state.searchParams.includeNigerian) {
    nextParams.set('ng', '0');
  }
  if (state.tableSearch.trim()) {
    nextParams.set('flt', state.tableSearch.trim());
  }
  if (state.providerFilter) {
    nextParams.set('prov', state.providerFilter);
  }
  if (state.remoteFilter) {
    nextParams.set('rem', state.remoteFilter);
  }
  if (state.employmentFilter) {
    nextParams.set('emp', state.employmentFilter);
  }
  if (state.onlySalaryListed) {
    nextParams.set('sal', '1');
  }
  if (state.onlySavedJobs) {
    nextParams.set('saved', '1');
  }

  const qs = nextParams.toString();
  return `${url.origin}${url.pathname}${qs ? `?${qs}` : ''}`;
}

export function syncStateToUrl(
  screen: 'form' | 'loading' | 'delivery' | 'error',
  state: WorkspaceUrlState
): void {
  if (typeof window === 'undefined' || !window.history?.replaceState) return;
  if (screen !== 'delivery') {
    const url = new URL(window.location.href);
    const currentMock = url.searchParams.get('mock');
    const cleanUrl = `${url.pathname}${currentMock ? `?mock=${encodeURIComponent(currentMock)}` : ''}`;
    if (`${window.location.pathname}${window.location.search}` !== cleanUrl) {
      window.history.replaceState(null, '', cleanUrl);
    }
    return;
  }

  const shareable = buildShareableSearchUrl(state);
  if (shareable && shareable !== window.location.href) {
    const parsed = new URL(shareable);
    window.history.replaceState(null, '', `${parsed.pathname}${parsed.search}`);
  }
}
