/**
 * Visited state management for job postings.
 * Follows the Daybreak "read" pattern to dim postings the user has already opened.
 * Persisted in localStorage with try/catch safeguards for private/restricted browsing.
 */

const STORAGE_KEY = 'bp.visited';
const MAX_ENTRIES = 1000;

function getStore(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return new Set(parsed);
    }
  } catch {
    // Ignore storage parse errors
  }
  return new Set();
}

function saveStore(store: Set<string>): void {
  try {
    // Cap stored entries to prevent localStorage bloat
    const list = Array.from(store);
    const capped = list.length > MAX_ENTRIES ? list.slice(list.length - MAX_ENTRIES) : list;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(capped));
  } catch {
    // Ignore QuotaExceededError or disabled storage
  }
}

/** Check if a job posting has been visited. */
export function isVisited(idOrUrl: string): boolean {
  if (!idOrUrl) return false;
  return getStore().has(idOrUrl);
}

/** Mark a job posting as visited. */
export function markVisited(idOrUrl: string): void {
  if (!idOrUrl) return;
  const store = getStore();
  store.add(idOrUrl);
  saveStore(store);
}

/** Clear all visited postings. */
export function clearVisited(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

/** Return total number of visited postings. */
export function getVisitedCount(): number {
  return getStore().size;
}
