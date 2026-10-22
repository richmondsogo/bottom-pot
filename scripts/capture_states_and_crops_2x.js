// scripts/capture_states_and_crops_2x.js
// Captures 2x full-page states and component-level crops across 5 viewports, light and dark.

import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const outputDir = path.resolve(__dirname, '..', 'docs', 'design', 'after-restore');
const cropsDir = path.resolve(outputDir, 'crops');

fs.mkdirSync(outputDir, { recursive: true });
fs.mkdirSync(cropsDir, { recursive: true });

const VIEWPORTS = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1024x768', width: 1024, height: 768 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '390x844', width: 390, height: 844 },
];

const THEMES = ['light', 'dark'];

async function runCapture() {
  const browser = await chromium.launch({ headless: true });

  for (const theme of THEMES) {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
      });

      const page = await context.newPage();

      // Set theme via local storage
      await page.addInitScript((th) => {
        localStorage.setItem('bp.theme', th);
        if (th === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }, theme);

      // 1. Landing state
      await page.goto('http://127.0.0.1:8000/?mock=default');
      await page.waitForLoadState('networkidle');
      await page.evaluate((th) => {
        if (th === 'dark') document.documentElement.classList.add('dark');
        else document.documentElement.classList.remove('dark');
      }, theme);

      await page.screenshot({
        path: path.join(outputDir, `landing_${theme}_${vp.name}.png`),
        fullPage: true,
      });

      // 2. Landing with More Filters open
      const moreFiltersBtn = page.getByRole('button', { name: /more filters/i });
      if (await moreFiltersBtn.isVisible()) {
        await moreFiltersBtn.click();
        await page.waitForTimeout(150);
        await page.screenshot({
          path: path.join(outputDir, `landing_more_filters_${theme}_${vp.name}.png`),
          fullPage: true,
        });

        // Crop: More filters panel
        if (vp.name === '1440x900' && theme === 'light') {
          const panel = page.locator('.search-form-card');
          if (await panel.isVisible()) {
            await panel.screenshot({
              path: path.join(cropsDir, `crop_form_panel_with_more_filters.png`),
            });
          }
        }
      }

      // 3. Command Palette open
      await page.keyboard.press('Control+k');
      await page.waitForTimeout(200);
      const cmdDialog = page.getByRole('dialog');
      if (await cmdDialog.isVisible()) {
        await page.screenshot({
          path: path.join(outputDir, `command_palette_${theme}_${vp.name}.png`),
          fullPage: false,
        });
        if (vp.name === '1440x900' && theme === 'light') {
          await cmdDialog.screenshot({
            path: path.join(cropsDir, `crop_command_palette.png`),
          });
        }
        await page.keyboard.press('Escape');
        await page.waitForTimeout(150);
      }

      // 4. Help / Shortcuts open
      const helpBtn = page.getByRole('button', { name: /keyboard shortcuts/i });
      if (await helpBtn.isVisible()) {
        await helpBtn.click();
        await page.waitForTimeout(200);
        await page.screenshot({
          path: path.join(outputDir, `help_shortcuts_${theme}_${vp.name}.png`),
          fullPage: false,
        });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(150);
      }

      // 5. Results state
      const searchBtn = page.getByRole('button', { name: /search ats platforms/i });
      if (await searchBtn.isVisible()) {
        await searchBtn.click();
        await page.waitForSelector('.results-table, .cards-mobile-view');
        await page.waitForTimeout(200);

        await page.screenshot({
          path: path.join(outputDir, `results_${theme}_${vp.name}.png`),
          fullPage: true,
        });

        // 6. Filtered results state
        const filterInput = page.getByPlaceholder(/filter by role, company/i);
        if (await filterInput.isVisible()) {
          await filterInput.fill('developer');
          await page.waitForTimeout(150);
          await page.screenshot({
            path: path.join(outputDir, `results_filtered_${theme}_${vp.name}.png`),
            fullPage: true,
          });
          await filterInput.fill('');
        }

        // Component crops on 1440x900 light
        if (vp.name === '1440x900' && theme === 'light') {
          // Summary row crop
          const summaryBar = page.locator('.search-summary-bar');
          if (await summaryBar.isVisible()) {
            await summaryBar.screenshot({
              path: path.join(cropsDir, `crop_summary_row.png`),
            });
          }

          // Toolbar crop
          const toolbar = page.locator('#table-search-input').locator('xpath=ancestor::div[contains(@class, "border-b")]');
          if (await toolbar.isVisible()) {
            await toolbar.screenshot({
              path: path.join(cropsDir, `crop_toolbar.png`),
            });
          }

          // Table header + rows crop
          const table = page.locator('.results-table');
          if (await table.isVisible()) {
            await table.screenshot({
              path: path.join(cropsDir, `crop_results_table.png`),
            });
          }

          // Header crop
          const header = page.locator('header');
          if (await header.isVisible()) {
            await header.screenshot({
              path: path.join(cropsDir, `crop_header.png`),
            });
          }

          // Hero crop on landing
          await page.goto('http://127.0.0.1:8000/?mock=default');
          await page.waitForLoadState('networkidle');
          const hero = page.locator('.hero-region');
          if (await hero.isVisible()) {
            await hero.screenshot({
              path: path.join(cropsDir, `crop_hero.png`),
            });
          }
          const formPanel = page.locator('.search-form-card');
          if (await formPanel.isVisible()) {
            await formPanel.screenshot({
              path: path.join(cropsDir, `crop_form_panel.png`),
            });
          }
        }
      }

      // 7. Loading state
      await page.goto('http://127.0.0.1:8000/?mock=slow');
      await page.waitForLoadState('networkidle');
      const slowSearchBtn = page.getByRole('button', { name: /search ats platforms/i });
      if (await slowSearchBtn.isVisible()) {
        await slowSearchBtn.click();
        await page.waitForTimeout(300);
        await page.screenshot({
          path: path.join(outputDir, `loading_${theme}_${vp.name}.png`),
          fullPage: true,
        });

        if (vp.name === '1440x900' && theme === 'light') {
          const loadingTable = page.locator('.results-table');
          if (await loadingTable.isVisible()) {
            await loadingTable.screenshot({
              path: path.join(cropsDir, `crop_loading_skeleton.png`),
            });
          }
        }
      }

      // 8. No results state
      await page.goto('http://127.0.0.1:8000/?mock=empty');
      await page.waitForLoadState('networkidle');
      const emptySearchBtn = page.getByRole('button', { name: /search ats platforms/i });
      if (await emptySearchBtn.isVisible()) {
        await emptySearchBtn.click();
        await page.waitForTimeout(300);
        await page.screenshot({
          path: path.join(outputDir, `no_results_${theme}_${vp.name}.png`),
          fullPage: true,
        });
        if (vp.name === '1440x900' && theme === 'light') {
          const emptyCard = page.locator('[data-slot="empty"]');
          if (await emptyCard.isVisible()) {
            await emptyCard.screenshot({
              path: path.join(cropsDir, `crop_no_results.png`),
            });
          }
        }
      }

      // 9. Error state
      await page.goto('http://127.0.0.1:8000/?mock=error');
      await page.waitForLoadState('networkidle');
      const errSearchBtn = page.getByRole('button', { name: /search ats platforms/i });
      if (await errSearchBtn.isVisible()) {
        await errSearchBtn.click();
        await page.waitForTimeout(300);
        await page.screenshot({
          path: path.join(outputDir, `error_${theme}_${vp.name}.png`),
          fullPage: true,
        });
      }

      await context.close();
    }
  }

  await browser.close();
  console.log('✓ All 2x screenshots and crops captured successfully.');
}

runCapture().catch((err) => {
  console.error('Capture error:', err);
  process.exit(1);
});
