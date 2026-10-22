// scripts/lint_css_cascade.js
// Guardrail: Fails if any CSS outside @layer contains element-selector or universal resets
// (*, button, input, select, textarea, h1 to h6, p, ul, ol, table, a).

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const srcDir = path.resolve(projectRoot, 'frontend', 'src');

function getCssFiles(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const fullPath = path.resolve(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getCssFiles(fullPath));
    } else if (file.endsWith('.css')) {
      results.push(fullPath);
    }
  }
  return results;
}

const FORBIDDEN_ELEMENT_SELECTORS = [
  '*',
  'button',
  'input',
  'select',
  'textarea',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'p',
  'ul',
  'ol',
  'table',
  'a',
];

function checkCssFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const relativePath = path.relative(projectRoot, filePath);

  // Remove comments
  const cleanContent = content.replace(/\/\*[\s\S]*?\*\//g, '');

  // Extract content outside @layer blocks
  let outsideLayer = '';
  let depth = 0;
  let inLayer = false;
  let i = 0;

  while (i < cleanContent.length) {
    // Check for @layer
    if (!inLayer && cleanContent.slice(i, i + 6) === '@layer') {
      inLayer = true;
      i += 6;
      continue;
    }

    const char = cleanContent[i];

    if (inLayer) {
      if (char === '{') {
        depth++;
      } else if (char === '}') {
        depth--;
        if (depth === 0) {
          inLayer = false;
        }
      }
    } else {
      outsideLayer += char;
    }
    i++;
  }

  // Parse rules in outsideLayer
  const errors = [];
  // Match selector { ... }
  const ruleRegex = /([^{};]+)\s*\{([^}]*)\}/g;
  let match;

  while ((match = ruleRegex.exec(outsideLayer)) !== null) {
    const selector = match[1].trim();

    // Skip at-rules like @import, @theme, @keyframes, @media
    if (selector.startsWith('@')) continue;

    // Split compound selectors: e.g. "button, input, select"
    const subSelectors = selector.split(',').map((s) => s.trim());

    for (const sub of subSelectors) {
      // Check for standalone * or element selector at start of rule
      for (const forbidden of FORBIDDEN_ELEMENT_SELECTORS) {
        // Match exact selector or with pseudo-classes/elements: e.g., "button", "input:focus", "*", "a:hover"
        const pattern = new RegExp(`(^|[\\s>+~])${forbidden === '*' ? '\\*' : forbidden}(\\s*[:.\\[\\s>+~]|$)`, 'i');
        if (pattern.test(sub)) {
          // If it is a class selector like .button or .table-desktop-view, skip
          if (sub.startsWith('.') || sub.includes('.' + forbidden)) {
            continue;
          }
          errors.push({
            file: relativePath,
            selector: sub,
            element: forbidden,
          });
        }
      }
    }
  }

  return errors;
}

const cssFiles = getCssFiles(srcDir);
let allErrors = [];

for (const file of cssFiles) {
  const fileErrors = checkCssFile(file);
  allErrors = allErrors.concat(fileErrors);
}

if (allErrors.length > 0) {
  console.error('\n❌ Cascade Lint Error: Element/universal selector found outside @layer:');
  for (const err of allErrors) {
    console.error(`   - ${err.file}: "${err.selector}" targets <${err.element}> without @layer wrapper.`);
  }
  console.error('\nAll base element resets and typography rules MUST live inside `@layer base`.');
  process.exit(1);
} else {
  console.log('✓ Cascade lint passed: all base element styles and universal resets are properly scoped inside @layer.');
  process.exit(0);
}
