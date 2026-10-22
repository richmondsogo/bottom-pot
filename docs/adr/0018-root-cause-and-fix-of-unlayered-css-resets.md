# ADR 0018: Root Cause and Fix of Missing Padding and Margins (Unlayered CSS Resets)

## Context
Following Pass 2, text across buttons, inputs, filter chips, and containers sat flush against borders with zero padding and zero margins. Utility classes like `px-4`, `py-2`, `mb-4`, `p-6`, and `gap-6` were written in JSX and compiled by Vite into the CSS bundle, but had no effect on the computed layout in the browser.

## Diagnosis via Computed Style Analysis
Direct measurement in the browser using Playwright/DevTools revealed:
- `h1`: `mb-4` resulted in `margin-bottom: 0px`.
- `Location input`: `px-3.5` resulted in `padding-left: 0px, padding-right: 0px`.
- `Search ATS platforms button`: `px-8` resulted in `padding-left: 0px, padding-right: 0px`.
- `Suggestion chip`: `px-3 py-1` resulted in `padding: 0px`.
- `More filters panel`: `p-6 mt-4` resulted in `padding: 0px, margin-top: 0px`.

### Root Cause
In `frontend/src/index.css`, universal resets were defined in the unlayered global scope:
```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  border-radius: 0 !important;
}
```
Per the CSS Cascading and Inheritance Level 4 & 5 specifications, **unlayered styles take precedence over all layered styles**, regardless of selector specificity.
Tailwind CSS v4 places all generated utility classes (`px-*`, `py-*`, `mb-*`, `p-*`, `mt-*`, etc.) into `@layer utilities`. Because the unlayered `* { margin: 0; padding: 0; }` matched every element in the unlayered scope, it silently eradicated all Tailwind utility margins and paddings across the application unless an explicit `!important` flag was provided.

## Decision
1. **Remove Destructive Universal Margin/Padding Reset**: Remove `margin: 0; padding: 0;` from `*`. Tailwind's built-in preflight handles element normalization safely within layers.
2. **Move Base Resets to `@layer base`**: Wrap all global element rules (`*`, `html`, `body`, `button`, `input`, `select`, `textarea`, `::-webkit-scrollbar`) inside `@layer base`.
3. **Strict Ban on Unlayered Element/Universal Rules**: Establish a permanent guardrail preventing any future unlayered element-selector resets in the stylesheet.

## Verification & Consequences
Immediate post-fix verification confirmed:
- `h1`: `margin-bottom` restored to `16px`.
- `Location input`: `padding-left` and `padding-right` restored to `14px` (`px-3.5`).
- `Search ATS platforms button`: `padding-left` and `padding-right` restored to `32px` (`px-8`).
- `Suggestion chip`: `padding-left` and `padding-right` restored to `12px` (`px-3`).
- `More filters panel`: `padding` restored to `24px` (`p-6`) and `margin-top` restored to `16px` (`mt-4`).
- All `!important` padding workarounds can now be systematically removed.
