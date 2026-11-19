import type {
  ApplicantEligibilityAssessment,
  EligibilityStatus,
  JobEligibility,
} from '../types';
import {
  UNIFORM_CAPABLE_REGIONS,
  getCountryByCode,
  isCountryInRegion,
  normalizeCountryCode,
  normalizeRegionName,
} from './countries';

const US_STATE_CODES = new Set([
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
  'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
  'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
  'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
]);

const CANADIAN_PROVINCE_TOKENS = new Set([
  'ON', 'BC', 'QC', 'AB', 'MB', 'SK', 'NS', 'NB', 'PE', 'NL', 'YT', 'NT', 'NU',
  'ontario', 'quebec', 'british columbia', 'alberta', 'manitoba', 'saskatchewan',
  'nova scotia', 'new brunswick',
]);

const GENERIC_NON_CITY_LOCATIONS = new Set(['africa', 'global', 'remote', 'worldwide']);

export type WorkArrangement = 'remote' | 'hybrid' | 'onsite' | 'unknown';

export function normalizeWorkArrangement(workModel?: string | null): WorkArrangement {
  const wm = (workModel || '').trim().toLowerCase().replace(/[-\s]/g, '_');
  if (wm === 'remote') return 'remote';
  if (wm === 'hybrid') return 'hybrid';
  if (wm === 'in_person' || wm === 'onsite' || wm === 'on_site') return 'onsite';
  return 'unknown';
}

export function splitCountriesAndRegions(labels?: string[] | null): {
  codes: string[];
  regions: string[];
} {
  if (!labels || labels.length === 0) {
    return { codes: [], regions: [] };
  }
  const codes: string[] = [];
  const regions: string[] = [];
  for (const item of labels) {
    const reg = normalizeRegionName(item);
    if (reg && reg !== 'Worldwide') {
      if (!regions.includes(reg)) regions.push(reg);
      continue;
    }
    const code = normalizeCountryCode(item);
    if (code && !codes.includes(code)) {
      codes.push(code);
    }
  }
  return { codes, regions };
}

export function inferPhysicalCountryCode(
  eligibility?: JobEligibility | null,
  location?: string | null
): string | null {
  if (eligibility?.physical_location_country_code) {
    const norm = normalizeCountryCode(eligibility.physical_location_country_code);
    if (norm) return norm;
  }
  if (eligibility?.physical_location_country) {
    const norm = normalizeCountryCode(eligibility.physical_location_country);
    if (norm) return norm;
  }
  if (location) {
    const firstLoc = location.split(';')[0]?.trim() || '';
    const parts = firstLoc.split(',').map((p) => p.trim()).filter(Boolean);
    const tail = parts[parts.length - 1] || firstLoc;
    const tailUpper = tail.toUpperCase();
    const hasCanadaContext = parts.slice(0, -1).some((p) => {
      const low = p.toLowerCase();
      return (
        low === 'canada' ||
        CANADIAN_PROVINCE_TOKENS.has(p.toUpperCase()) ||
        CANADIAN_PROVINCE_TOKENS.has(low)
      );
    });
    if (parts.length >= 2 && US_STATE_CODES.has(tailUpper) && !hasCanadaContext) {
      return 'US';
    }
    const norm = normalizeCountryCode(tail);
    if (norm) return norm;
  }
  return null;
}

export function shortCountryLabel(code: string): string {
  if (code === 'US') return 'US';
  if (code === 'GB') return 'UK';
  return getCountryByCode(code)?.name || code;
}

export function formatAllowedScope(
  allowedCodes: string[],
  allowedRegions: string[]
): string | null {
  const parts: string[] = allowedCodes.map((c) => shortCountryLabel(c));
  for (const r of allowedRegions) {
    if (!parts.includes(r)) parts.push(r);
  }
  if (parts.length === 0) return null;
  if (parts.length === 1) return `${parts[0]} only`;
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`;
}

function getNormalizedRestrictionLists(eligibility?: JobEligibility | null) {
  let allowedCodes = [...(eligibility?.allowed_country_codes || [])];
  let allowedRegions = [...(eligibility?.allowed_regions || [])];
  if (
    allowedCodes.length === 0 &&
    allowedRegions.length === 0 &&
    eligibility?.allowed_residence_countries?.length
  ) {
    const fb = splitCountriesAndRegions(eligibility.allowed_residence_countries);
    allowedCodes = fb.codes;
    allowedRegions = fb.regions;
  }

  let excludedCodes = [...(eligibility?.excluded_country_codes || [])];
  let excludedRegions = [...(eligibility?.excluded_regions || [])];
  if (
    excludedCodes.length === 0 &&
    excludedRegions.length === 0 &&
    eligibility?.excluded_residence_countries?.length
  ) {
    const fb = splitCountriesAndRegions(eligibility.excluded_residence_countries);
    excludedCodes = fb.codes;
    excludedRegions = fb.regions;
  }

  return { allowedCodes, allowedRegions, excludedCodes, excludedRegions };
}

/**
 * Returns a concise objective scope label independent of applicant country:
 * e.g. 'Worldwide', 'US only', 'Germany and EU', 'Lagos, Nigeria', 'Eligibility unverified'.
 * Never returns 'Worldwide' unless global_remote_explicit is true.
 */
export function buildObjectiveScopeLabel(
  eligibility?: JobEligibility | null,
  workModel?: string | null,
  location?: string | null
): string | null {
  const workArrangement = normalizeWorkArrangement(workModel);
  const { allowedCodes, allowedRegions, excludedCodes, excludedRegions } =
    getNormalizedRestrictionLists(eligibility);
  const physCode = inferPhysicalCountryCode(eligibility, location);
  const physName =
    eligibility?.physical_location_country ||
    (physCode ? getCountryByCode(physCode)?.name || null : null);

  if (
    eligibility?.global_remote_explicit &&
    allowedCodes.length === 0 &&
    allowedRegions.length === 0
  ) {
    if (excludedCodes.length > 0 || excludedRegions.length > 0) {
      const excl =
        excludedCodes.map((c) => shortCountryLabel(c)).join(', ') ||
        excludedRegions.join(', ');
      return `Worldwide (excl. ${excl})`;
    }
    return 'Worldwide';
  }

  if (allowedCodes.length > 0 || allowedRegions.length > 0) {
    return formatAllowedScope(allowedCodes, allowedRegions);
  }

  if (workArrangement === 'onsite' || workArrangement === 'hybrid') {
    const trimmed = (location || '').trim();
    if (trimmed && !GENERIC_NON_CITY_LOCATIONS.has(trimmed.toLowerCase())) {
      return trimmed;
    }
    return physName || 'Eligibility unverified';
  }

  if (workArrangement === 'remote') {
    return 'Eligibility unverified';
  }

  return null;
}

function buildCountryAwareSummaryLabel(params: {
  workArrangement: WorkArrangement;
  status: EligibilityStatus;
  applicantCountryName: string;
  applicantCountryCode: string;
  eligibility?: JobEligibility | null;
  allowedCodes: string[];
  allowedRegions: string[];
  excludedCodes: string[];
  excludedRegions: string[];
  location?: string | null;
  physName?: string | null;
}): string | null {
  const {
    workArrangement,
    status,
    applicantCountryName,
    applicantCountryCode,
    eligibility,
    allowedCodes,
    allowedRegions,
    excludedCodes,
    excludedRegions,
    location,
    physName,
  } = params;

  const workPrefix =
    workArrangement === 'remote'
      ? 'Remote'
      : workArrangement === 'hybrid'
        ? 'Hybrid'
        : workArrangement === 'onsite'
          ? 'Onsite'
          : null;

  if (
    (workArrangement === 'onsite' || workArrangement === 'hybrid') &&
    status === 'eligible'
  ) {
    const place = (location || '').trim();
    if (place && !GENERIC_NON_CITY_LOCATIONS.has(place.toLowerCase())) {
      return `${workPrefix} · ${place}`;
    }
    if (physName) {
      return `${workPrefix} · ${physName}`;
    }
  }

  let scope: string | null = null;
  if (
    eligibility?.global_remote_explicit &&
    allowedCodes.length === 0 &&
    allowedRegions.length === 0
  ) {
    if (excludedCodes.length > 0 || excludedRegions.length > 0) {
      const excl =
        excludedCodes.map((c) => shortCountryLabel(c)).join(', ') ||
        excludedRegions.join(', ');
      scope = `Worldwide (excl. ${excl})`;
    } else {
      scope = 'Worldwide';
    }
  } else if (allowedCodes.length > 0 || allowedRegions.length > 0) {
    if (
      status === 'eligible' &&
      allowedCodes.includes(applicantCountryCode) &&
      allowedCodes.length > 1 &&
      allowedRegions.length === 0
    ) {
      scope = `${applicantCountryName} eligible`;
    } else if (
      status === 'eligible' &&
      allowedCodes.length === 0 &&
      allowedRegions.length > 0
    ) {
      scope = `${applicantCountryName} eligible`;
    } else {
      scope = formatAllowedScope(allowedCodes, allowedRegions);
    }
  } else if (status === 'eligible') {
    scope = `${applicantCountryName} eligible`;
  } else if (workArrangement === 'onsite' || workArrangement === 'hybrid') {
    const place = (location || '').trim() || physName;
    scope = place || 'Eligibility unverified';
  } else {
    scope = 'Eligibility unverified';
  }

  if (workPrefix && scope) {
    return `${workPrefix} · ${scope}`;
  }
  return scope;
}

/**
 * Evaluate job eligibility dynamically for a selectable ISO 3166-1 alpha-2 applicant country.
 * Returns null when no applicant country is selected (never silently assuming Nigeria).
 */
export function evaluateEligibilityForCountry(
  eligibility?: JobEligibility | null,
  applicantCountry?: string | null,
  workModel?: string | null,
  location?: string | null
): ApplicantEligibilityAssessment | null {
  const cc = normalizeCountryCode(applicantCountry);
  if (!cc) return null;

  const entry = getCountryByCode(cc);
  const countryName = entry?.name || cc;
  const workArrangement = normalizeWorkArrangement(workModel);

  // Use precomputed server assessment only when it matches the exact requested country.
  if (
    eligibility?.applicant_assessment &&
    normalizeCountryCode(eligibility.applicant_assessment.applicant_country_code) === cc
  ) {
    return eligibility.applicant_assessment;
  }

  if (!eligibility) {
    const summary =
      workArrangement === 'remote'
        ? 'Remote · Eligibility unverified'
        : (workArrangement === 'onsite' || workArrangement === 'hybrid') && location?.trim()
          ? `${workArrangement === 'onsite' ? 'Onsite' : 'Hybrid'} · ${location.trim()}`
          : null;
    return {
      applicant_country_code: cc,
      applicant_country_name: countryName,
      status: 'unknown',
      reason: null,
      work_arrangement: workArrangement,
      summary_label: summary,
    };
  }

  const { allowedCodes, allowedRegions, excludedCodes, excludedRegions } =
    getNormalizedRestrictionLists(eligibility);

  const physCode = inferPhysicalCountryCode(eligibility, location);
  const physName =
    eligibility.physical_location_country ||
    (physCode ? getCountryByCode(physCode)?.name || null : null);

  const payrollParsed = splitCountriesAndRegions(eligibility.payroll_requirements);
  const workAuthParsed = splitCountriesAndRegions(eligibility.work_authorization_required);
  const citizenshipParsed = splitCountriesAndRegions(eligibility.citizenship_requirements);

  const hybridConfirmed =
    eligibility.hybrid_attendance_confirmed ??
    Boolean(eligibility.facts?.some((f) => f.dimension === 'hybrid_attendance'));

  const foreignPhysical = Boolean(physCode && physCode !== cc);
  const inAllowedCode = allowedCodes.includes(cc);
  const inAllowedRegion = allowedRegions.some((reg) => isCountryInRegion(cc, reg));
  const hasResidenceScope = Boolean(
    eligibility.residence_restriction_confirmed ||
      allowedCodes.length > 0 ||
      allowedRegions.length > 0
  );
  const hasForeignPayroll = Boolean(
    (payrollParsed.codes.length > 0 || payrollParsed.regions.length > 0) &&
      !payrollParsed.codes.includes(cc) &&
      !payrollParsed.regions.some((reg) => isCountryInRegion(cc, reg))
  );

  const makeResult = (
    status: EligibilityStatus,
    reason: string | null
  ): ApplicantEligibilityAssessment => ({
    applicant_country_code: cc,
    applicant_country_name: countryName,
    status,
    reason,
    work_arrangement: workArrangement,
    summary_label: buildCountryAwareSummaryLabel({
      workArrangement,
      status,
      applicantCountryName: countryName,
      applicantCountryCode: cc,
      eligibility,
      allowedCodes,
      allowedRegions,
      excludedCodes,
      excludedRegions,
      location,
      physName,
    }),
  });

  // 1. Explicit country exclusion
  if (excludedCodes.includes(cc)) {
    return makeResult(
      'restricted',
      `Role explicitly excludes applicants residing in ${countryName}.`
    );
  }

  // 2. Explicit regional exclusion
  const matchingExclReg = excludedRegions.find((r) => isCountryInRegion(cc, r));
  if (matchingExclReg) {
    return makeResult(
      'restricted',
      `Role explicitly excludes applicants in ${matchingExclReg}.`
    );
  }

  // 3. Explicit allowed residence scope does not include applicant's country or region
  if (hasResidenceScope && !inAllowedCode && !inAllowedRegion) {
    const scopeNames = eligibility.allowed_residence_countries?.length
      ? eligibility.allowed_residence_countries
      : [
          ...allowedCodes.map((c) => getCountryByCode(c)?.name || c),
          ...allowedRegions,
        ];
    return makeResult(
      'restricted',
      `Applicant residence restricted to ${scopeNames.join(', ')}.`
    );
  }

  // 4. Relocation required to another country
  if (eligibility.relocation_required && foreignPhysical) {
    return makeResult('restricted', `Relocation to ${physName} is required.`);
  }

  // 5. Onsite role in another country
  if (workArrangement === 'onsite' && foreignPhysical && !inAllowedCode) {
    return makeResult(
      'restricted',
      `On-site role in ${physName} requires physical attendance outside ${countryName}.`
    );
  }

  // 6. Confirmed hybrid attendance in another country
  if (
    workArrangement === 'hybrid' &&
    foreignPhysical &&
    hybridConfirmed &&
    !inAllowedCode
  ) {
    return makeResult(
      'restricted',
      `Hybrid role requires in-office attendance in ${physName}.`
    );
  }

  // 7. Incompatible local payroll requirement
  if (hasForeignPayroll) {
    const reqLabels = eligibility.payroll_requirements?.length
      ? eligibility.payroll_requirements
      : payrollParsed.codes.map((c) => getCountryByCode(c)?.name || c);
    return makeResult(
      'restricted',
      `Employment restricted to local ${reqLabels.join(', ')} payroll.`
    );
  }

  // 8. Explicit country residence permission
  if (inAllowedCode) {
    return makeResult('eligible', `Explicitly permits applicants in ${countryName}.`);
  }

  // 9. Local onsite or hybrid role located in applicant's own country
  if ((workArrangement === 'onsite' || workArrangement === 'hybrid') && physCode === cc) {
    if (
      citizenshipParsed.codes.length > 0 &&
      !citizenshipParsed.codes.includes(cc)
    ) {
      return makeResult('unknown', 'Citizenship requirement disclosed for local role.');
    }
    const label = workArrangement === 'onsite' ? 'Onsite' : 'Hybrid';
    return makeResult('eligible', `${label} role located in ${physName || countryName}.`);
  }

  // 10. Explicit pan-regional remote permission (Africa / Sub-Saharan Africa / EU / EEA only)
  if (inAllowedRegion) {
    const matchingUniformRegions = allowedRegions.filter(
      (r) => UNIFORM_CAPABLE_REGIONS.has(r) && isCountryInRegion(cc, r)
    );
    const conflictingNarrowCountry = Boolean(
      (allowedCodes.length > 0 &&
        !inAllowedCode &&
        !eligibility.pan_regional_remote_confirmed) ||
        (workAuthParsed.codes.length > 0 &&
          !workAuthParsed.codes.includes(cc) &&
          eligibility.visa_sponsorship_status === 'not_available')
    );
    if (
      matchingUniformRegions.length > 0 &&
      eligibility.pan_regional_remote_confirmed === true &&
      workArrangement === 'remote' &&
      !conflictingNarrowCountry &&
      !(foreignPhysical && !eligibility.pan_regional_remote_confirmed)
    ) {
      return makeResult(
        'eligible',
        `Explicitly permits remote applicants across ${matchingUniformRegions.join(', ')} (confirm country-specific contract terms).`
      );
    }
    const matchedRegLabels = allowedRegions.filter((r) => isCountryInRegion(cc, r));
    return makeResult(
      'unknown',
      `Scoped to ${matchedRegLabels.join(', ')}; country-level eligibility for ${countryName} is unconfirmed.`
    );
  }

  // 11. Explicit worldwide remote
  if (eligibility.global_remote_explicit) {
    return makeResult('eligible', 'Explicitly open worldwide / work from anywhere.');
  }

  // 12. Work authorization / sponsorship / citizenship / clearance disclosures
  if (
    eligibility.work_authorization_required?.length &&
    eligibility.visa_sponsorship_status === 'not_available'
  ) {
    return makeResult(
      'unknown',
      `Discloses ${eligibility.work_authorization_required.join(', ')} work authorization / no sponsorship without confirmed residence or physical attendance restriction.`
    );
  }

  if (eligibility.work_authorization_required?.length) {
    return makeResult(
      'unknown',
      `Discloses ${eligibility.work_authorization_required.join(', ')} work authorization without confirmed residence or physical attendance restriction.`
    );
  }

  if (eligibility.visa_sponsorship_status === 'not_available') {
    return makeResult(
      'unknown',
      'Visa sponsorship unavailable; geographic residence eligibility undisclosed.'
    );
  }

  if (
    eligibility.citizenship_requirements?.length ||
    eligibility.security_clearance_required
  ) {
    return makeResult(
      'unknown',
      'Citizenship or security clearance requirement disclosed without residence ban.'
    );
  }

  if (workArrangement === 'hybrid' && foreignPhysical) {
    return makeResult(
      'unknown',
      `Hybrid role in ${physName}; physical attendance frequency undisclosed.`
    );
  }

  return makeResult('unknown', null);
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
