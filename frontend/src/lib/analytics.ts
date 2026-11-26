import { isMockModeActive } from './mock';

export interface AnalyticsCheckContext {
  isProd?: boolean;
  isMock?: boolean;
  isWebdriver?: boolean;
  pathname?: string;
}

export function shouldEnableVercelAnalytics(ctx?: AnalyticsCheckContext): boolean {
  const isProd =
    ctx?.isProd !== undefined
      ? ctx.isProd
      : typeof import.meta !== 'undefined' && Boolean(import.meta.env?.PROD);
  if (!isProd) return false;

  const mockActive = ctx?.isMock !== undefined ? ctx.isMock : isMockModeActive();
  if (mockActive) return false;

  const isWebdriver =
    ctx?.isWebdriver !== undefined
      ? ctx.isWebdriver
      : typeof navigator !== 'undefined' && Boolean(navigator.webdriver);
  if (isWebdriver) return false;

  if (ctx?.pathname === undefined && typeof window === 'undefined') {
    return false;
  }

  const pathname = ctx?.pathname !== undefined ? ctx.pathname : window.location.pathname;
  const cleanPath = (pathname || '/').replace(/\/+$/, '') || '/';
  if (cleanPath === '/admin') return false;

  return true;
}
