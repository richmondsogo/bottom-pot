import type { JobListing } from '../types';
import { matchesJobIdentity } from './identity';
import { readStorage, writeStorage } from './storage';

export type ApplicationStage = 'saved' | 'applied' | 'interviewing' | 'archived';

export interface SavedJobEntry {
  job: JobListing;
  stage: ApplicationStage;
  savedAt: number;
  updatedAt: number;
}

const STORAGE_KEY = 'bp.shortlist.v1';

export const STAGE_LABELS: Record<ApplicationStage, string> = {
  saved: 'Saved',
  applied: 'Applied',
  interviewing: 'Interviewing',
  archived: 'Archived',
};

export const APPLICATION_STAGES: ApplicationStage[] = [
  'saved',
  'applied',
  'interviewing',
  'archived',
];

export function getSavedJobsMap(): Record<string, SavedJobEntry> {
  return readStorage<Record<string, SavedJobEntry>>(STORAGE_KEY, {});
}

export function getSavedJobsList(): SavedJobEntry[] {
  const map = getSavedJobsMap();
  return Object.values(map).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function findSavedJobEntry(
  job: { id: string; aliases?: string[] } | string,
  map?: Record<string, SavedJobEntry>
): SavedJobEntry | null {
  const savedMap = map ?? getSavedJobsMap();
  const targetId = typeof job === 'string' ? job : job.id;

  // Direct ID match fast path
  if (savedMap[targetId]) {
    return savedMap[targetId];
  }

  // Alias matching path
  for (const entry of Object.values(savedMap)) {
    if (matchesJobIdentity(entry.job, job)) {
      return entry;
    }
  }

  return null;
}

export function isJobSaved(
  job: { id: string; aliases?: string[] } | string,
  map?: Record<string, SavedJobEntry>
): boolean {
  return findSavedJobEntry(job, map) !== null;
}

export function getJobStage(
  job: { id: string; aliases?: string[] } | string,
  map?: Record<string, SavedJobEntry>
): ApplicationStage | null {
  return findSavedJobEntry(job, map)?.stage ?? null;
}

export function toggleSavedJob(job: JobListing): {
  saved: boolean;
  entry?: SavedJobEntry;
  map: Record<string, SavedJobEntry>;
} {
  const map = { ...getSavedJobsMap() };
  const existingEntry = findSavedJobEntry(job, map);

  if (existingEntry) {
    // Delete using key under which it is stored in map
    delete map[existingEntry.job.id];
    writeStorage(STORAGE_KEY, map);
    return { saved: false, map };
  }

  const now = Date.now();
  const entry: SavedJobEntry = {
    job,
    stage: 'saved',
    savedAt: now,
    updatedAt: now,
  };
  map[job.id] = entry;
  writeStorage(STORAGE_KEY, map);
  return { saved: true, entry, map };
}

export function updateSavedJobStage(
  job: JobListing,
  stage: ApplicationStage
): Record<string, SavedJobEntry> {
  const map = { ...getSavedJobsMap() };
  const now = Date.now();
  const existingEntry = findSavedJobEntry(job, map);
  const targetKey = existingEntry ? existingEntry.job.id : job.id;

  map[targetKey] = {
    job: existingEntry?.job || job,
    stage,
    savedAt: existingEntry?.savedAt || now,
    updatedAt: now,
  };
  writeStorage(STORAGE_KEY, map);
  return map;
}
