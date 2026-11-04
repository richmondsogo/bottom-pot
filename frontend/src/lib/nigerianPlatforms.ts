import { NIGERIAN_PLATFORM_IDS } from './constants';

export function areAllNigerianSelected(platforms: string[]): boolean {
  return NIGERIAN_PLATFORM_IDS.every((id) => platforms.includes(id));
}

export function hasAnyNigerianSelected(platforms: string[]): boolean {
  return platforms.some((id) => (NIGERIAN_PLATFORM_IDS as readonly string[]).includes(id));
}

export function toggleNigerianPlatforms(platforms: string[], selectAll: boolean): string[] {
  if (selectAll) {
    const missing = NIGERIAN_PLATFORM_IDS.filter((id) => !platforms.includes(id));
    return [...platforms, ...missing];
  }
  return platforms.filter((id) => !(NIGERIAN_PLATFORM_IDS as readonly string[]).includes(id));
}

export function applyNgToPlatforms(currentPlatforms: string[], ng: string | null): string[] {
  if (ng === null) {
    // ng absent: leaves the saved selection untouched
    return currentPlatforms;
  }
  if (ng === '0') {
    // ng=0: removes the Nigerian chips
    return currentPlatforms.filter((id) => !(NIGERIAN_PLATFORM_IDS as readonly string[]).includes(id));
  }
  if (ng === '1') {
    // ng=1: adds all three only if none is selected
    const hasAny = currentPlatforms.some((id) => (NIGERIAN_PLATFORM_IDS as readonly string[]).includes(id));
    if (!hasAny) {
      return [...currentPlatforms, ...NIGERIAN_PLATFORM_IDS];
    }
    return currentPlatforms;
  }
  return currentPlatforms;
}
