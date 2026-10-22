import React, { useEffect, useState } from 'react';
import { isMockModeActive, getMockModeType } from '../lib/mock';
import { HelpCircle, Sun, Moon, Command as CommandIcon } from 'lucide-react';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';

interface HeaderProps {
  onOpenShortcuts: () => void;
  onOpenCommand: () => void;
  onResetSearch?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const FEEDBACK_URL = '';

export const Header: React.FC<HeaderProps> = ({
  onOpenShortcuts,
  onOpenCommand,
  onResetSearch,
  theme,
  onToggleTheme,
}) => {
  const isMock = isMockModeActive();
  const mockType = getMockModeType();
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 12);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  return (
    <header
      className="sticky top-0 z-30 w-full transition-colors duration-150"
      style={{
        backgroundColor: 'var(--bg)',
        borderBottom: isScrolled ? '1px solid var(--border)' : '1px solid transparent',
        height: 'var(--header-height)',
      }}
    >
      <div className="page-shell h-full flex items-center justify-between">
        {/* Brandmark + Wordmark */}
        <div
          onClick={onResetSearch}
          className="flex items-center gap-2.5 select-none focus-visible:outline-none"
          style={{ cursor: onResetSearch ? 'pointer' : 'default' }}
          role={onResetSearch ? 'button' : undefined}
          tabIndex={onResetSearch ? 0 : undefined}
          aria-label={onResetSearch ? 'Bottom Pot' : undefined}
          onKeyDown={(e) => {
            if (onResetSearch && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault();
              onResetSearch();
            }
          }}
        >
          <div
            aria-hidden="true"
            className="flex items-center justify-center font-bold text-xs"
            style={{
              width: '24px',
              height: '24px',
              backgroundColor: 'var(--accent)',
              color: '#FFFFFF',
              letterSpacing: '-0.02em',
            }}
          >
            BP
          </div>
          <span className="font-semibold text-[15px] tracking-[-0.02em] text-[var(--ink)]">
            Bottom Pot
          </span>
        </div>

        {/* Right Actions: Command, Theme, Help */}
        <div className="flex items-center gap-1.5">
          {isMock && (
            <span
              className="text-data text-[11px] px-2 py-0.5 border"
              style={{
                backgroundColor: 'var(--surface-subtle)',
                color: 'var(--ink-muted)',
                borderColor: 'var(--border)',
              }}
              title="Running against offline fixtures (0 Serper calls)"
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

          {/* Command Palette Trigger */}
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
