const { test, expect, fixture } = require('./helpers');

test('controls using design tokens pass', async ({ page }) => {
  await fixture(page, `<main data-check>
    <span class="btn pri">Submit</span><span class="tag success">Ready</span>
    <div class="inp">Title</div><p>Body text</p>
  </main>`);
  expect(await page.evaluate(() => window.aiflowSpecCheck())).toEqual([]);
});

for (const [name, style, message] of [
  ['text color', 'color:rgb(3, 81, 123)', '文字颜色'],
  ['background', 'background:rgb(3, 81, 123)', '背景色'],
  ['border', 'border-color:rgb(3, 81, 123)', '边框色'],
  ['font size', 'font-size:19px', '字号'],
  ['font family', 'font-family:monospace', '字体不是规范字体'],
  ['radius', 'border-radius:11px', '圆角'],
  ['height', 'height:46px', '按钮高'],
]) {
  test(`non-token ${name} is detected`, async ({ page }) => {
    await fixture(page, `<main data-check><span class="btn" style="${style}">Submit</span></main>`);
    const issues = await page.evaluate(() => window.aiflowSpecCheck());
    expect(issues.some(item => item.includes(message))).toBe(true);
  });
}

test('pseudo-element colors are checked', async ({ page }) => {
  await fixture(page, '<main data-check><span class="btn">Submit</span></main>',
    '.btn::before { content:""; display:block; width:12px; height:12px; background:rgb(3,81,123); }');
  const issues = await page.evaluate(() => window.aiflowSpecCheck());
  expect(issues.some(item => item.includes('::before 背景色'))).toBe(true);
});

test('hidden elements, annotation layers and opt-outs are ignored', async ({ page }) => {
  await fixture(page, `<main data-check>
    <span class="btn">Submit</span>
    <span hidden style="color:rgb(3,81,123)">Hidden</span>
    <span class="mk" style="color:rgb(3,81,123)">1</span>
    <span data-nocheck style="color:rgb(3,81,123)">Excluded</span>
  </main>`);
  expect(await page.evaluate(() => window.aiflowSpecCheck())).toEqual([]);
});

test('nested scopes do not double count violations', async ({ page }) => {
  await fixture(page, `<main data-check><div data-check>
    <span class="bad">One</span><span class="bad">Two</span>
  </div></main>`, '.bad { color:rgb(3,81,123); }');
  const issues = await page.evaluate(() => window.aiflowSpecCheck());
  expect(issues).toHaveLength(1);
  expect(issues[0]).toContain('同类共 2 处');
});

test('missing UI scopes do not pass silently', async ({ page }) => {
  await fixture(page, '<p>No UI scope</p>');
  const issues = await page.evaluate(() => window.aiflowSpecCheck());
  expect(issues).toHaveLength(1);
  expect(issues[0]).toContain('没有可查的界面区域');
});

test('the UI scope root itself is inspected', async ({ page }) => {
  await fixture(page, '<span data-check class="btn" style="height:46px">Submit</span>');
  const issues = await page.evaluate(() => window.aiflowSpecCheck());
  expect(issues.some(item => item.includes('按钮高'))).toBe(true);
});

test('exported design rules also check an implementation root', async ({ page }) => {
  await fixture(page, '<main data-check><span class="btn">Submit</span></main>');
  const config = await page.evaluate(() => window.aiflowSpecConfig());
  await fixture(page, '<main id="app"><span class="btn" style="height:46px">Submit</span></main>',
    ':root { --check-btn-heights:46; }');
  const issues = await page.evaluate(config => window.aiflowSpecCheck(config, '#app'), config);
  expect(issues.some(item => item.includes('按钮高 46px'))).toBe(true);
});
