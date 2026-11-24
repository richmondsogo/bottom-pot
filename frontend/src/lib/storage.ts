/**
 * LocalStorage wrapper with error handling and quota protection.
 * Restrained square monogram utilities.
 */

export function readStorage<T>(key: string, defaultValue: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return defaultValue;
    return JSON.parse(raw) as T;
  } catch {
    return defaultValue;
  }
}

export function writeStorage<T>(key: string, value: T): boolean {
  try {
    const serialized = JSON.stringify(value);
    localStorage.setItem(key, serialized);
    return true;
  } catch {
    // Gracefully handle QuotaExceededError or security restrictions
    return false;
  }
}

export function removeStorage(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {}
}

/** Extract 1-2 uppercase monogram characters from company name */
export function getCompanyInitials(name: string): string {
  if (!name || name === 'Unknown' || name === '—') return '—';
  const clean = name.replace(/[^a-zA-Z0-9\s]/g, '').trim();
  if (!clean) return '—';
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase();
}

/**
 * Restrained, deterministic neutral color tints for square monogram tiles.
 * Replaces circular pastel rainbow avatars with neutral ink/cream/forest tones.
 */
const MONOGRAM_PALETTES = [
  { bg: 'var(--mono-0-bg)', color: 'var(--mono-0-text)', border: 'var(--mono-0-border)' },
  { bg: 'var(--mono-1-bg)', color: 'var(--mono-1-text)', border: 'var(--mono-1-border)' },
  { bg: 'var(--mono-2-bg)', color: 'var(--mono-2-text)', border: 'var(--mono-2-border)' },
  { bg: 'var(--mono-3-bg)', color: 'var(--mono-3-text)', border: 'var(--mono-3-border)' },
  { bg: 'var(--mono-4-bg)', color: 'var(--mono-4-text)', border: 'var(--mono-4-border)' },
  { bg: 'var(--mono-5-bg)', color: 'var(--mono-5-text)', border: 'var(--mono-5-border)' },
  { bg: 'var(--mono-6-bg)', color: 'var(--mono-6-text)', border: 'var(--mono-6-border)' },
];

export function getCompanyTileColor(name: string): { bg: string; color: string; border: string } {
  if (!name) return MONOGRAM_PALETTES[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % MONOGRAM_PALETTES.length;
  return MONOGRAM_PALETTES[index];
}
