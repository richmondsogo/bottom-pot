import type { NormalizedJob } from '../types';
import { buildObjectiveScopeLabel } from './eligibility';
import { normalizeWorkModelKind, type NormalizedWorkModel } from './normalize';

export { normalizeWorkModelKind, type NormalizedWorkModel };

export interface MobileMetaPart {
  text: string;
  toneClass: string;
}

export interface MobileCardMeta {
  normalizedWorkModel: NormalizedWorkModel;
  locationText: string | null;
  eligibilityText: string | null;
  eligibilityTone: string;
  combinedMetaParts: MobileMetaPart[];
}

const STOP_WORDS = new Set([
  'only',
  'restricted',
  'eligible',
  'from',
  'remote',
  'hybrid',
  'onsite',
  'on',
  'site',
  'in',
  'person',
  'fully',
  'work',
  'and',
  'or',
  'the',
]);

function normalizeToken(tok: string): string {
  if (tok === 'usa' || tok === 'u.s.' || tok === 'u.s' || tok === 'united' || tok === 'states') return 'us';
  if (tok === 'u.k.' || tok === 'uk' || tok === 'britain') return 'uk';
  if (tok === 'global' || tok === 'anywhere') return 'worldwide';
  return tok;
}

function tokenizeNormalized(input: string): string[] {
  const lower = input
    .toLowerCase()
    .replace(/\bunited states of america\b|\bunited states\b|\bu\.s\.a\.?\b|\bu\.s\.?\b/g, ' us ')
    .replace(/\bunited kingdom\b|\bu\.k\.?\b/g, ' uk ')
    .replace(/\b(worldwide|global|anywhere)\b/g, ' worldwide ');
  return lower
    .split(/[^a-z0-9]+/)
    .map((t) => normalizeToken(t))
    .filter((t) => t.length > 0 && !STOP_WORDS.has(t));
}

function cleanLocationSegment(segment: string, workModel: NormalizedWorkModel): string {
  let s = segment.trim();
  if (!s || s === '—') return '';

  if (workModel === 'remote') {
    if (/^(fully\s+)?remote$/i.test(s) || /^work from home$/i.test(s)) {
      return '';
    }
    const paren = s.match(/^(?:fully\s+)?remote\s*\(([^)]+)\)$/i);
    if (paren) {
      s = paren[1].trim();
    } else {
      s = s.replace(/^(?:fully\s+)?remote\s*[-–·,:]\s*/i, '').trim();
    }
  } else if (workModel === 'hybrid') {
    if (/^hybrid$/i.test(s)) return '';
    const paren = s.match(/^hybrid\s*\(([^)]+)\)$/i);
    if (paren) {
      s = paren[1].trim();
    }
  } else if (workModel === 'in_person') {
    if (/^(in[- ]person|on[- ]?site)$/i.test(s)) return '';
    const paren = s.match(/^(?:in[- ]person|on[- ]?site)\s*\(([^)]+)\)$/i);
    if (paren) {
      s = paren[1].trim();
    }
  }

  return s.trim();
}

function isCoveredByEligibility(locationSegment: string, eligibilityText: string | null): boolean {
  if (!eligibilityText) return false;
  const locLower = locationSegment.trim().toLowerCase();
  const eligLower = eligibilityText.trim().toLowerCase();
  if (!locLower) return true;
  if (eligLower === locLower || eligLower.includes(locLower)) return true;

  const locTokens = tokenizeNormalized(locationSegment);
  const eligTokens = new Set(tokenizeNormalized(eligibilityText));
  if (locTokens.length === 0) return true;
  return locTokens.every((t) => eligTokens.has(t));
}

/**
 * Computes deduplicated mobile row metadata (Line 4) without hiding distinct country restrictions.
 */
export function buildMobileCardMeta(job: NormalizedJob): MobileCardMeta {
  const normalizedWorkModel = normalizeWorkModelKind(job.work_model);

  const elig = job.displayEligibility;
  const eligibilityText: string | null = elig
    ? elig.status === 'restricted'
      ? elig.scopeLabel && !elig.scopeLabel.toLowerCase().includes('not eligible')
        ? `Restricted · ${elig.scopeLabel}`
        : elig.statusLabel || 'Restricted'
      : elig.status === 'eligible'
        ? elig.combinedLabel?.replace(/^(Remote|Hybrid|Onsite)\s*·\s*/i, '') ||
          elig.scopeLabel ||
          elig.statusLabel ||
          null
        : elig.scopeLabel || elig.statusLabel || null
    : buildObjectiveScopeLabel(job.eligibility, job.work_model, job.location);

  const eligibilityTone =
    elig?.status === 'restricted'
      ? 'text-[var(--danger-text)]'
      : elig?.status === 'eligible'
        ? 'text-[var(--ink)] font-medium'
        : 'text-[var(--ink-muted)]';

  const rawLocation = job.displayLocation && job.displayLocation !== '—' ? job.displayLocation.trim() : '';
  let locationText: string | null = null;

  if (rawLocation) {
    // Split compound strings like "Tokyo / Remote (Japan)" so distinct cities stay even when country is in eligibilityText
    const rawParts = rawLocation.includes(' / ') ? rawLocation.split(/\s*\/\s*/) : [rawLocation];
    const keptParts: string[] = [];
    for (const part of rawParts) {
      const cleaned = cleanLocationSegment(part, normalizedWorkModel);
      if (!cleaned) continue;
      if (isCoveredByEligibility(cleaned, eligibilityText)) continue;
      if (!keptParts.some((k) => k.toLowerCase() === cleaned.toLowerCase())) {
        keptParts.push(cleaned);
      }
    }
    if (keptParts.length > 0) {
      locationText = keptParts.join(' · ');
    }
  }

  const combinedMetaParts: MobileMetaPart[] = [];
  if (locationText) {
    combinedMetaParts.push({ text: locationText, toneClass: 'text-[var(--ink-muted)]' });
  }
  if (eligibilityText) {
    combinedMetaParts.push({ text: eligibilityText, toneClass: eligibilityTone });
  }

  return {
    normalizedWorkModel,
    locationText,
    eligibilityText,
    eligibilityTone,
    combinedMetaParts,
  };
}

/**
 * Handles tapping the mobile row quick-save bookmark without opening DetailSheet.
 */
export function handleMobileQuickSaveClick(
  event: { stopPropagation: () => void },
  job: NormalizedJob,
  onToggleSave?: (job: NormalizedJob) => void
): void {
  event.stopPropagation();
  onToggleSave?.(job);
}
