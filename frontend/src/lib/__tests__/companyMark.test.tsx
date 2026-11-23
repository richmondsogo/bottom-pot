import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CompanyMark } from '../../components/CompanyMark';
import { normalizeJob } from '../normalize';
import {
  buildLogoDevUrl,
  isSafeCompanyDomain,
  isValidPublishableLogoDevToken,
} from '../logo';
import type { JobListing } from '../../types';

const TEST_PK_TOKEN = ['pk', 'vitest', 'sample'].join('_');
const TEST_SK_TOKEN = ['sk', 'vitest', 'forbidden'].join('_');

function makeJob(overrides: Partial<JobListing> = {}): JobListing {
  return {
    id: 'teamtailor:qtech:8029561',
    title: 'Java Developer',
    company: 'Q-Tech',
    company_slug: 'qtech',
    company_logo_url: 'https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/image_uploads/logo.png',
    location: 'Barcelona',
    work_model: 'hybrid',
    employment_type: 'full_time',
    apply_url: 'https://qtech.teamtailor.com/jobs/8029561-java-developer',
    source_url: 'https://qtech.teamtailor.com/jobs/8029561-java-developer',
    provider: 'teamtailor',
    data_source: 'scrape',
    ...overrides,
  };
}

describe('Step 35 & Phase 6: CompanyMark & Logo.dev Fallback Chain', () => {
  it('renders square bordered img with alt, dimensions, lazy loading, and api source for safe HTTPS logo URLs', () => {
    const html = renderToStaticMarkup(
      <CompanyMark
        company="Q-Tech"
        logoUrl="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/logo.svg"
        companyDomain="qtech.example"
        logoDevToken={TEST_PK_TOKEN}
        size="md"
      />
    );
    expect(html).toContain('<img');
    expect(html).toContain('data-logo-source="api"');
    expect(html).toContain('alt="Q-Tech"');
    expect(html).toContain('width="28"');
    expect(html).toContain('height="28"');
    expect(html).toContain('loading="lazy"');
    expect(html).toContain('src="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/logo.svg"');
    expect(html).toContain('object-contain');
    expect(html).toContain('rounded-none');
    expect(html).toContain('size-7');
    expect(html).not.toContain('img.logo.dev');
    expect(html).not.toContain('QT');
  });

  it('uses Logo.dev with fallback=404 when API logo is missing and a verified domain + pk_ token exist', () => {
    const html = renderToStaticMarkup(
      <CompanyMark
        company="Supabase"
        logoUrl={null}
        companyDomain="supabase.com"
        logoDevToken={TEST_PK_TOKEN}
        size="lg"
      />
    );
    expect(html).toContain('<img');
    expect(html).toContain('data-logo-source="logo_dev"');
    expect(html).toContain(`https://img.logo.dev/supabase.com?token=${TEST_PK_TOKEN}&amp;size=128&amp;format=png&amp;fallback=404`);
    expect(html).toContain('alt="Supabase"');
    expect(html).toContain('width="36"');
    expect(html).toContain('height="36"');
    expect(html).toContain('rounded-none');
    expect(html).toContain('size-9');
  });

  it('falls back to initials monogram when logoUrl is null/unsafe or token/domain invalid', () => {
    for (const unsafeUrl of [
      null,
      undefined,
      '',
      'http://images.teamtailor-cdn.com/logo.png',
      'javascript:alert(1)',
      'data:image/svg+xml,<svg/>',
    ]) {
      const html = renderToStaticMarkup(
        <CompanyMark company="Stripe Payments" logoUrl={unsafeUrl} size="lg" />
      );
      expect(html).not.toContain('<img');
      expect(html).toContain('data-logo-source="monogram"');
      expect(html).toContain('SP');
      expect(html).toContain('size-9');
      expect(html).toContain('rounded-none');
    }

    // Secret sk_ keys or unsafe domains are rejected and stay on monogram
    expect(isValidPublishableLogoDevToken(TEST_SK_TOKEN)).toBe(false);
    expect(isValidPublishableLogoDevToken(TEST_PK_TOKEN)).toBe(true);
    expect(isSafeCompanyDomain('supabase.com')).toBe(true);
    expect(isSafeCompanyDomain('https://supabase.com')).toBe(false);
    expect(buildLogoDevUrl('supabase.com', TEST_SK_TOKEN)).toBeNull();
    const skHtml = renderToStaticMarkup(
      <CompanyMark company="Supabase" logoUrl={null} companyDomain="supabase.com" logoDevToken={TEST_SK_TOKEN} size="md" />
    );
    expect(skHtml).not.toContain('<img');
    expect(skHtml).toContain('data-logo-source="monogram"');
  });

  it('preserves company_logo_url and company_domain cleanly through normalizeJob', () => {
    const withLogo = normalizeJob(makeJob({ company_domain: 'qtech.io' }));
    expect(withLogo.company_logo_url).toContain('images.teamtailor-cdn.com');
    expect(withLogo.company_domain).toBe('qtech.io');

    const withoutLogo = normalizeJob(makeJob({ provider: 'workday', company_logo_url: null, company_domain: null }));
    expect(withoutLogo.company_logo_url).toBeNull();
    expect(withoutLogo.company_domain).toBeNull();
  });
});
