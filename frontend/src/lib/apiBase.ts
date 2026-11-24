/**
 * Configurable backend API base URL helper.
 *
 * Defaults to "" (same-origin) for unified local server, Vite proxy dev, and Playwright E2E.
 * Set VITE_API_BASE_URL (e.g. https://api.bottompot.example) when deploying frontend/ on Vercel
 * separately from the persistent FastAPI backend container.
 */

export function getApiBaseUrl(): string {
  const raw =
    typeof import.meta !== 'undefined' && import.meta.env
      ? (import.meta.env.VITE_API_BASE_URL as string | undefined)
      : undefined;
  return (raw || '').trim().replace(/\/+$/, '');
}

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const base = getApiBaseUrl();
  return base ? `${base}${normalizedPath}` : normalizedPath;
}

export function apiCredentials(): RequestCredentials {
  return getApiBaseUrl() ? 'include' : 'same-origin';
}
