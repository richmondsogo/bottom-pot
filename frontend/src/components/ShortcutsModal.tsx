import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      modalRef.current?.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const shortcuts = [
    { key: 'j / ↓', desc: 'Move selection to next posting' },
    { key: 'k / ↑', desc: 'Move selection to previous posting' },
    { key: 'Enter / o', desc: 'Open detail sheet for selected posting' },
    { key: 'Esc', desc: 'Close detail sheet or shortcuts modal' },
    { key: '/', desc: 'Focus keyword filter input' },
    { key: '?', desc: 'Toggle keyboard shortcuts help' },
  ];

  return (
    <div
      className="detail-sheet-backdrop"
      style={{ alignItems: 'center', justifyContent: 'center', padding: 'var(--space-4)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        ref={modalRef}
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border-strong)',
          maxWidth: '440px',
          width: '100%',
          padding: 'var(--space-6)',
          boxShadow: '0 8px 32px rgba(24, 24, 22, 0.12)',
        }}
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
          <h2 id="shortcuts-title" style={{ fontSize: 'var(--text-h3)', fontWeight: 700 }}>
            Keyboard Shortcuts
          </h2>
          <button
            type="button"
            className="btn btn-sm"
            onClick={onClose}
            aria-label="Close shortcuts modal"
            style={{ width: '28px', height: '28px', padding: 0 }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {shortcuts.map(({ key, desc }) => (
            <div
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: 'var(--space-2)',
                borderBottom: '1px solid var(--border-subtle)',
                fontSize: 'var(--text-ui)',
              }}
            >
              <span style={{ color: 'var(--ink)' }}>{desc}</span>
              <kbd
                className="mono"
                style={{
                  background: 'var(--surface-subtle)',
                  border: '1px solid var(--border)',
                  padding: '2px 8px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--accent)',
                }}
              >
                {key}
              </kbd>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 'var(--space-5)', textAlign: 'right' }}>
          <button type="button" className="btn btn-sm" onClick={onClose}>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
