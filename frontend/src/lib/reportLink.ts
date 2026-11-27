import type { NormalizedJob } from '../types';
import { getConfiguredContactEmail } from './contactConfig';

export function isSafeReportTargetUrl(rawUrl?: string | null): boolean {
  if (!rawUrl || typeof rawUrl !== 'string') return false;
  const trimmed = rawUrl.trim();
  if (!trimmed) return false;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === 'https:') {
      return Boolean(parsed.hostname);
    }
    if (parsed.protocol === 'mailto:') {
      const address = (parsed.pathname || '').trim();
      return address.includes('@') && !address.startsWith('@') && !address.endsWith('@');
    }
    return false;
  } catch {
    return false;
  }
}

export function getConfiguredReportProblemUrl(overrideUrl?: string | null): string | null {
  if (overrideUrl !== undefined && overrideUrl !== null && overrideUrl !== '') {
    return isSafeReportTargetUrl(overrideUrl) ? overrideUrl.trim() : null;
  }
  const viteUrl =
    typeof import.meta !== 'undefined' && import.meta.env
      ? (import.meta.env.VITE_REPORT_PROBLEM_URL as string | undefined)
      : undefined;
  if (typeof viteUrl === 'string' && viteUrl.trim().length > 0) {
    return isSafeReportTargetUrl(viteUrl) ? viteUrl.trim() : null;
  }
  const globalUrl = (globalThis as { __BOTTOM_POT_REPORT_PROBLEM_URL__?: unknown })
    .__BOTTOM_POT_REPORT_PROBLEM_URL__;
  if (typeof globalUrl === 'string' && globalUrl.trim().length > 0) {
    return isSafeReportTargetUrl(globalUrl) ? globalUrl.trim() : null;
  }
  const email = getConfiguredContactEmail();
  return email ? `mailto:${email}` : null;
}

export function buildReportProblemUrl(
  job: Pick<NormalizedJob, 'id' | 'provider' | 'displayCompany' | 'displayTitle' | 'apply_url'>,
  overrideUrl?: string | null
): string | null {
  const base = getConfiguredReportProblemUrl(overrideUrl);
  if (!base) return null;

  try {
    const parsed = new URL(base);
    if (parsed.protocol === 'https:') {
      parsed.searchParams.set('listing_id', job.id);
      if (job.provider) parsed.searchParams.set('provider', job.provider);
      if (job.displayCompany) parsed.searchParams.set('company', job.displayCompany);
      if (job.displayTitle) parsed.searchParams.set('title', job.displayTitle);
      if (job.apply_url) parsed.searchParams.set('apply_url', job.apply_url);
      return parsed.toString();
    }
    if (parsed.protocol === 'mailto:') {
      const subject = `Listing issue: ${job.displayCompany} - ${job.displayTitle}`.slice(0, 160);
      const bodyLines = [
        `Listing ID: ${job.id}`,
        `Provider: ${job.provider}`,
        `Company: ${job.displayCompany}`,
        `Role: ${job.displayTitle}`,
        ...(job.apply_url ? [`Apply URL: ${job.apply_url}`] : []),
        '',
        'What looks wrong with this listing:',
        '',
      ];
      parsed.searchParams.set('subject', subject);
      parsed.searchParams.set('body', bodyLines.join('\n'));
      return parsed.toString();
    }
    return null;
  } catch {
    return null;
  }
}
