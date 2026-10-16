// LocalStorage and display utilities

export function readStorage<T>(key: string, defaultValue: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return defaultValue;
    return JSON.parse(raw) as T;
  } catch {
    return defaultValue;
  }
}

export function writeStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore quota errors
  }
}

// Deterministic company initials and avatar styling
export function getCompanyInitials(name: string): string {
  if (!name || name === 'Unknown') return '?';
  const clean = name.replace(/[^a-zA-Z0-9\s]/g, '').trim();
  const words = clean.split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase();
}

export function getCompanyAvatarColor(name: string): { backgroundColor: string; color: string; borderColor: string } {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return {
    backgroundColor: `hsl(${hue}, 40%, 88%)`,
    color: `hsl(${hue}, 60%, 20%)`,
    borderColor: `hsl(${hue}, 35%, 78%)`,
  };
}
