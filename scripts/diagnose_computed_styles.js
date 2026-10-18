const { chromium } = require('@playwright/test');

async function diagnose() {
  const browser = await chromium.launch({ channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });

  // Open "More filters" to test panel and platform chips as well
  const moreBtn = page.getByRole('button', { name: /more filters/i });
  if (await moreBtn.isVisible()) {
    await moreBtn.click();
    await page.waitForTimeout(200);
  }

  const elements = [
    { name: 'h1', selector: 'h1' },
    { name: 'lead paragraph', selector: 'h1 + p, .text-lead' },
    { name: 'Role input', selector: 'input#role-input, input[name="keywords"], input[placeholder*="Backend Engineer"]' },
    { name: 'Location input', selector: 'input#location-input, input[name="location"], input[placeholder*="Nigeria"]' },
    { name: 'Search ATS platforms button', selector: 'button[type="submit"]' },
    { name: 'Field label (role)', selector: 'label[for="role-input"], label:has-text("Role or keyword")' },
    { name: 'Suggestion chip', selector: '.suggestion-chip, button:has-text("Backend Engineer")' },
    { name: 'More filters trigger', selector: 'button:has-text("More filters")' },
    { name: 'More filters panel', selector: '[data-slot="collapsible-content"], div:has(button[role="checkbox"])' },
    { name: 'Platform chip', selector: 'button[role="checkbox"], .platform-chip' },
  ];

  console.log('=== COMPUTED STYLES DIAGNOSIS ===\n');

  for (const el of elements) {
    const locator = page.locator(el.selector).first();
    const count = await locator.count();
    if (count === 0) {
      console.log(`[NOT FOUND] ${el.name} (selector: ${el.selector})`);
      continue;
    }

    const info = await locator.evaluate((node) => {
      const computed = window.getComputedStyle(node);
      return {
        tag: node.tagName.toLowerCase(),
        classes: node.className,
        boxSizing: computed.boxSizing,
        width: computed.width,
        height: computed.height,
        lineHeight: computed.lineHeight,
        fontSize: computed.fontSize,
        paddingTop: computed.paddingTop,
        paddingRight: computed.paddingRight,
        paddingBottom: computed.paddingBottom,
        paddingLeft: computed.paddingLeft,
        marginTop: computed.marginTop,
        marginRight: computed.marginRight,
        marginBottom: computed.marginBottom,
        marginLeft: computed.marginLeft,
        borderWidth: computed.borderWidth,
        borderStyle: computed.borderStyle,
        borderColor: computed.borderColor,
      };
    });

    console.log(`--- ${el.name} (${info.tag}) ---`);
    console.log(`Classes: "${info.classes}"`);
    console.log(`Height: ${info.height} (line-height: ${info.lineHeight}, font-size: ${info.fontSize})`);
    console.log(`Padding: T:${info.paddingTop} R:${info.paddingRight} B:${info.paddingBottom} L:${info.paddingLeft}`);
    console.log(`Margin:  T:${info.marginTop} R:${info.marginRight} B:${info.marginBottom} L:${info.marginLeft}`);
    console.log(`Border:  ${info.borderWidth} ${info.borderStyle} ${info.borderColor}\n`);
  }

  await browser.close();
}

diagnose().catch(console.error);
