# Step 19 Log: Header, Footer, and Brand Logo Kit Integration

- **Status**: COMPLETED
- **Branch**: `step/19-header-footer-logo`
- **Baseline**: `main` at `08f30eb` after step 17 (prompt composer and exports), PR #21
- **Step 17 Merge Commit SHA**: `08f30ebbc812c2e31b1fcc69a70b27d490e2f491` (`08f30eb`)
- **First Commit SHA**: `67c7f36`
- **Last Commit SHA**: `28ee58c`
- **PR URL**: https://github.com/richmondsogo/bottom-pot/pull/22
- **Merge SHA**: recorded on merge / next step doc
- **Active Baselines**: `user-s19-1` and `admin-s19-1` (succeeding Step 17's `user-s17b-1` and `admin-s17c-2`; legacy `ext-1` and `user-1` retired)
- **Author**: Antigravity Pair Programmer
- **Date**: 2026-10-29

---

## 1. Objectives & Scope

1. **Brand Logo Symbol & Component (`frontend/src/components/BottomPotLogo.tsx`, `docs/adr/0023-logo-and-icon-set.md`)**:
   - Adopt the saucepan-from-above brand mark (`<LogoSymbol className="h-6 w-6 shrink-0 text-[var(--ink)]" />`, `24px` symbol-only, removing the typed wordmark completely) across all headers and the admin login card, paired with `<LogoSymbol className="h-4 w-auto shrink-0 text-[var(--ink)]" />` in the footer:
     1. `/` marketing header (`HeroPortalSection.tsx` — `h-8 w-8 p-2 -ml-2` button matching the `32×32px` theme toggle control)
     2. `/app` workspace header (`Header.tsx` — `h-8 w-8 p-2 -ml-2` button matching the `32×32px` toolbar icon buttons)
     3. `/admin` workspace header (`Header.tsx` — `h-8 w-8 p-2 -ml-2` button)
     4. `/admin` login card (`AdminLogin.tsx` — standalone `<LogoSymbol className="h-6 w-6 shrink-0 text-[var(--ink)]" />`)
     5. Browser favicons, touch icons, OG image, and webmanifest (`frontend/public/` + `frontend/index.html`)
     6. Minimal `<Footer />` on `/` (`EditorialManifesto.tsx`) and on `/app` + `/admin` (`Workspace.tsx`)
   - Light/Dark optical cuts: light mode uses forest green symbol (`#1A382B`, `--logo-symbol`); dark mode (`.dark`) swaps in the optically thinned `SYMBOL_REVERSED` path in warm cream (`currentColor`).
   - Accessibility: `<LogoLockup />` and `<LogoSymbol />` support `aria-hidden="true"` when nested inside a labelled `<button>` (omitting `role="img"` and `aria-label` to prevent duplicate screen-reader announcements) while preserving `role="img" aria-label={title}` when rendered standalone (e.g., on `AdminLogin.tsx`).

2. **Web Icon Set & HTML Metadata (`frontend/public/`, `frontend/index.html`)**:
   - Installed `favicon.svg` (using the `16–24px` small optical cut with `@media(prefers-color-scheme:dark)` switching from `#1A382B` to `#FAF8F5`), `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `maskable-512.png`, `og-image.png`, and `site.webmanifest` into `frontend/public/`.
   - Updated `frontend/index.html` with icon links, manifest, light/dark `theme-color` meta tags (`#FAF8F5` and `#0C0D0C`), and `<meta property="og:image" content="/og-image.png" />`.
   - Archived the raw designer folder out of the repository root to `$env:TEMP\bottom-pot-logo-kit-archive`.

3. **Restrained Minimal Footer (`frontend/src/components/Footer.tsx`)**:
   - Created a single-row, `.page-shell`-aligned `<Footer />` component rendered on `/` (`EditorialManifesto.tsx`) and `/app` + `/admin` (`Workspace.tsx`).
   - Left cluster: `<LogoSymbol className="h-4 w-auto shrink-0 text-[var(--ink)]" aria-hidden="true" />` + `<span>Bottom Pot &middot; Jobs straight from the company</span>`.
   - Right cluster on `/` (`variant="marketing"`): working buttons (`h-8 px-3`) for `Search jobs` (`onStartSearching`), `Where we search` (`#where-we-search`), `Why Bottom Pot` (`#why-bottom-pot`), and `Manifesto` (`#manifesto`).
   - Right cluster on `/app` and `/admin` (`variant="workspace"`): working buttons (`h-8 px-3`) for `Overview` (`onBackToMarketing`), `New search` (`onNewSearch`), and `Shortcuts (?)` (`onOpenShortcuts`).
   - Zero dead/placeholder links (`Privacy`, `Terms`, `About`, `Careers`, `Blog`, `Contact`, `Status` strictly excluded).

---

## 2. Verification Evidence

### 1. Lint Gate (`npm --prefix frontend run lint`)
```text
Found 3 warnings and 0 errors.
Finished in 166ms on 81 files with 116 rules using 4 threads.
```

### 2. Vitest Suite (`npm --prefix frontend test`)
```text
Test Files  10 passed (10)
     Tests  71 passed (71)
  Duration  4.40s
```
Includes `frontend/src/lib/__tests__/logoAndFooter.test.tsx` (3 tests covering light/dark SVG path cuts, `aria-hidden` vs `role="img"`, legacy `"BP"` tile replacement with symbol-only `<LogoSymbol />` in `Header` and `AdminLogin`, and `Footer` marketing/workspace action sets and callback invocation).

### 3. Frontend Production Build (`npm --prefix frontend run build`)
```text
✓ 2608 modules transformed.
dist/index.html                     1.51 kB │ gzip:   0.71 kB
dist/assets/index-C1He1r43.css     95.22 kB │ gzip:  16.59 kB
dist/assets/index-Cu7o7usR.js     896.62 kB │ gzip: 274.10 kB
✓ built in 1.91s
```

### 4. Pytest Suite (`pytest`)
```text
====================== 339 passed, 21 warnings in 11.87s ======================
```

### 5. Playwright E2E Suite (`npx playwright test --workers=1 --reporter=list`)
```text
Running 33 tests using 1 worker
  33 passed (1.4m)
```
Includes `step 19: brand logo symbol, web icons, and restrained footer across /, /app, and /admin` in `tests/e2e/bottom-pot.spec.js`.

### 6. 38-State Capture, Self-Diff & Cropped Workspace Region Comparison (Port 8001, `SERPER_MODE=cache_only`)
- **User Mode Self-Diff (`user-s19-1` vs `user-s19-2`)**:
  - `SUCCESS: ALL 76 FILES MATCH IDENTICALLY (zero jitter) for User Mode (user-s19-1 vs user-s19-2)!`
- **Admin Mode Self-Diff (`admin-s19-1` vs `admin-s19-2`)**:
  - `SUCCESS: ALL 76 FILES MATCH IDENTICALLY (zero jitter) for Admin Mode (admin-s19-1 vs admin-s19-2)!`
- **Cropped Workspace Region Comparison (`y = 56px` down to top of footer)**:
  - `user-s19-1` vs `user-s17b-1`: **33/33 cropped workspace states have 0 pixel differences**.
  - `admin-s19-1` vs `admin-s17c-2`: **31/33 cropped workspace states have 0 pixel differences** (the remaining 2 states have sub-0.12% anti-aliasing diffs: `results_command_palette_390.png` has 354/307,320 pixels at `y=56..60` from the Command Palette overlay's `4px` `backdrop-blur` bleeding across the `y=56px` header boundary, and `results_keyboard_row_1440.png` has 144/1,215,360 pixels at `y=519..530` from keyboard focus outline anti-aliasing).
- **Visual Contact Sheet**:
  - Generated at: `C:\Users\Richmond\AppData\Local\Temp\bp-refactor-baseline\contact-sheet-step19.html`

### 7. Database & Process Integrity
- `data/cache.sqlite` `mtime` before (`1793288978.309245`) and after (`1793288978.309245`): **unchanged**.
- `serper_daily_budget` rows before (`[('2026-10-29', 18)]`) and after (`[('2026-10-29', 18)]`): **unchanged**.
- Temporary port 8001 server cleanly stopped and verified released.
