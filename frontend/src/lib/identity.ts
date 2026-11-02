import type { JobListing } from '../types';

/**
 * Shared alias-matching helper.
 * Returns true if candidate matches target either by direct ID, target aliases, candidate aliases,
 * or intersection of aliases.
 */
export function matchesJobIdentity(
  candidate: { id: string; aliases?: string[] },
  target: { id: string; aliases?: string[] } | string
): boolean {
  if (!candidate || !target) return false;

  const targetId = typeof target === 'string' ? target : target.id;
  const targetAliases = typeof target === 'string' ? [] : target.aliases || [];

  // 1. Direct ID match
  if (candidate.id === targetId) return true;

  // 2. Candidate ID matches any target alias
  if (targetAliases.includes(candidate.id)) return true;

  // 3. Target ID matches any candidate alias
  if (candidate.aliases && candidate.aliases.includes(targetId)) return true;

  // 4. Any candidate alias intersects with any target alias
  if (candidate.aliases && targetAliases.length > 0) {
    for (const a of candidate.aliases) {
      if (targetAliases.includes(a)) return true;
    }
  }

  return false;
}

/**
 * In-place batch upsert helper.
 * Replaces matching snippet cards in place using alias identity matching,
 * appending only genuinely new records.
 */
export function upsertJobBatch(
  existing: JobListing[],
  incomingBatch: JobListing[]
): { results: JobListing[]; upgradedCount: number } {
  const next = [...existing];
  let upgradedCount = 0;

  for (const incoming of incomingBatch) {
    let matchedIdx = -1;
    for (let i = 0; i < next.length; i++) {
      if (matchesJobIdentity(next[i], incoming)) {
        matchedIdx = i;
        break;
      }
    }

    if (matchedIdx >= 0) {
      next[matchedIdx] = incoming;
      upgradedCount++;
    } else {
      next.push(incoming);
    }
  }

  return { results: next, upgradedCount };
}
