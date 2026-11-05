const { test, expect, fixture } = require('./helpers');

test('centered controls pass', async ({ page }) => {
  await fixture(page, `<main data-check>
    <span class="btn">Submit</span>
    <span class="tag">Ready</span>
    <div class="inp">Title</div>
  </main>`);
  expect(await page.evaluate(() => window.aiflowLayoutCheck())).toEqual([]);
});

for (const [axis, transform, issue] of [
  ['vertical', 'translateY(7px)', '偏下'],
  ['horizontal', 'translateX(9px)', '偏右'],
]) {
  test(`${axis} text offset is detected`, async ({ page }) => {
    await fixture(page, `<span class="btn"><span style="transform:${transform}">Submit</span></span>`);
    const issues = await page.evaluate(() => window.aiflowLayoutCheck());
    expect(issues.some(item => item.includes(issue))).toBe(true);
  });
}

test('wrapped button labels are detected', async ({ page }) => {
  await fixture(page, '<span class="btn">Submit this form</span>',
    '.btn { width:64px; height:80px; padding:0; white-space:normal; }');
  const issues = await page.evaluate(() => window.aiflowLayoutCheck());
  expect(issues.some(item => item.includes('文字换成了'))).toBe(true);
});

test('overflowing content is detected', async ({ page }) => {
  await fixture(page, '<span class="btn">VeryLongButtonLabel</span>',
    '.btn { width:40px; padding:0; }');
  const issues = await page.evaluate(() => window.aiflowLayoutCheck());
  expect(issues.some(item => item.includes('内容超出控件'))).toBe(true);
});

test('icon and text misalignment is detected', async ({ page }) => {
  await fixture(page, '<span class="btn"><span class="i"></span>Submit</span>',
    '.i { width:14px; height:14px; background:var(--primary); transform:translateY(8px); }');
  const issues = await page.evaluate(() => window.aiflowLayoutCheck());
  expect(issues.some(item => item.includes('图标和文字没对齐'))).toBe(true);
});

test('hidden controls and annotations do not affect layout results', async ({ page }) => {
  await fixture(page, `<span class="btn an">Submit<span class="mk">1</span></span>
    <div hidden><span class="btn" style="width:1px">Hidden label</span></div>
    <div class="dim"><span class="btn" style="width:1px">Annotation</span></div>`);
  expect(await page.evaluate(() => window.aiflowLayoutCheck())).toEqual([]);
});

test('hidden descendant text does not create a false offset', async ({ page }) => {
  await fixture(page, `<span class="btn">Submit
    <span style="position:absolute; left:300px; visibility:hidden">Hidden label</span>
  </span>`);
  expect(await page.evaluate(() => window.aiflowLayoutCheck())).toEqual([]);
});

test('an element passed as the scope is checked too', async ({ page }) => {
  await fixture(page, '<span class="btn" id="target"><span style="transform:translateY(7px)">Submit</span></span>');
  const issues = await page.evaluate(() => window.aiflowLayoutCheck(document.querySelector('#target')));
  expect(issues.some(item => item.includes('偏下'))).toBe(true);
});
