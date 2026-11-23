/**
 * Backend-first eligibility display facade.
 *
 * Prefers server-computed `eligibility.objective_scope_label` and
 * `eligibility.applicant_assessment` (via `/search` or `/api/eligibility/evaluate`),
 * falling back to `legacyEligibilityFallback.ts` only for legacy cached/offline items.
 */

import type {
  ApplicantEligibilityAssessment,
  EligibilityStatus,
  JobEligibility,
} from '../types';
import { normalizeCountryCode } from './countries';
import {
  legacyBuildObjectiveScopeLabel,
  legacyEvaluateEligibilityForCountry,
  normalizeWorkArrangement,
} from './legacyEligibilityFallback';

export {
  type WorkArrangement,
  formatAllowedScope,
  inferPhysicalCountryCode,
  normalizeWorkArrangement,
  shortCountryLabel,
  splitCountriesAndRegions,
} from './legacyEligibilityFallback';

export function buildObjectiveScopeLabel(
  eligibility?: JobEligibility | null,
  workModel?: string | null,
  location?: string | null
): string | null {
  const authoritative = eligibility?.objective_scope_label?.trim();
  if (authoritative) {
    return authoritative;
  }
  return legacyBuildObjectiveScopeLabel(eligibility, workModel, location);
}

export function evaluateEligibilityForCountry(
  eligibility?: JobEligibility | null,
  applicantCountry?: string | null,
  workModel?: string | null,
  location?: string | null
): ApplicantEligibilityAssessment | null {
  const cc = normalizeCountryCode(applicantCountry);
  if (!cc) return null;

  if (
    eligibility?.applicant_assessment &&
    normalizeCountryCode(eligibility.applicant_assessment.applicant_country_code) === cc
  ) {
    return eligibility.applicant_assessment;
  }

  return legacyEvaluateEligibilityForCountry(eligibility, cc, workModel, location);
}

export function formatApplicantStatusLabel(
  status: EligibilityStatus,
  countryName: string
): string {
  if (status === 'eligible') return `Eligible from ${countryName}`;
  if (status === 'restricted') return `Not eligible from ${countryName}`;
  return `Eligibility unverified for ${countryName}`;
}

export function buildCombinedWorkEligibilityLabel(
  workModel?: string | null,
  scopeLabel?: string | null,
  assessment?: ApplicantEligibilityAssessment | null
): string | null {
  if (assessment?.summary_label) {
    return assessment.summary_label;
  }
  const arrangement = normalizeWorkArrangement(workModel);
  const workPrefix =
    arrangement === 'remote'
      ? 'Remote'
      : arrangement === 'hybrid'
        ? 'Hybrid'
        : arrangement === 'onsite'
          ? 'Onsite'
          : null;
  if (workPrefix && scopeLabel) return `${workPrefix} · ${scopeLabel}`;
  return scopeLabel || workPrefix;
}
