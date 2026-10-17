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
  { bg: '#F3EFE8', color: '#181816', border: '#DCD6CA' },
  { bg: '#EAE5DB', color: '#181816', border: '#D4CEBF' },
  { bg: '#EBF2ED', color: '#1A382B', border: '#CCD9CE' },
  { bg: '#E3ECE6', color: '#1A382B', border: '#C0D2C6' },
  { bg: '#EFEFEA', color: '#2B2D2B', border: '#D5D5CF' },
  { bg: '#F5F2EB', color: '#3A3832', border: '#DDD8CB' },
  { bg: '#E8E7DF', color: '#252420', border: '#CECCC2' },
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
