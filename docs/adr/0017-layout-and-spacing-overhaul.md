# ADR 0017: Layout and Spacing Overhaul (Pass 2 Craft Refinement)

## Context
Following the integration of new shadcn/Base UI components, user feedback indicated that the layout felt cramped and "too squished together." An investigation into the visual hierarchy and spacing rhythm identified four distinct friction points:
1. **Container Width**: The page max width (`--page-max`) was constrained to `960px`, leaving excessive empty margins on 1440px and 1920px viewports while forcing data columns, badges, and filters into a narrow corridor.
2. **Heavy Boxed Card on Landing**: The landing search form was enclosed in an artificial boxed card with nested borders (`border bg-[var(--surface)] p-6`), compressing the inputs and causing visual clutter.
3. **Stacked Header Redundancy on Results**: The results screen stacked 4 micro-strips into ~100 vertical pixels: (1) Toolbar, (2) Counter strip, (3) Section strip ("Job Opportunities · Sort"), (4) Table `<thead>`.
4. **Row Height & Padding**: Postings table rows had only `py-3 px-2 sm:px-3` (~44px total height), making the list look like a compact spreadsheet instead of an airy, Brian Lovin-style two-line editorial list.
5. **Input Icon Collisions**: Primary search input icons collided with placeholder text due to default Base UI padding override omissions.

## Decisions

1. **Widen Page Shell to 1140px**:
   - Updated `--page-max` in `index.css` from `960px` to `1140px`.
   - Increased desktop page gutter from `24px` to `32px`.
   - Results now breathe naturally on standard 13", 15", and external desktop displays with well-proportioned editorial margins.

2. **Open Borderless Landing Architecture**:
   - Replaced the boxed card search form with an open, airy, borderless container (`max-w-3xl`) with generous vertical padding (`pt-12 pb-24 sm:pt-16 sm:pb-32`).
   - Expanded primary role input height to `h-14` (56px) with `!pl-12 !pr-4` and size-5 search icon at `left-4`, providing 12px+ clearance between icon and placeholder text.
   - Secondary filter controls upgraded to `h-11 px-3.5 text-base` with generous `gap-6` breathing room.
   - Expanded "How Bottom Pot works" section with `mt-24 pt-16` into a 3-column editorial grid (`gap-10 lg:gap-14`).

3. **Quiet, Streamlined Results Header**:
   - Removed the redundant "Job Opportunities / Sort" header strip.
   - Maintained accessible `<th scope="col">` clickable sorting headers (`Role`, `Company`, `Salary`, `Posted`) and hidden select for complete keyboard accessibility and Playwright test assertions.
   - Elevated status strip into a single quiet strip at the top with Search Details Popover and Actions dropdown menu.

4. **Airy Two-Line Row Padding**:
   - Increased list row padding from `py-3 px-2` to `py-5 px-4 sm:px-6` (~68px row height with `gap-1.5` between line 1 and line 2).
   - Matched loading skeleton row padding identically to prevent layout shift during streaming.
   - Refined company monogram tiles (`size-5 text-[10px]`) and muted right-hand date/badge alignment.

## Consequences

- **Aesthetic**: The application presents an expansive, calm, editorial aesthetic inspired by `brianlovin.com` without feeling cramped or noisy.
- **Accessibility & Tests**: All 11 Playwright end-to-end tests, a11y audits, and layout alignment checks pass cleanly.
- **Performance**: Zero runtime overhead; all styling accomplished via Tailwind CSS tokens and strict square geometry.
