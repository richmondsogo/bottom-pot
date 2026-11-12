import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CompanyMark } from '../../components/CompanyMark';
import { normalizeJob } from '../normalize';
import type { JobListing } from '../../types';

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

describe('Step 35: CompanyMark & Company Logo Rendering', () => {
  it('renders square bordered img for safe HTTPS logo URLs (PNG/SVG/WebP)', () => {
    const html = renderToStaticMarkup(
      <CompanyMark
        company="Q-Tech"
        logoUrl="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/logo.svg"
        size="md"
      />
    );
    expect(html).toContain('<img');
    expect(html).toContain('src="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/logo.svg"');
    expect(html).toContain('object-contain');
    expect(html).toContain('rounded-none');
    expect(html).toContain('size-7');
    expect(html).not.toContain('QT');
  });

  it('falls back to initials monogram when logoUrl is null, empty, or unsafe protocol', () => {
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
      expect(html).toContain('SP');
      expect(html).toContain('size-9');
      expect(html).toContain('rounded-none');
    }
  });

  it('preserves company_logo_url cleanly through normalizeJob', () => {
    const withLogo = normalizeJob(makeJob());
    expect(withLogo.company_logo_url).toContain('images.teamtailor-cdn.com');

    const withoutLogo = normalizeJob(makeJob({ provider: 'workday', company_logo_url: null }));
    expect(withoutLogo.company_logo_url).toBeNull();
  });
});
