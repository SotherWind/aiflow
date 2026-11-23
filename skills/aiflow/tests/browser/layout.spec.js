const { test, expect, fixture } = require('./helpers');

test('centered controls pass', async ({ page }) => {
  await fixture(page, `<main data-check>
    <span class="btn">Submit</span>
    <span class="tag">Ready</span>
    <div class="inp">Title</div>
  </main>`);
  expect(await page.evaluate(() => window.aiflowLayoutCheck())).toEqual([]);
});

for (const [source, attr, padding, direction] of [
  ['value', 'value="Example"', '25px 12px 0', '偏下'],
  ['placeholder', 'type="search" placeholder="Example"', '0 12px 25px', '偏上'],
]) {
  test(`native input ${source}: reports offset and clipping inside the field`, async ({ page }) => {
    await fixture(page, `<input ${attr} id="field">`,
      `input { box-sizing:border-box; height:40px; font:20px/24px Arial; border:1px solid; padding:${padding}; }`);
    const issues = await page.locator('#field').evaluate(el => window.aiflowLayoutCheck(el));
    expect(issues.some(item => item.includes(direction))).toBe(true);
    expect(issues.some(item => item.includes('裁切'))).toBe(true);
  });
}

test('native inputs: ordinary editable text, blank fields and other control types stay quiet', async ({ page }) => {
  await fixture(page, `<input value="${'Long editable text '.repeat(20)}"><input type="email" placeholder="Email">
    <input class="small"><input type="checkbox" class="small" checked>
    <input type="range" class="small"><input type="hidden" value="Hidden">
    <input type="text" class="small" hidden value="Hidden"><textarea>Multiline</textarea>`,
    'input { box-sizing:border-box; height:40px; width:100px; font:16px/24px Arial; padding:4px 12px; }' +
    '.small { height:15px; padding:10px 0 0; }');
  expect(await page.evaluate(() => window.aiflowLayoutCheck())).toEqual([]);
});

test('native inputs: line height, symmetric padding and a harmless offset do not imply clipping', async ({ page }) => {
  await fixture(page, '<input id="centered" value="Example"><input id="shifted" value="Example">',
    'input { height:44px; box-sizing:border-box; border:1px solid; font:16px/70px Arial; }' +
    '#centered { padding:16px 4px; } #shifted { padding:8px 4px 0; }');
  expect(await page.locator('#centered').evaluate(el => window.aiflowLayoutCheck(el))).toEqual([]);
  const issues = await page.locator('#shifted').evaluate(el => window.aiflowLayoutCheck(el));
  expect(issues).toHaveLength(1);
  expect(issues[0]).toContain('偏下');
});

test('native inputs: use the visible placeholder font, then recheck the live value', async ({ page }) => {
  await fixture(page, '<input id="field" placeholder="Mg">',
    'input { box-sizing:border-box; height:30px; font:14px Arial; padding:0 4px; }' +
    'input::placeholder { font-size:48px; }');
  const field = page.locator('#field');
  const issues = await field.evaluate(el => window.aiflowLayoutCheck(el));
  expect(issues.some(item => item.includes('裁切'))).toBe(true);
  await field.fill('Mg');
  expect(await field.evaluate(el => window.aiflowLayoutCheck(el))).toEqual([]);
});

test('native inputs: password findings identify the control without disclosing its value', async ({ page }) => {
  await fixture(page, '<input id="passcode" type="password" value="private-example">',
    'input { height:40px; box-sizing:border-box; padding:24px 0 0; }');
  const issues = await page.evaluate(() => window.aiflowLayoutCheck());
  expect(issues.some(item => item.includes('passcode') && item.includes('偏下'))).toBe(true);
  expect(issues.join(' ')).not.toContain('private-example');
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
