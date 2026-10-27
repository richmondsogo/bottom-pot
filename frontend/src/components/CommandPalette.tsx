import React, { useEffect } from 'react';
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from './ui/command';
import { Kbd } from './ui/kbd';
import {
  RotateCcw,
  Plus,
  Edit3,
  Trash2,
  Download,
  Moon,
  Sun,
  Keyboard,
  Filter,
  Compass,
  LayoutGrid,
} from 'lucide-react';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNewSearch: () => void;
  onEditSearch: () => void;
  onRunAgain: () => void;
  onClearSaved: () => void;
  onDownloadCsv: () => void;
  onDownloadJson: () => void;
  onFocusFilter: () => void;
  onOpenShortcuts: () => void;
  onSwitchToMarketing?: () => void;
  onSwitchToWorkspace?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  hasResults: boolean;
  hasSavedResults: boolean;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  open,
  onOpenChange,
  onNewSearch,
  onEditSearch,
  onRunAgain,
  onClearSaved,
  onDownloadCsv,
  onDownloadJson,
  onFocusFilter,
  onOpenShortcuts,
  onSwitchToMarketing,
  onSwitchToWorkspace,
  theme,
  onToggleTheme,
  hasResults,
  hasSavedResults,
}) => {
  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange]);

  const runCommand = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Bottom Pot Commands"
      description="Type a command or search..."
    >
      <CommandInput placeholder="Type a command or search actions..." />
      <CommandList>
        <CommandEmpty>No matching actions found.</CommandEmpty>

        <CommandGroup heading="Search Actions">
          <CommandItem onSelect={() => runCommand(onNewSearch)}>
            <Plus className="size-4 mr-2 text-[var(--ink-muted)]" />
            <span>New search</span>
            <Kbd className="ml-auto text-[10px]">N</Kbd>
          </CommandItem>

          {(hasResults || hasSavedResults) && (
            <CommandItem onSelect={() => runCommand(onEditSearch)}>
              <Edit3 className="size-4 mr-2 text-[var(--ink-muted)]" />
              <span>Edit search parameters</span>
              <Kbd className="ml-auto text-[10px]">E</Kbd>
            </CommandItem>
          )}

          {(hasResults || hasSavedResults) && (
            <CommandItem onSelect={() => runCommand(onRunAgain)}>
              <RotateCcw className="size-4 mr-2 text-[var(--ink-muted)]" />
              <span>Run search again</span>
              <Kbd className="ml-auto text-[10px]">R</Kbd>
            </CommandItem>
          )}

          {hasResults && (
            <CommandItem onSelect={() => runCommand(onFocusFilter)}>
              <Filter className="size-4 mr-2 text-[var(--ink-muted)]" />
              <span>Focus search filter</span>
              <Kbd className="ml-auto text-[10px]">/</Kbd>
            </CommandItem>
          )}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Data & Storage">
          <CommandItem
            onSelect={() => runCommand(onDownloadCsv)}
            disabled={!hasResults && !hasSavedResults}
          >
            <Download className="size-4 mr-2 text-[var(--ink-muted)]" />
            <span>Download results as CSV</span>
          </CommandItem>

          <CommandItem
            onSelect={() => runCommand(onDownloadJson)}
            disabled={!hasResults && !hasSavedResults}
          >
            <Download className="size-4 mr-2 text-[var(--ink-muted)]" />
            <span>Download results as JSON</span>
          </CommandItem>

          {hasSavedResults && (
            <CommandItem onSelect={() => runCommand(onClearSaved)}>
              <Trash2 className="size-4 mr-2 text-[var(--destructive)]" />
              <span className="text-[var(--destructive)]">Clear saved results</span>
            </CommandItem>
          )}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigation & Views">
          {onSwitchToMarketing && (
            <CommandItem onSelect={() => runCommand(onSwitchToMarketing)}>
              <Compass className="size-4 mr-2 text-[var(--ink-muted)]" />
              <span>Marketing overview &amp; live stage</span>
            </CommandItem>
          )}

          {onSwitchToWorkspace && (
            <CommandItem onSelect={() => runCommand(onSwitchToWorkspace)}>
              <LayoutGrid className="size-4 mr-2 text-[var(--ink-muted)]" />
              <span>Open product workspace (/app)</span>
            </CommandItem>
          )}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Preferences & Help">
          <CommandItem onSelect={() => runCommand(onToggleTheme)}>
            {theme === 'dark' ? (
              <Sun className="size-4 mr-2 text-[var(--ink-muted)]" />
            ) : (
              <Moon className="size-4 mr-2 text-[var(--ink-muted)]" />
            )}
            <span>Toggle theme ({theme === 'dark' ? 'Light mode' : 'Dark mode'})</span>
          </CommandItem>

          <CommandItem onSelect={() => runCommand(onOpenShortcuts)}>
            <Keyboard className="size-4 mr-2 text-[var(--ink-muted)]" />
            <span>Keyboard shortcuts & help</span>
            <Kbd className="ml-auto text-[10px]">?</Kbd>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
};
