# Step 17 Log: Prominent CSV/JSON Exports & Upgraded Search Prompt Composer

- **Status**: READY FOR REVIEW (Commits staged on step branch; awaiting PR instruction)
- **Branch**: `step/17-exports-and-search-prompt`
- **Baseline**: `main` at `58ef527` after Step 16 (`balanced ATS/Nigerian result mix and HotNigerianJobs application extraction`)
- **Author**: Antigravity Pair Programmer
- **Date**: 2026-10-29

---

## 1. Objectives & Scope

1. **Prominent CSV/JSON Exports (`SearchSummaryBar.tsx`)**:
   - Introduce a prominent, dedicated **Export** dropdown button next to "Edit search" in `SearchSummaryBar.tsx` (when `mode === 'user'`).
   - Trigger: Square `<Button variant="outline" size="sm">` with `<Download className="size-3.5 mr-1" />`, label `Export`, and subtle chevron (`ChevronDown`), `aria-label="Export results"`.
   - Content: Square `DropdownMenuContent` (`align="end"`, `rounded-none`, `border-[var(--border)]`, `bg-[var(--surface)]`) containing:
     - `<DropdownMenuItem id="downloadBtn">` -> `Download CSV ({visibleCount})`
     - `<DropdownMenuItem id="downloadJsonBtn">` -> `Download JSON ({visibleCount})`
   - Remove CSV/JSON items from the `More actions` (`...`) overflow menu when `mode === 'user'` to eliminate duplicate HTML ID attributes (`#downloadBtn`, `#downloadJsonBtn`).
   - Retain CSV/JSON in `More actions` when `mode === 'admin'` to maintain 100% byte-identical DOM parity with `ext-1`.
   - Leave `Toolbar.tsx` visual DOM untouched.

2. **Upgraded Search Prompt Composer (`prompt-kit` + `shadcn`)**:
   - Create `frontend/src/components/prompt-kit/prompt-input.tsx` following `prompt-kit` architecture (`PromptInput`, `PromptInputField`, `PromptInputActions`, `PromptInputAction`) with strict square design system (`--radius: 0`, `rounded-none`, hairline `border-[var(--border)]`, restrained 140ms ease-out transitions).
   - Upgrade `SearchForm.tsx` (in `mode === 'user'`) to use this unified Command Prompt Composer:
     - Top region: high-contrast keyword prompt input (`id="keywords-input"`, preserving `<Label htmlFor="keywords-input">` with `"Role or keyword"` so `page.getByLabel(/role or keyword/i)` works).
     - Attached bottom action dock (`PromptInputActions`):
       - Inline Location field (`id="location-input"`, preserving accessible label `"Location or country"`).
       - Inline Work Model selector (`id="work-model-select"`, preserving accessible label `"Work model"` and native `<select>` control).
       - More Filters toggle (`CollapsibleTrigger`) showing badge count when secondary filters are active.
       - Primary Submit button ("Search jobs") styled in deep forest green accent (`var(--accent)`).
     - Below composer: Role suggestion chips (`PromptSuggestion` pills) and `CollapsibleContent` drawer for secondary platform and date filters.

3. **Admin Workspace Parity Isolation**:
   - Isolate admin JSX completely via early return in `SearchForm.tsx` and `SearchSummaryBar.tsx`, ensuring all 33 admin workspace states remain 100% byte-identical to `ext-1`.

4. **Rigorous Verification & Provenance**:
   - Unit tests for prompt-input and export dropdown (`frontend/src/lib/__tests__/promptInput.test.tsx`).
   - Playwright E2E coverage updated and extended with `step 17: prompt-input composer and prominent export dropdown flow` in `tests/e2e/bottom-pot.spec.js`.
   - Admin parity audit across 33 workspace states on port 8001 in `cache_only` mode.
   - Contact sheet comparing `user-step15` vs `user-step17` across form and results viewports plus open export dropdown.

---

## 2. Grep Matches for Export Selectors in Tests & Scripts

A preliminary grep across `tests/` and scripts for `downloadBtn`, `downloadJsonBtn`, `More actions`, `Download CSV`, and `Download JSON` revealed:
- `tests/e2e/bottom-pot.spec.js:189`: `// Test CSV and JSON download triggers`
- `tests/e2e/bottom-pot.spec.js:190`: `await page.getByRole('button', { name: /more actions/i }).click();`
- `tests/e2e/bottom-pot.spec.js:191`: `const [csvDownload] = await Promise.all([..., page.locator('#downloadBtn').click()]);`
- `tests/e2e/bottom-pot.spec.js:194`: `await page.getByRole('button', { name: /more actions/i }).click();`
- `tests/e2e/bottom-pot.spec.js:195`: `const [jsonDownload] = await Promise.all([..., page.locator('#downloadJsonBtn').click()]);`

### Playwright Selector Update
In `tests/e2e/bottom-pot.spec.js`, line 190 was updated:
```diff
- await page.getByRole('button', { name: /more actions/i }).click();
+ await page.getByRole('button', { name: /export results/i }).click();
```
Line 194 was also updated to reopen the dedicated `export results` dropdown menu instead of the overflow menu.

---

## 3. Implementation Details

### A. Prompt Composer Component (`frontend/src/components/prompt-kit/prompt-input.tsx`)
Implemented modular, composable primitives with Base UI integration and strict square styling:
- `PromptInput`: Frame wrapper with hairline border, background surface, and focus-within ring.
- `PromptInputField`: Text input/textarea area with muted placeholder, sans-serif typography, and zero native border.
- `PromptInputActions`: Bottom toolbar dock separated by hairline `border-t border-[var(--border)] bg-[var(--bg-subtle)]`.
- `PromptInputAction`: Action button with optional Base UI tooltip support.

### B. Upgraded User `SearchForm.tsx`
- Integrated `PromptInput` into `SearchForm.tsx` for `mode === 'user'`.
- Preserved exact accessible labels for `role or keyword`, `location or country`, and `work model`.
- Styled primary submit button with 140ms ease-out transitions and square geometry.
- Fully preserved separate admin JSX block for 100% baseline parity.

### C. Dedicated Export Dropdown in `SearchSummaryBar.tsx`
- Positioned between "Edit search" and "More actions".
- User mode exposes `Download CSV ({visibleCount})` and `Download JSON ({visibleCount})`.
- Admin mode retains CSV and JSON downloads inside `More actions` to guarantee 0 DOM diffs against `ext-1`.

---

## 4. Verification Evidence

### 1. Oxlint Gate
```
Found 8 warnings and 0 errors.
Finished in 151ms on 90 files using 4 threads.
(3 baseline UI primitive warnings + 5 legacy frontend-old warnings; 0 errors)
```

### 2. Vitest Suite
```
 Test Files  9 passed (9)
      Tests  63 passed (63)
   Duration  3.43s
```
Includes 4 unit tests in `promptInput.test.tsx`:
- PromptInput renders with correct structure and CSS classes
- PromptInputActions renders action children in dock
- SearchSummaryBar renders dedicated Export dropdown in user mode
- SearchSummaryBar keeps CSV and JSON in More actions for admin mode

### 3. Frontend Build (`tsc -b && vite build`)
```
✓ 2606 modules transformed.
dist/index.html                     1.15 kB │ gzip:   0.62 kB
dist/assets/index-G0jhxx16.css     95.31 kB │ gzip:  16.59 kB
dist/assets/index-fotipZBI.js     904.11 kB │ gzip: 274.10 kB
✓ built in 2.35s
```

### 4. Pytest Suite
```
====================== 334 passed, 21 warnings in 18.53s ======================
```

### 5. Playwright E2E Suite
```
Running 31 tests using 1 worker
  31 passed (1.4m)
```
All 31 E2E tests passing, including the new `step 17: prompt-input composer and prominent export dropdown flow` test.

### 6. Admin Workspace Parity Audit (Port 8001, Cache-Only Mode)
```
--- 1. ADMIN PARITY AUDIT (33 WORKSPACE STATES vs ext-1) ---
[ADMIN MATCH]    : empty_1440.html
[ADMIN MATCH]    : empty_390.html
[ADMIN MATCH]    : error_1440.html
[ADMIN MATCH]    : error_390.html
[ADMIN MATCH]    : form_1024.html
[ADMIN MATCH]    : form_1440.html
[ADMIN MATCH]    : form_1920.html
[ADMIN MATCH]    : form_390.html
[ADMIN MATCH]    : form_768.html
[ADMIN MATCH]    : loading_1024.html
[ADMIN MATCH]    : loading_1440.html
[ADMIN MATCH]    : loading_1920.html
[ADMIN MATCH]    : loading_390.html
[ADMIN MATCH]    : loading_768.html
[ADMIN MATCH]    : results_1024.html
[ADMIN MATCH]    : results_1440.html
[ADMIN MATCH]    : results_1920.html
[ADMIN MATCH]    : results_390.html
[ADMIN MATCH]    : results_768.html
[ADMIN MATCH]    : results_command_palette_1440.html
[ADMIN MATCH]    : results_command_palette_390.html
[ADMIN MATCH]    : results_dark_1440.html
[ADMIN MATCH]    : results_dark_390.html
[ADMIN MATCH]    : results_detail_sheet_1440.html
[ADMIN MATCH]    : results_detail_sheet_390.html
[ADMIN MATCH]    : results_keyboard_row_1440.html
[ADMIN MATCH]    : results_keyboard_row_390.html
[ADMIN MATCH]    : results_scrolled_900_1440.html
[ADMIN MATCH]    : results_scrolled_900_390.html
[ADMIN MATCH]    : results_shortcuts_1440.html
[ADMIN MATCH]    : results_shortcuts_390.html
[ADMIN MATCH]    : results_telemetry_1440.html
[ADMIN MATCH]    : results_telemetry_390.html
Admin Workspace Parity: 33 MATCH, 0 MISMATCH out of 33 workspace states.
```

### 7. Visual Contact Sheet
Generated at:
`C:\Users\Richmond\AppData\Local\Temp\bp-refactor-baseline\contact-sheet-step17.html`
Side-by-side comparisons of `user-step15` vs `user-step17`:
- `form_1440` (Desktop 1440x900): Unified Prompt Composer vs step15 form
- `form_390` (Mobile 390x844): Mobile Prompt Composer & dock vs step15 mobile form
- `results_1440` (Desktop 1440x900): Dedicated prominent Export dropdown in Summary Bar vs step15
- `results_390` (Mobile 390x844): Mobile Export button visible in Summary Bar vs step15
- `results_1440_export_open` (Desktop 1440x900): Export dropdown open displaying `Download CSV ({visibleCount})` and `Download JSON ({visibleCount})`

### 8. Database & Process Integrity
- `serper_daily_budget` count before audit: `0`
- `serper_daily_budget` count after audit: `0`
- Port 8001 process (task-935) started during this turn was cleanly terminated and port 8001 verified released. No manual database doctoring was performed.
