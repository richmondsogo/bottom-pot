import React from 'react';
import { isMockModeActive, getMockModeType } from '../lib/mock';
import { HelpCircle, Sun, Moon, Command as CommandIcon, Menu } from 'lucide-react';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';
import { LogoSymbol } from './BottomPotLogo';
import { routeToPath, type AppRoute } from '../lib/router';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from './ui/dropdown-menu';

export interface HeaderProps {
  activeRoute: AppRoute;
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
  onOpenShortcuts: () => void;
  onOpenCommand: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  mode?: 'user' | 'admin';
  onLogout?: () => void;
}

const PRIMARY_NAV_ITEMS: Array<{ route: AppRoute; label: string }> = [
  { route: 'search', label: 'Search' },
  { route: 'product', label: 'Product' },
  { route: 'sources', label: 'Sources' },
  { route: 'about', label: 'About' },
];

export const Header: React.FC<HeaderProps> = ({
  activeRoute,
  onNavigate,
  onStartNewSearch,
  onOpenShortcuts,
  onOpenCommand,
  theme,
  onToggleTheme,
  mode = 'user',
  onLogout,
}) => {
  const isMock = isMockModeActive();
  const mockType = getMockModeType();
  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  const handleOpenSearchClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (onStartNewSearch) {
      onStartNewSearch();
    } else {
      onNavigate('search');
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
      <div className="page-shell h-full flex items-center justify-between gap-4">
        {/* Left: Brand mark + Primary Page Navigation */}
        <div className="flex items-center gap-2 sm:gap-5 min-w-0">
          <a
            href="/"
            onClick={handleLinkClick('home')}
            className="h-8 max-md:h-11 px-2 -ml-2 rounded-md inline-flex items-center gap-2.5 select-none focus-visible:outline-none cursor-pointer group text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)] transition-[color,background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none shrink-0"
            aria-label="Bottom Pot home"
          >
            <LogoSymbol className="h-5 w-auto shrink-0 text-[var(--ink)]" aria-hidden="true" />
            <span className="font-semibold text-sm tracking-tight text-[var(--ink)]">
              Bottom Pot
            </span>
          </a>

          {mode === 'admin' && (
            <span
              className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-sm border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] select-none shrink-0"
              title="Administrator Workspace"
            >
              ADMIN
            </span>
          )}

          <nav aria-label="Primary navigation" className="hidden md:flex items-center gap-1">
            {PRIMARY_NAV_ITEMS.map(({ route, label }) => {
              const isActive =
                activeRoute === route || (route === 'search' && activeRoute === 'admin');
              return (
                <a
                  key={route}
                  href={routeToPath(route)}
                  onClick={handleLinkClick(route)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`h-8 px-3 rounded-md inline-flex items-center gap-2 text-sm border transition-[color,background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none select-none cursor-pointer ${
                    isActive
                      ? 'bg-[var(--surface-subtle)] border-[var(--border-strong)] text-[var(--ink)] font-medium'
                      : 'border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                  }`}
                >
                  {isActive && (
                    <span className="size-1.5 bg-[var(--accent)] shrink-0" aria-hidden="true" />
                  )}
                  <span>{label}</span>
                </a>
              );
            })}
          </nav>
        </div>

        {/* Right Actions: Contextual Link, Admin Actions, Theme, Shortcuts, Mobile Menu */}
        <div className="flex items-center gap-1.5 shrink-0">
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
              className="text-data text-[11px] px-2 py-0.5 rounded-sm border max-md:hidden"
              style={{
                backgroundColor: 'var(--surface-subtle)',
                color: 'var(--ink-muted)',
                borderColor: 'var(--border)',
              }}
              title={
                mode === 'admin'
                  ? 'Running against offline fixtures (0 Serper calls)'
                  : 'Running against offline fixtures'
              }
            >
              MOCK ({mockType.toUpperCase()})
            </span>
          )}

          {mode === 'admin' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onOpenCommand}
              className="hidden sm:inline-flex items-center gap-1.5 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] h-8 px-3 border border-transparent hover:border-[var(--border)]"
              title={
                isMac
                  ? 'Commands (⌘K): Open command palette'
                  : 'Commands (Ctrl+K): Open command palette'
              }
              aria-label={
                isMac
                  ? 'Commands (⌘K): Open command palette'
                  : 'Commands (Ctrl+K): Open command palette'
              }
            >
              <CommandIcon className="size-3.5" aria-hidden="true" />
              <span className="text-small text-[12.5px]">Commands</span>
              <Kbd className="text-[10px] ml-1 px-1 py-0">{isMac ? '⌘K' : 'Ctrl+K'}</Kbd>
            </Button>
          )}

          {activeRoute !== 'search' && activeRoute !== 'admin' && (
            <a
              href="/app"
              onClick={handleOpenSearchClick}
              className="hidden sm:inline-flex items-center h-8 px-3 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] text-xs font-medium text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none"
            >
              Open search
            </a>
          )}

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleTheme}
            className="max-md:size-11 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Sun className="size-4" aria-hidden="true" />
            ) : (
              <Moon className="size-4" aria-hidden="true" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenShortcuts}
            className="max-md:size-11 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
            title="Keyboard shortcuts & help (?)"
            aria-label="Keyboard shortcuts and help"
          >
            <HelpCircle className="size-4" aria-hidden="true" />
          </Button>

          <div className="md:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger
                className="h-8 w-8 max-md:size-11 p-2 rounded-md inline-flex items-center justify-center border border-transparent hover:border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] cursor-pointer select-none"
                aria-label="Open navigation menu"
              >
                <Menu className="size-4" aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuItem onClick={() => onNavigate('home')}>Home</DropdownMenuItem>
                {PRIMARY_NAV_ITEMS.map(({ route, label }) => (
                  <DropdownMenuItem key={route} onClick={() => onNavigate(route)}>
                    {label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </header>
  );
};
