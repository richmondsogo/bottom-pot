# ADR 0023: Logo and Icon Set

## Status
Accepted

## Context
Earlier iterations of Bottom Pot used a `28×28px` forest-green square tile displaying the letters `"BP"` alongside a typed wordmark in the header and browser favicon (`ADR 0004`). As the results table introduced deterministic `28×28px` square company monogram tiles, the header `"BP"` tile looked visually identical to a company monogram. Additionally, the marketing landing page, workspace header, administrator login, footer, and web manifest needed a unified, recognizable brand mark that scales cleanly from `16px` favicons up to full lockups in both light and dark modes while honoring our strict square geometry (`--radius: 0`) and editorial palette.

## Decision

1. **The Symbol (Saucepan Seen from Above)**:
   - The brand mark depicts a saucepan viewed from above: an outer ring, a thicker settled crescent at the bottom representing the crust ("bottom pot"), and a single square-cut (`0`-radius) handle pointing right to give direction.
   - Because the symbol is a geometric silhouette rather than a letter on a square tile, it is never confused with the `28×28px` company monograms in the results table.

2. **Wordmark & Lockup**:
   - The horizontal lockup pairs the saucepan symbol with `"Bottom Pot"` set in **Geist SemiBold** outlined directly to SVG paths (`viewBox="0 -88.75 705.84 106.5"`). The wordmark is never retyped with live font text inside the lockup.
   - Minimum screen widths: `112px` for the horizontal lockup (`h-[18px]` / `119px` wide on `<640px` mobile viewports; `h-7` / `185px` wide on `>=640px` desktop viewports), `24px` for the standard symbol, and `16px` for the small optical cut.

3. **Optical Cuts & Polarity**:
   - **Light Mode**: Symbol in forest green (`#1A382B`, `--logo-symbol`), wordmark in primary ink (`#181816`, `currentColor`).
   - **Dark Mode**: Reversed, optically thinned drawing (`SYMBOL_REVERSED`, `WORDMARK_REVERSED`) rendered in warm cream (`#FAF8F5` / `var(--ink)` via `currentColor`). The dark-mode mint/green accent (`#2E7D52` / `#34D399`) is never used for the logo.
   - **Small Optical Cut (`16–24px`)**: Used in `favicon.svg` with a shorter handle and thicker strokes for crisp pixel-grid legibility at `16×16px` and `32×32px`.

4. **Square App Tiles & Web Icons (`--radius: 0`)**:
   - All raster and vector app tiles (`favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `maskable-512.png`, `og-image.png`) use full-bleed `0`-radius forest-green squares (`#1A382B`) with the reversed symbol in cream (`#FAF8F5`). Operating systems apply their own masks where applicable; no rounded corners are baked into our assets.
   - `favicon.svg` adapts automatically to the browser's `prefers-color-scheme` (`#1A382B` in light mode, `#FAF8F5` in dark mode).

5. **Exemption from ADR 0021 Green Accent Budget**:
   - The logo symbol is brand identity, not an interactive UI chip or banner, and is exempt from the ADR 0021 green UI control budget (and uses SVG `fill` rather than CSS `backgroundColor` or `borderColor`).

## Consequences
- `frontend/src/components/BottomPotLogo.tsx` (`<LogoLockup />` and `<LogoSymbol />`) replaces all `"BP"` monogram tiles across `/`, `/app`, `/admin`, `/admin` login, and `<Footer />`.
- Static icon and manifest assets live in `frontend/public/` and are linked in `frontend/index.html`.
- Any future modification to the mark requires regenerating both light and reversed optical cuts and the static icon set from the master scripts.
