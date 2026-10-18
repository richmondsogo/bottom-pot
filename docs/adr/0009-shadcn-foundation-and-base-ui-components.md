# ADR 0009: shadcn/ui Foundation and Base UI Component Architecture

## Status
Accepted

## Context
In pass 1, the frontend was rebuilt with React 19, Tailwind CSS v4, and `@base-ui/react`, but UI components in `frontend/src/components` remained largely hand-rolled divs and bespoke CSS classes without standard accessible component primitives. This led to inconsistent behaviors, awkward focus states, and styling maintenance overhead. The mission requires `shadcn/ui` as the mandatory component foundation with strict square geometry (`--radius: 0`).

## Decision
1. Standardize all UI interactive controls on `shadcn/ui` components located in `frontend/src/components/ui/`.
2. Configure `components.json` using the modern `@base-ui/react` (base-nova) primitive layer compatible with React 19.
3. Use shadcn MCP tools to inspect, view, and add primitives (Button, Input, Select, DropdownMenu, Popover, Command, Dialog, Sheet, Tooltip, Toggle, Checkbox, Collapsible, Badge, Separator, Skeleton, Empty, Kbd, Sonner).
4. Enforce `--radius: 0` globally at the token level, with no per-component radius overrides.

## Consequences
- Every control has built-in accessibility (ARIA roles, keyboard focus management, focus-visible outlines).
- Consistent event handling and standardized variant patterns (`cva`).
- Clean separation between core reusable UI primitives (`components/ui`) and application views (`components`).
