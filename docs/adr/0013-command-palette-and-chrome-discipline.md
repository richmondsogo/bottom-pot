# ADR 0013: Command Palette (Cmd+K) and Chrome Discipline

## Status
Accepted

## Context
Pass 1 had severe chrome clutter:
- Six outlined icon buttons competed for attention in the toolbar (Edit search, New search, Run again, Clear saved, Download CSV, Download JSON).
- Two stacked bands repeated information: a full-bleed "Search:" summary bar, followed by a separate status card.
- Redundant question mark icons appeared in the header.

## Decision
1. **Consolidated Summary Line**: Merge into ONE quiet sticky summary line:
   `Full Stack Developer · Last 7 days · 6 platforms · 52 postings · Saved 1m ago`
   with a "Search details" Popover containing Serper queries, cache metrics, and elapsed time.
2. **Action Hierarchy**:
   - Primary Action: "Edit search" ghost/outline button.
   - Secondary Actions: Consolidated into a single square DropdownMenu (Run again, New search, Clear saved with undo/confirmation, Download CSV, Download JSON).
3. **Command Palette (`shadcn/ui Command`)**:
   - Global shortcut: `⌘K` / `Ctrl+K`.
   - Offers rapid keyboard execution for all primary and secondary actions: New search, Edit search, Run again, Clear saved, Download CSV/JSON, Toggle theme, Show keyboard shortcuts.
   - Header button displays `⌘K` / `Ctrl K` via `<Kbd>` component.
4. **Header Cleanup**:
   - Single clean Help icon opening the Help/Shortcuts dialog without redundant glyphs.
   - Clean theme toggle icon button.

## Consequences
- Vastly reduced cognitive load on results pages.
- Power users can navigate entirely via keyboard shortcuts and the command palette.
- Eliminates toolbar button explosion.
