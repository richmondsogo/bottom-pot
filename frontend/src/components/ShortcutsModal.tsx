import React, { useEffect } from 'react';
import { X, Keyboard } from 'lucide-react';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  const shortcuts = [
    { key: isMac ? '⌘K' : 'Ctrl+K', desc: 'Open command palette' },
    { key: '/', desc: 'Focus keyword filter input' },
    { key: 'j / ↓', desc: 'Move selection to next posting' },
    { key: 'k / ↑', desc: 'Move selection to previous posting' },
    { key: 'Enter / o', desc: 'Open detail sheet for selected posting' },
    { key: 'Esc', desc: 'Close dialogs, sheets, or clear search focus' },
    { key: '?', desc: 'Toggle keyboard shortcuts help' },
  ];

  return (
    <div
      className="modal-backdrop fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.45)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        className="modal-card w-full max-w-md p-6 bg-[var(--surface)] border border-[var(--border)] text-[var(--ink)] shadow-none flex flex-col gap-5 focus:outline-none"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
          <div className="flex items-center gap-2">
            <Keyboard className="size-4 text-[var(--accent)]" aria-hidden="true" />
            <h2 id="shortcuts-title" className="text-body font-semibold text-[var(--ink)]">
              Keyboard shortcuts
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close shortcuts modal"
            className="text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]"
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex flex-col divide-y divide-[var(--border-subtle)]">
          {shortcuts.map(({ key, desc }) => (
            <div
              key={key}
              className="py-2.5 flex items-center justify-between text-small"
            >
              <span className="text-[var(--ink)]">{desc}</span>
              <Kbd className="text-caption">{key}</Kbd>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-2 border-t border-[var(--border-subtle)]">
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="text-small border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]"
          >
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
