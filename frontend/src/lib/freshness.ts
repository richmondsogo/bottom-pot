import type { FreshnessTier, JobListing } from '../types';

export const FRESH_MAX_DAYS = 30;
export const RECENT_MAX_DAYS = 90;

export type ResolvedFreshnessTier = FreshnessTier | 'unknown';

export const FRESHNESS_TIER_ORDER: Record<ResolvedFreshnessTier, number> = {
  fresh: 0,
  recent: 1,
  evergreen: 2,
  unknown: 3,
  stale: 4,
};

function parseTimestampMs(raw?: string | null): number | null {
  if (!raw || !raw.trim()) return null;
  const trimmed = raw.trim();
  if (/^\d+$/.test(trimmed)) {
    const num = Number(trimmed);
    if (!Number.isFinite(num) || num <= 0) return null;
    return num > 1e12 ? num : num * 1000;
  }
  const ms = Date.parse(trimmed);
  return Number.isNaN(ms) ? null : ms;
}

export function computeAgeDays(
  postedAt?: string | null,
  firstSeenAt?: string | null,
  nowMs = Date.now()
): number | null {
  const refMs = parseTimestampMs(postedAt) ?? parseTimestampMs(firstSeenAt);
  if (refMs === null) return null;
  const diffDays = Math.floor((nowMs - refMs) / 86400000);
  return Math.max(0, diffDays);
}

export function resolveFreshnessTier(
  job: Pick<JobListing, 'freshness' | 'posted_at' | 'first_seen_at'>,
  nowMs = Date.now()
): ResolvedFreshnessTier {
  const rawTier = job.freshness?.toLowerCase().trim();
  if (rawTier === 'fresh' || rawTier === 'recent' || rawTier === 'stale' || rawTier === 'evergreen') {
    return rawTier;
  }

  const postedMs = parseTimestampMs(job.posted_at);
  if (postedMs !== null) {
    const days = Math.max(0, Math.floor((nowMs - postedMs) / 86400000));
    if (days <= FRESH_MAX_DAYS) return 'fresh';
    if (days <= RECENT_MAX_DAYS) return 'recent';
    return 'stale';
  }

  const seenMs = parseTimestampMs(job.first_seen_at);
  if (seenMs !== null) {
    const seenDays = Math.max(0, Math.floor((nowMs - seenMs) / 86400000));
    if (seenDays > RECENT_MAX_DAYS) return 'stale';
  }

  return 'unknown';
}

export function formatAgeBadgeLabel(
  ageDays: number | null,
  tier: ResolvedFreshnessTier
): string {
  let ageText = 'Date unlisted';
  if (ageDays !== null) {
    if (ageDays === 0) ageText = 'Today';
    else if (ageDays === 1) ageText = '1d ago';
    else if (ageDays < 30) ageText = `${ageDays}d ago`;
    else if (ageDays < 365) ageText = `${Math.max(1, Math.floor(ageDays / 30))}mo ago`;
    else ageText = `${Math.max(1, Math.floor(ageDays / 365))}y ago`;
  }

  if (tier === 'evergreen') return `${ageText} · Evergreen`;
  if (tier === 'stale') return `${ageText} · Older`;
  return ageText;
}

export function getFreshnessRankKey(tier?: ResolvedFreshnessTier | null): number {
  if (!tier) return FRESHNESS_TIER_ORDER.unknown;
  return FRESHNESS_TIER_ORDER[tier] ?? FRESHNESS_TIER_ORDER.unknown;
}
