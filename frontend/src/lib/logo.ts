const SAFE_DOMAIN_RE =
  /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;

export function isSafeHttpsLogoUrl(url?: string | null): url is string {
  if (!url) return false;
  const trimmed = url.trim();
  if (!trimmed.startsWith('https://')) return false;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function isValidPublishableLogoDevToken(token?: string | null): token is string {
  if (!token || typeof token !== 'string') return false;
  const trimmed = token.trim();
  if (trimmed.length < 6 || /\s/.test(trimmed)) return false;
  // Secret keys (`sk_`) are strictly forbidden in frontend runtime/config.
  return trimmed.startsWith('pk_');
}

export function isSafeCompanyDomain(domain?: string | null): domain is string {
  if (!domain || typeof domain !== 'string') return false;
  const normalized = domain.trim().toLowerCase().replace(/\.$/, '');
  return SAFE_DOMAIN_RE.test(normalized);
}

export function getConfiguredLogoDevToken(overrideToken?: string | null): string | null {
  if (overrideToken !== undefined && overrideToken !== null && overrideToken !== '') {
    return isValidPublishableLogoDevToken(overrideToken) ? overrideToken.trim() : null;
  }
  const viteToken =
    typeof import.meta !== 'undefined' && import.meta.env
      ? (import.meta.env.VITE_LOGO_DEV_TOKEN as string | undefined)
      : undefined;
  if (isValidPublishableLogoDevToken(viteToken)) {
    return viteToken.trim();
  }
  const globalToken = (globalThis as { __BOTTOM_POT_LOGO_DEV_TOKEN__?: unknown })
    .__BOTTOM_POT_LOGO_DEV_TOKEN__;
  if (typeof globalToken === 'string' && isValidPublishableLogoDevToken(globalToken)) {
    return globalToken.trim();
  }
  return null;
}

export function buildLogoDevUrl(
  companyDomain?: string | null,
  overrideToken?: string | null,
  sizePx = 128
): string | null {
  if (!isSafeCompanyDomain(companyDomain)) return null;
  const token = getConfiguredLogoDevToken(overrideToken);
  if (!token) return null;
  const cleanDomain = companyDomain.trim().toLowerCase().replace(/\.$/, '');
  const clampedSize = Math.min(800, Math.max(32, Math.round(sizePx)));
  return `https://img.logo.dev/${encodeURIComponent(cleanDomain)}?token=${encodeURIComponent(
    token
  )}&size=${clampedSize}&format=png&fallback=404`;
}
