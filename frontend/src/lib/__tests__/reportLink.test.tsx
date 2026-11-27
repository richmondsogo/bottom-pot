import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  buildReportProblemUrl,
  getConfiguredReportProblemUrl,
  isSafeReportTargetUrl,
} from '../reportLink';
import { normalizeJob } from '../normalize';
import { DetailSheet } from '../../components/DetailSheet';

describe('Report a problem with this listing helper & UI', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    delete (globalThis as { __BOTTOM_POT_REPORT_PROBLEM_URL__?: unknown }).__BOTTOM_POT_REPORT_PROBLEM_URL__;
  });

  const sampleJob = normalizeJob({
    id: 'ashby:supabase:job-1',
    provider: 'ashby',
    data_source: 'api',
    title: 'Support Engineer',
    company: 'Supabase',
    company_slug: 'supabase',
    location: 'Remote',
    work_model: 'remote',
    apply_url: 'https://jobs.ashbyhq.com/supabase/job-1',
    source_url: 'https://jobs.ashbyhq.com/supabase/job-1',
  });

  it('accepts only https:// and mailto: URLs, defaults to contact email mailto:, and rejects unsafe overrides', () => {
    vi.stubEnv('VITE_REPORT_PROBLEM_URL', '');
    vi.stubEnv('VITE_CONTACT_EMAIL', '');
    expect(isSafeReportTargetUrl('https://report.example.test/issue')).toBe(true);
    expect(isSafeReportTargetUrl('mailto:issues@bottompot.example')).toBe(true);
    expect(isSafeReportTargetUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeReportTargetUrl('http://insecure.example/report')).toBe(false);
    expect(isSafeReportTargetUrl('')).toBe(false);

    expect(getConfiguredReportProblemUrl()).toBe('mailto:richmondsogo@gmail.com');

    vi.stubEnv('VITE_REPORT_PROBLEM_URL', 'https://report.example.test/issue');
    expect(getConfiguredReportProblemUrl()).toBe('https://report.example.test/issue');
    expect(getConfiguredReportProblemUrl('javascript:alert(1)')).toBeNull();
    expect(buildReportProblemUrl(sampleJob, 'javascript:alert(1)')).toBeNull();
  });

  it('attaches only listing metadata (zero personal data) to https:// and mailto: URLs', () => {
    const httpsHref = buildReportProblemUrl(
      sampleJob,
      'https://report.example.test/issue?template=listing.yml'
    );
    expect(httpsHref).not.toBeNull();
    const parsed = new URL(httpsHref!);
    expect(parsed.searchParams.get('template')).toBe('listing.yml');
    expect(parsed.searchParams.get('listing_id')).toBe('ashby:supabase:job-1');
    expect(parsed.searchParams.get('provider')).toBe('ashby');
    expect(parsed.searchParams.get('company')).toBe('Supabase');
    expect(parsed.searchParams.get('title')).toBe('Support Engineer');
    expect(parsed.searchParams.get('apply_url')).toBe('https://jobs.ashbyhq.com/supabase/job-1');
    for (const forbidden of ['email', 'country', 'applicant_country', 'query', 'token', 'user']) {
      expect(parsed.searchParams.has(forbidden)).toBe(false);
    }

    const mailHref = buildReportProblemUrl(sampleJob, 'mailto:qa@bottompot.example');
    expect(mailHref).toContain('mailto:qa@bottompot.example');
    expect(mailHref).toContain('subject=');
    expect(mailHref).toContain('ashby%3Asupabase%3Ajob-1');
  });

  it('defaults DetailSheet report link to contact email mailto: with job context and honors configured URL override', () => {
    vi.stubEnv('VITE_REPORT_PROBLEM_URL', '');
    vi.stubEnv('VITE_CONTACT_EMAIL', '');
    const defaultHtml = renderToStaticMarkup(
      <DetailSheet job={sampleJob} onClose={() => {}} onMarkVisited={() => {}} />
    );
    expect(defaultHtml).toContain('data-testid="report-problem-link"');
    expect(defaultHtml).toContain('Report a problem with this listing');
    expect(defaultHtml).toContain('href="mailto:richmondsogo@gmail.com?');
    expect(defaultHtml).toContain('ashby%3Asupabase%3Ajob-1');
    expect(defaultHtml).not.toContain('github.com');

    (globalThis as { __BOTTOM_POT_REPORT_PROBLEM_URL__?: unknown }).__BOTTOM_POT_REPORT_PROBLEM_URL__ =
      'https://report.example.test/issue';
    const configuredHtml = renderToStaticMarkup(
      <DetailSheet job={sampleJob} onClose={() => {}} onMarkVisited={() => {}} />
    );
    expect(configuredHtml).toContain('data-testid="report-problem-link"');
    expect(configuredHtml).toContain('href="https://report.example.test/issue?');
    expect(configuredHtml).toContain('listing_id=ashby%3Asupabase%3Ajob-1');
  });
});
