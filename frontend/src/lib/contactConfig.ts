const BASIC_EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const DEFAULT_CONTACT_EMAIL = 'richmondsogo@gmail.com';

export function isValidContactEmail(raw?: string | null): boolean {
  if (!raw || typeof raw !== 'string') return false;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 254) return false;
  return BASIC_EMAIL_RE.test(trimmed);
}

export function getConfiguredContactEmail(override?: string | null): string | null {
  if (override !== undefined) {
    return isValidContactEmail(override) ? override!.trim() : null;
  }

  const envEmail =
    typeof import.meta !== 'undefined' && import.meta.env
      ? (import.meta.env.VITE_CONTACT_EMAIL as string | undefined)
      : undefined;
  if (typeof envEmail === 'string' && envEmail.trim().length > 0) {
    return isValidContactEmail(envEmail) ? envEmail.trim() : null;
  }

  const globalEmail = (globalThis as { __BOTTOM_POT_CONTACT_EMAIL__?: unknown })
    .__BOTTOM_POT_CONTACT_EMAIL__;
  if (typeof globalEmail === 'string' && globalEmail.trim().length > 0) {
    return isValidContactEmail(globalEmail) ? globalEmail.trim() : null;
  }

  return DEFAULT_CONTACT_EMAIL;
}
