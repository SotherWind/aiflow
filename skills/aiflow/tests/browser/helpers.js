const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test: base, expect } = require('@playwright/test');

const skillRoot = path.resolve(__dirname, '../..');
const kitRoot = path.join(skillRoot, 'templates/prototype-kit');
const layoutScript = path.join(kitRoot, 'layout-check.js');
const specScript = path.join(kitRoot, 'spec-check.js');
const parityScript = path.join(skillRoot, 'scripts/parity/parity.js');
const kitCss = readFileSync(path.join(kitRoot, '_src/kit.css'), 'utf8');

const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => route.abort());
    await use(page);
    expect(errors, 'Unexpected browser errors').toEqual([]);
  },
});

async function fixture(page, content, css = '') {
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8">
    <style>${kitCss}\n${css}</style></head><body>${content}</body></html>`);
  await page.addScriptTag({ path: layoutScript });
  await page.addScriptTag({ path: specScript });
  await page.evaluate(() => document.fonts.ready);
}

async function parityPage(page, side) {
  const assets = new Map([
    ['/scripts/parity/kit.html', 'scripts/parity/kit.html'],
    ['/scripts/parity/element-plus.html', 'scripts/parity/element-plus.html'],
    ['/templates/prototype-kit/_src/kit.css', 'templates/prototype-kit/_src/kit.css'],
    ['/templates/prototype-kit/_src/presets/element-plus.css', 'templates/prototype-kit/_src/presets/element-plus.css'],
  ]);
  const libraries = new Map([
    ['https://unpkg.com/vue@3.5.44/dist/vue.global.prod.js', require.resolve('vue/dist/vue.global.prod.js')],
    ['https://unpkg.com/element-plus@2.14.7/dist/index.css', require.resolve('element-plus/dist/index.css')],
    ['https://unpkg.com/element-plus@2.14.7/dist/index.full.min.js', require.resolve('element-plus/dist/index.full.min.js')],
  ]);
  const unexpected = [];
  // Serve only the real sample pages and pinned local dependencies; never use the network.
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    const relative = url.origin === 'http://aiflow.test' && assets.get(url.pathname);
    const file = relative ? path.join(skillRoot, relative) : libraries.get(url.href);
    if (!file) {
      unexpected.push(url.href);
      await route.abort();
      return;
    }
    const contentType = file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : 'text/html';
    await route.fulfill({ path: file, contentType: `${contentType}; charset=utf-8` });
  });
  await page.goto(`http://aiflow.test/scripts/parity/${side === 'kit' ? 'kit.html?preset=element-plus' : 'element-plus.html'}`);
  await page.waitForFunction(() => window.__ready === true);
  await page.evaluate(() => document.fonts.ready);
  await page.addScriptTag({ path: parityScript });
  expect(unexpected, 'Unmapped asset requests').toEqual([]);
  return page.evaluate(side => window.aiflowParityMeasure(side), side);
}

module.exports = { test, expect, fixture, parityPage };
