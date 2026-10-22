import type { JobListing } from '../types';
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

export function isJobSaved(jobId: string): boolean {
  const map = getSavedJobsMap();
  return Boolean(map[jobId]);
}

export function getJobStage(jobId: string): ApplicationStage | null {
  const map = getSavedJobsMap();
  return map[jobId]?.stage || null;
}

export function toggleSavedJob(job: JobListing): {
  saved: boolean;
  entry?: SavedJobEntry;
  map: Record<string, SavedJobEntry>;
} {
  const map = { ...getSavedJobsMap() };
  if (map[job.id]) {
    delete map[job.id];
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
  const existing = map[job.id];
  map[job.id] = {
    job: existing?.job || job,
    stage,
    savedAt: existing?.savedAt || now,
    updatedAt: now,
  };
  writeStorage(STORAGE_KEY, map);
  return map;
}
