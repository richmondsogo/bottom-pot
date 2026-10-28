import React from 'react';
import { isMockModeActive, getMockModeType } from '../lib/mock';
import { HelpCircle, Sun, Moon, Command as CommandIcon } from 'lucide-react';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';

interface HeaderProps {
  onOpenShortcuts: () => void;
  onOpenCommand: () => void;
  onResetSearch?: () => void;
  onBackToMarketing?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  mode?: 'user' | 'admin';
  onLogout?: () => void;
}

export const FEEDBACK_URL = '';

export const Header: React.FC<HeaderProps> = ({
  onOpenShortcuts,
  onOpenCommand,
  onResetSearch,
  onBackToMarketing,
  theme,
  onToggleTheme,
  mode = 'user',
  onLogout,
}) => {
  const isMock = isMockModeActive();
  const mockType = getMockModeType();

  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  const handleBrandClick = () => {
    if (onBackToMarketing) {
      onBackToMarketing();
    } else if (onResetSearch) {
      onResetSearch();
    }
  };

  return (
    <header
      className="sticky top-0 z-30 w-full transition-colors duration-150 border-b border-[var(--border)]"
      style={{
        backgroundColor: 'var(--bg)',
        height: 'var(--header-height)',
      }}
    >
      <div className="page-shell h-full flex items-center justify-between">
        {/* Brandmark + Wordmark + Overview back link */}
        <div className="flex items-center gap-3">
          <div
            onClick={handleBrandClick}
            className="flex items-center gap-2.5 select-none focus-visible:outline-none cursor-pointer group"
            role="button"
            tabIndex={0}
            aria-label="Bottom Pot - Return to Overview"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleBrandClick();
              }
            }}
          >
            <div
              aria-hidden="true"
              className="flex items-center justify-center font-bold text-xs w-7 h-7 bg-[var(--accent)] text-[var(--accent-foreground)] tracking-[-0.02em]"
            >
              BP
            </div>
            <span className="font-semibold text-[15px] tracking-[-0.02em] text-[var(--ink)]">
              Bottom Pot
            </span>
          </div>

          {mode === 'admin' && (
            <span
              className="text-[11px] font-mono font-semibold px-2 py-0.5 border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] select-none"
              title="Administrator Workspace"
            >
              ADMIN
            </span>
          )}

          {onBackToMarketing && (
            <button
              type="button"
              onClick={onBackToMarketing}
              className="hidden sm:inline-flex items-center gap-1.5 h-8 px-3 border border-[var(--border)] text-xs font-mono text-[var(--ink-muted)] hover:text-[var(--ink)] hover:border-[var(--border-strong)] transition-colors cursor-pointer select-none"
              title="Return to marketing overview"
            >
              <span>&larr; Overview</span>
            </button>
          )}
        </div>

        {/* Right Actions: Command, Theme, Help */}
        <div className="flex items-center gap-1.5">
          {mode === 'admin' && onLogout && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onLogout}
              className="text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] h-8 px-3 border border-transparent hover:border-[var(--border)] select-none cursor-pointer"
              title="Log out of admin session"
              aria-label="Log out of admin session"
            >
              Log out
            </Button>
          )}

          {isMock && (
            <span
              className="text-data text-[11px] px-2 py-0.5 border"
              style={{
                backgroundColor: 'var(--surface-subtle)',
                color: 'var(--ink-muted)',
                borderColor: 'var(--border)',
              }}
              title={mode === 'admin' ? "Running against offline fixtures (0 Serper calls)" : "Running against offline fixtures"}
            >
              MOCK ({mockType.toUpperCase()})
            </span>
          )}

          {FEEDBACK_URL && (
            <a
              href={FEEDBACK_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-small text-[var(--ink-muted)] hover:text-[var(--ink)] px-2 py-1"
            >
              Feedback
            </a>
          )}

          {/* Command Palette Trigger (Admin only) */}
          {mode === 'admin' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onOpenCommand}
              className="hidden sm:inline-flex items-center gap-1.5 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] h-8 px-3 border border-transparent hover:border-[var(--border)]"
              title={isMac ? 'Commands (⌘K) — Open command palette' : 'Commands (Ctrl+K) — Open command palette'}
              aria-label={isMac ? 'Commands (⌘K) — Open command palette' : 'Commands (Ctrl+K) — Open command palette'}
            >
              <CommandIcon className="size-3.5" aria-hidden="true" />
              <span className="text-small text-[12.5px]">Commands</span>
              <Kbd className="text-[10px] ml-1 px-1 py-0">{isMac ? '⌘K' : 'Ctrl+K'}</Kbd>
            </Button>
          )}

          {/* Theme Toggle Button */}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleTheme}
            className="text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Sun className="size-4" aria-hidden="true" />
            ) : (
              <Moon className="size-4" aria-hidden="true" />
            )}
          </Button>

          {/* Single Help Control */}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenShortcuts}
            className="text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
            title="Keyboard shortcuts & help (?)"
            aria-label="Keyboard shortcuts and help"
          >
            <HelpCircle className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </header>
  );
};
