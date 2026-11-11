import { describe, it, expect } from 'vitest';
import { ALL_PLATFORMS } from '../constants';

function buildPlatformsQueryParam(selectedPlatforms: string[]): string | null {
  const queryParams = new URLSearchParams();
  if (selectedPlatforms.length === 0) {
    queryParams.set('platforms', '');
  } else if (selectedPlatforms.length < ALL_PLATFORMS.length) {
    queryParams.set('platforms', selectedPlatforms.join(','));
  }
  return queryParams.get('platforms');
}

describe('empty platform search contract', () => {
  it('transmits explicit empty string when selection is none ([])', () => {
    const param = buildPlatformsQueryParam([]);
    expect(param).toBe('');
  });

  it('transmits comma-separated IDs when custom subset is selected', () => {
    const param = buildPlatformsQueryParam(['greenhouse', 'lever']);
    expect(param).toBe('greenhouse,lever');
  });

  it('omits platforms parameter when all platforms are selected (default)', () => {
    const allIds = ALL_PLATFORMS.map((p) => p.id);
    const param = buildPlatformsQueryParam(allIds);
    expect(param).toBeNull();
  });
});
