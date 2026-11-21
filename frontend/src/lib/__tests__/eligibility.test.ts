import { describe, it, expect } from 'vitest';
import {
  buildCombinedWorkEligibilityLabel,
  buildObjectiveScopeLabel,
  evaluateEligibilityForCountry,
  formatApplicantStatusLabel,
} from '../eligibility';
import type { JobEligibility } from '../../types';

const REPRESENTATIVE_COUNTRIES = [
  'NG', 'GH', 'KE', 'ZA', 'EG', 'GB', 'DE', 'US', 'CA', 'IN', 'SG', 'AU',
];

describe('global applicant eligibility evaluation', () => {
  it('returns null when applicant country is unset and never assumes Nigeria', () => {
    const elig: JobEligibility = {
      classification: 'worldwide',
      global_remote_explicit: true,
      nigeria_eligible: true,
    };
    expect(evaluateEligibilityForCountry(elig, '', 'remote', 'Remote - Worldwide')).toBeNull();
    expect(evaluateEligibilityForCountry(elig, null, 'remote', 'Remote - Worldwide')).toBeNull();
    expect(evaluateEligibilityForCountry(elig, undefined, 'remote', 'Remote - Worldwide')).toBeNull();
  });

  it('evaluates explicit worldwide remote as eligible across all 12 representative countries', () => {
    const elig: JobEligibility = {
      classification: 'worldwide',
      global_remote_explicit: true,
    };
    for (const code of REPRESENTATIVE_COUNTRIES) {
      const res = evaluateEligibilityForCountry(elig, code, 'remote', 'Remote - Worldwide');
      expect(res?.status).toBe('eligible');
      expect(res?.summary_label).toBe('Remote · Worldwide');
    }
  });

  it('never labels generic remote or undisclosed geo as worldwide', () => {
    const elig: JobEligibility = {
      classification: 'unknown',
      global_remote_explicit: false,
    };
    expect(buildObjectiveScopeLabel(elig, 'remote', 'Remote')).toBe('Eligibility unverified');
    for (const code of REPRESENTATIVE_COUNTRIES) {
      const res = evaluateEligibilityForCountry(elig, code, 'remote', 'Remote');
      expect(res?.status).toBe('unknown');
      expect(res?.summary_label).toBe('Remote · Eligibility unverified');
      expect(res?.summary_label?.toLowerCase()).not.toContain('worldwide');
    }
  });

  it('evaluates US-only remote accurately without mislabeling worldwide', () => {
    const elig: JobEligibility = {
      classification: 'country_restricted',
      allowed_residence_countries: ['United States'],
      allowed_country_codes: ['US'],
      residence_restriction_confirmed: true,
      global_remote_explicit: false,
    };
    expect(buildObjectiveScopeLabel(elig, 'remote', 'Remote (US)')).toBe('US only');

    const usRes = evaluateEligibilityForCountry(elig, 'US', 'remote', 'Remote (US)');
    expect(usRes?.status).toBe('eligible');
    expect(usRes?.summary_label).toBe('Remote · US only');

    for (const other of REPRESENTATIVE_COUNTRIES.filter((c) => c !== 'US')) {
      const res = evaluateEligibilityForCountry(elig, other, 'remote', 'Remote (US)');
      expect(res?.status).toBe('restricted');
      expect(res?.summary_label).toBe('Remote · US only');
    }
  });

  it('handles Germany and EU remote vs bare EMEA region conservatively', () => {
    const deEu: JobEligibility = {
      classification: 'region_restricted',
      allowed_residence_countries: ['Germany', 'EU'],
      allowed_country_codes: ['DE'],
      allowed_regions: ['EU'],
      pan_regional_remote_confirmed: true,
      residence_restriction_confirmed: true,
    };
    expect(buildObjectiveScopeLabel(deEu, 'remote', 'Remote')).toBe('Germany and EU');
    expect(evaluateEligibilityForCountry(deEu, 'DE', 'remote')?.status).toBe('eligible');
    expect(evaluateEligibilityForCountry(deEu, 'FR', 'remote')?.status).toBe('eligible');
    for (const nonEu of ['NG', 'GB', 'US', 'CA', 'IN', 'SG', 'AU', 'EG']) {
      expect(evaluateEligibilityForCountry(deEu, nonEu, 'remote')?.status).toBe('restricted');
    }

    const emeaBare: JobEligibility = {
      classification: 'region_restricted',
      allowed_residence_countries: ['EMEA'],
      allowed_regions: ['EMEA'],
      residence_restriction_confirmed: true,
    };
    for (const member of ['NG', 'DE', 'GB', 'EG']) {
      expect(evaluateEligibilityForCountry(emeaBare, member, 'remote')?.status).toBe('unknown');
    }
    for (const nonMember of ['US', 'CA', 'IN', 'SG', 'AU']) {
      expect(evaluateEligibilityForCountry(emeaBare, nonMember, 'remote')?.status).toBe('restricted');
    }
  });

  it('distinguishes Egypt-only African roles, Nigeria & Kenya hubs, and Lagos onsite vs Berlin onsite', () => {
    const egyptOnly: JobEligibility = {
      classification: 'country_restricted',
      allowed_country_codes: ['EG'],
      residence_restriction_confirmed: true,
    };
    expect(evaluateEligibilityForCountry(egyptOnly, 'EG', 'remote')?.status).toBe('eligible');
    expect(evaluateEligibilityForCountry(egyptOnly, 'NG', 'remote')?.status).toBe('restricted');

    const lagosOnsite: JobEligibility = {
      classification: 'onsite_or_hybrid_local',
      physical_location_country: 'Nigeria',
      physical_location_country_code: 'NG',
    };
    const ngOnsite = evaluateEligibilityForCountry(lagosOnsite, 'NG', 'in_person', 'Lagos, Nigeria');
    expect(ngOnsite?.status).toBe('eligible');
    expect(ngOnsite?.summary_label).toBe('Onsite · Lagos, Nigeria');
    expect(evaluateEligibilityForCountry(lagosOnsite, 'KE', 'in_person', 'Lagos, Nigeria')?.status).toBe('restricted');

    const berlinOnsite: JobEligibility = {
      classification: 'onsite_or_hybrid_local',
      physical_location_country: 'Germany',
      physical_location_country_code: 'DE',
    };
    expect(evaluateEligibilityForCountry(berlinOnsite, 'DE', 'in_person', 'Berlin, Germany')?.status).toBe('eligible');
    expect(evaluateEligibilityForCountry(berlinOnsite, 'NG', 'in_person', 'Berlin, Germany')?.status).toBe('restricted');
  });

  it('handles worldwide exclusion and formats separated work/eligibility labels cleanly', () => {
    const exclUs: JobEligibility = {
      classification: 'worldwide',
      global_remote_explicit: true,
      excluded_country_codes: ['US', 'CA'],
    };
    expect(evaluateEligibilityForCountry(exclUs, 'US', 'remote')?.status).toBe('restricted');
    expect(evaluateEligibilityForCountry(exclUs, 'NG', 'remote')?.status).toBe('eligible');
    expect(buildObjectiveScopeLabel(exclUs, 'remote')).toBe('Worldwide (excl. US, Canada)');
    expect(formatApplicantStatusLabel('eligible', 'Ghana')).toBe('Eligible from Ghana');
    expect(formatApplicantStatusLabel('restricted', 'United States')).toBe('Not eligible from United States');
    expect(formatApplicantStatusLabel('unknown', 'India')).toBe('Eligibility unverified for India');
    expect(
      buildCombinedWorkEligibilityLabel('remote', 'Nigeria eligible', null)
    ).toBe('Remote · Nigeria eligible');
  });

  it('recognizes AMER and NAMER macro-region aliases conservatively on frontend parity helpers', () => {
    const amerElig: JobEligibility = {
      classification: 'region_restricted',
      allowed_residence_countries: ['Americas'],
      allowed_regions: ['Americas'],
      residence_restriction_confirmed: true,
      global_remote_explicit: false,
    };
    expect(buildObjectiveScopeLabel(amerElig, 'remote', 'Remote, AMER')).toBe('Americas only');
    expect(evaluateEligibilityForCountry(amerElig, 'NG', 'remote')?.status).toBe('restricted');
    expect(evaluateEligibilityForCountry(amerElig, 'DE', 'remote')?.status).toBe('restricted');
    expect(evaluateEligibilityForCountry(amerElig, 'US', 'remote')?.status).toBe('unknown');
  });

  it('resolves bare major city London and Hybrid - prefixed locations with backend parity', () => {
    const londonElig: JobEligibility = {
      classification: 'onsite_or_hybrid_local',
    };
    const gbRes = evaluateEligibilityForCountry(londonElig, 'GB', 'hybrid', 'London');
    expect(gbRes?.status).toBe('eligible');
    expect(gbRes?.summary_label).toBe('Hybrid · London');
    expect(evaluateEligibilityForCountry(londonElig, 'NG', 'hybrid', 'London')?.status).toBe('unknown');

    const sgElig: JobEligibility = {
      classification: 'onsite_or_hybrid_local',
      hybrid_attendance_confirmed: true,
    };
    const sgRes = evaluateEligibilityForCountry(sgElig, 'SG', 'hybrid', 'Hybrid - Singapore');
    expect(sgRes?.status).toBe('eligible');
    expect(sgRes?.summary_label).toBe('Hybrid · Hybrid - Singapore');
    expect(
      evaluateEligibilityForCountry(sgElig, 'NG', 'hybrid', 'Hybrid - Singapore')?.status
    ).toBe('restricted');
  });
});
