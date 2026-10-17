import React from 'react';
import { isMockModeActive, getMockModeType } from '../lib/mock';
import { HelpCircle } from 'lucide-react';

interface HeaderProps {
  onOpenShortcuts: () => void;
  onResetSearch?: () => void;
}

// Config constant: rendered only if non-empty string. Unset by default per prompt.
export const FEEDBACK_URL = '';

export const Header: React.FC<HeaderProps> = ({ onOpenShortcuts, onResetSearch }) => {
  const isMock = isMockModeActive();
  const mockType = getMockModeType();

  return (
    <header className="topbar">
      <div className="content-max-width" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <div 
          className="brand-wrap"
          onClick={onResetSearch}
          style={{ cursor: onResetSearch ? 'pointer' : 'default' }}
          role={onResetSearch ? 'button' : undefined}
          tabIndex={onResetSearch ? 0 : undefined}
          onKeyDown={(e) => {
            if (onResetSearch && (e.key === 'Enter' || e.key === ' ')) {
              onResetSearch();
            }
          }}
        >
          <div className="brand-logo" aria-label="Bottom Pot logo">
            BP
          </div>
          <div className="brand-name">
            <span>Bottom Pot</span>
            <span className="brand-tagline">Direct ATS Discovery</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {isMock && (
            <span
              className="mono"
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                background: 'var(--status-warning-bg)',
                color: 'var(--status-warning-text)',
                border: '1px solid var(--border)',
                fontWeight: 600,
              }}
            >
              MOCK MODE ({mockType.toUpperCase()})
            </span>
          )}

          {FEEDBACK_URL && (
            <a
              href={FEEDBACK_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm"
            >
              Feedback
            </a>
          )}

          <button
            type="button"
            className="btn btn-sm"
            onClick={onOpenShortcuts}
            title="Keyboard shortcuts (?)"
            aria-label="Keyboard shortcuts"
            style={{ padding: '0 8px' }}
          >
            <HelpCircle size={15} aria-hidden="true" />
            <span className="mono" style={{ fontSize: '11px' }}>?</span>
          </button>
        </div>
      </div>
    </header>
  );
};
