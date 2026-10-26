const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, '..', 'docs', 'screenshots');
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

const BANNED_WORDS = [
  'tier',
  'ladder',
  'provenance',
  'sse',
  'dork',
  'ats',
  'serper',
  'cache',
  'adr',
  'engine',
  'workspace',
  'mock',
  'fabricated',
];

async function waitForServer(url, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // wait
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Server at ${url} did not start within ${timeoutMs}ms`);
}

async function run() {
  console.log('\n--- Starting Hero & Marketing Page Visual & Jargon Verification ---');
  const { spawn } = require('child_process');
  let serverProcess = null;

  try {
    const health = await fetch('http://127.0.0.1:8000/health').then((r) => r.ok).catch(() => false);
    if (!health) {
      console.log('Spawning uvicorn server on port 8000...');
      serverProcess = spawn('python', ['-m', 'uvicorn', 'src.api.main:app', '--host', '127.0.0.1', '--port', '8000'], {
        stdio: 'ignore',
      });
      await waitForServer('http://127.0.0.1:8000/health');
      console.log('Server is healthy!');
    }
  } catch (e) {
    console.error('Error starting server:', e);
  }

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000';
  await page.goto(baseUrl);
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });

  // 1. Scan DOM for banned words
  console.log('1. Checking DOM for banned developer jargon on landing page...');
  const textContent = await page.evaluate(() => {
    // Collect visible text from body
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const texts = [];
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement && window.getComputedStyle(node.parentElement).display !== 'none') {
        const t = node.textContent?.trim();
        if (t) texts.push(t);
      }
    }
    return texts.join(' ');
  });

  const foundBanned = [];
  const words = textContent.toLowerCase().split(/[\s,.;:!?/()—"'-]+/);
  for (const bw of BANNED_WORDS) {
    // Match whole word
    if (words.includes(bw)) {
      foundBanned.push(bw);
    }
  }

  if (foundBanned.length > 0) {
    console.error(`  FAIL: Found banned words on landing page: ${foundBanned.join(', ')}`);
  } else {
    console.log('  PASS: Zero banned jargon words detected in visible landing text!');
  }

  // 2. Capture Viewports & Portal Scroll Progress
  console.log('2. Capturing viewports and scroll states...');
  const viewports = [
    { name: '1920x1080', width: 1920, height: 1080 },
    { name: '1440x900', width: 1440, height: 900 },
    { name: '1024x768', width: 1024, height: 768 },
    { name: '768x1024', width: 768, height: 1024 },
    { name: '390x844', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);

    const shotPath = path.join(SCREENSHOTS_DIR, `hero_${vp.name}_p0.png`);
    await page.screenshot({ path: shotPath });
    console.log(`  Captured: ${shotPath}`);

    if (vp.name === '1920x1080') {
      // Scroll to mid-portal (progress ~0.5)
      await page.evaluate(() => window.scrollTo(0, window.innerHeight * 0.9));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_1920x1080_p05.png`) });

      // Scroll to revealed search form (progress ~1.0)
      await page.evaluate(() => window.scrollTo(0, window.innerHeight * 1.8));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_1920x1080_p10.png`) });
    }
  }

  // 3. Test Mobile Touch Picker (any-pointer: coarse)
  console.log('3. Testing mobile touch picker (390x844)...');
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto(baseUrl);
  await mobilePage.waitForLoadState('networkidle');
  await mobilePage.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_mobile_touch_390x844.png`) });
  await mobileContext.close();

  // 4. Test Reduced Motion Fallback
  console.log('4. Testing reduced motion fallback...');
  const reducedMotionContext = await browser.newContext({
    reducedMotion: 'reduce',
    viewport: { width: 1440, height: 900 },
  });
  const rmPage = await reducedMotionContext.newPage();
  await rmPage.goto(baseUrl);
  await rmPage.waitForLoadState('networkidle');
  const motionMode = await rmPage.locator('[data-gp-motion]').getAttribute('data-gp-motion');
  console.log(`  Reduced-motion attribute data-gp-motion: "${motionMode}"`);
  await rmPage.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_reduced_motion.png`) });
  await reducedMotionContext.close();

  // 5. Test Font Timeout Static Fallback
  console.log('5. Testing font timeout fallback...');
  const fontBlockedContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const fontPage = await fontBlockedContext.newPage();
  // Block Geist font woff2 files so font loading promise fails/times out
  await fontPage.route('**/*.woff2', (route) => route.abort());
  await fontPage.route('**/*.woff', (route) => route.abort());
  await fontPage.goto(baseUrl);
  // Wait 1.8s for font timeout (~1.6s)
  await fontPage.waitForTimeout(1900);
  await fontPage.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_font_timeout_fallback.png`) });
  console.log('  Captured font timeout static fallback.');
  await fontBlockedContext.close();

  // 6. Test Keyboard Navigation & Focus Order
  console.log('6. Testing keyboard access & focus order...');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(baseUrl);
  await page.waitForLoadState('networkidle');

  // Tab through header
  await page.keyboard.press('Tab'); // Logo button
  const activeTag1 = await page.evaluate(() => document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent);
  console.log(`  Tab 1 active element: "${activeTag1?.trim()}"`);

  await page.keyboard.press('Tab'); // How it works
  await page.keyboard.press('Tab'); // Where we search
  await page.keyboard.press('Tab'); // Why Bottom Pot
  await page.keyboard.press('Tab'); // Theme toggle
  await page.keyboard.press('Tab'); // Start searching CTA
  const activeCTA = await page.evaluate(() => document.activeElement?.textContent?.trim());
  console.log(`  Tab into CTA: "${activeCTA}"`);

  // Press Enter on Start searching to jump into revealed form
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, `hero_after_enter_cta.png`) });

  console.log('--- Verification Complete ---\n');
  await browser.close();
  if (serverProcess) {
    serverProcess.kill();
  }
}

run().catch((err) => {
  console.error('Verification script failed:', err);
  process.exit(1);
});
