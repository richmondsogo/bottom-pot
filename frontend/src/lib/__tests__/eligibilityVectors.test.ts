import { describe, it, expect } from 'vitest';
import {
  buildObjectiveScopeLabel,
  evaluateEligibilityForCountry,
} from '../eligibility';
import type { JobEligibility } from '../../types';
import vectorBundle from '../../../../tests/vectors/eligibility.json';

interface VectorSpec {
  id: string;
  description: string;
  work_model?: string | null;
  location?: string | null;
  eligibility: JobEligibility;
  expected_objective_scope_label: string | null;
  expected_assessments: Record<string, { status: string; summary_contains?: string }>;
}

const VECTORS: VectorSpec[] = vectorBundle.vectors as unknown as VectorSpec[];

describe('shared cross-language eligibility vectors', () => {
  it('loads all shared eligibility vectors', () => {
    expect(VECTORS.length).toBeGreaterThanOrEqual(12);
  });

  it('matches every vector via legacy fallback when backend labels are absent', () => {
    for (const vec of VECTORS) {
      const scope = buildObjectiveScopeLabel(vec.eligibility, vec.work_model, vec.location);
      expect(scope, `${vec.id} objective scope`).toBe(vec.expected_objective_scope_label);

      for (const [countryCode, expected] of Object.entries(vec.expected_assessments)) {
        const res = evaluateEligibilityForCountry(
          vec.eligibility,
          countryCode,
          vec.work_model,
          vec.location
        );
        expect(res?.status, `${vec.id} [${countryCode}] status`).toBe(expected.status);
        if (expected.summary_contains) {
          expect(res?.summary_label ?? '', `${vec.id} [${countryCode}] summary`).toContain(
            expected.summary_contains
          );
        }
      }
    }
  });

  it('prefers authoritative backend objective_scope_label and matching applicant_assessment', () => {
    const sample = VECTORS[0];
    const authoritativeElig: JobEligibility = {
      ...sample.eligibility,
      objective_scope_label: 'Server Authorized Scope',
      applicant_assessment: {
        applicant_country_code: 'NG',
        applicant_country_name: 'Nigeria',
        status: 'eligible',
        reason: 'Evaluated on backend.',
        work_arrangement: 'hybrid',
        summary_label: 'Hybrid · Server Authorized Nigeria',
      },
    };

    expect(buildObjectiveScopeLabel(authoritativeElig, sample.work_model, sample.location)).toBe(
      'Server Authorized Scope'
    );
    const ng = evaluateEligibilityForCountry(authoritativeElig, 'ng', sample.work_model, sample.location);
    expect(ng?.summary_label).toBe('Hybrid · Server Authorized Nigeria');

    // Mismatched country falls back rather than reusing another country's cached assessment
    const us = evaluateEligibilityForCountry(authoritativeElig, 'US', sample.work_model, sample.location);
    expect(us?.applicant_country_code).toBe('US');
    expect(us?.status).toBe('restricted');
  });
});
