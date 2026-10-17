import React from 'react';
import type { SearchParams } from '../types';
import { Edit2, RotateCcw } from 'lucide-react';

interface SearchSummaryBarProps {
  searchParams: SearchParams;
  onEditSearch: () => void;
  onNewSearch: () => void;
  platformCount?: number;
}

export const SearchSummaryBar: React.FC<SearchSummaryBarProps> = ({
  searchParams,
  onEditSearch,
  onNewSearch,
  platformCount = 18,
}) => {
  const parts: string[] = [];
  if (searchParams.keywords) parts.push(searchParams.keywords);
  if (searchParams.location) parts.push(searchParams.location);
  if (searchParams.workModel === 'remote') parts.push('Remote only');
  else if (searchParams.workModel === 'onsite') parts.push('Exclude remote');
  parts.push(`Last ${searchParams.postAge} days`);
  if (platformCount) parts.push(`${platformCount} platforms`);

  return (
    <div className="search-summary-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        <span style={{ fontWeight: 700, color: 'var(--ink)' }}>Search:</span>
        <span style={{ color: 'var(--ink)' }}>{parts.join(' · ')}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexShrink: 0 }}>
        <button
          type="button"
          className="btn btn-sm"
          onClick={onEditSearch}
          style={{ height: '28px', fontSize: '11px' }}
        >
          <Edit2 size={12} aria-hidden="true" />
          <span>Edit search</span>
        </button>
        <button
          type="button"
          className="btn btn-sm"
          onClick={onNewSearch}
          style={{ height: '28px', fontSize: '11px' }}
        >
          <RotateCcw size={12} aria-hidden="true" />
          <span>New search</span>
        </button>
      </div>
    </div>
  );
};
