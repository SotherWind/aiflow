const { test, expect, parityPage } = require('./helpers');

test('the preset matches all 70 pinned real-library pairs', async ({ page }) => {
  const kit = await parityPage(page, 'kit');
  const library = await parityPage(page, 'element-plus');
  expect(library.side).toBe('element-plus 2.14.7');
  expect(Object.keys(kit.pairs)).toHaveLength(70);
  expect(Object.values(kit.pairs).every(Boolean)).toBe(true);
  expect(Object.values(library.pairs).every(Boolean)).toBe(true);
  const differences = await page.evaluate(({ kit, library }) => window.aiflowParityCompare(kit, library), { kit, library });
  expect(differences).toEqual([]);
});

test('a real rendered dimension change is detected', async ({ page }) => {
  const library = await parityPage(page, 'element-plus');
  const baseline = await parityPage(page, 'kit');
  const height = baseline.pairs.btn.height;
  await page.locator('[data-pair="btn"] .btn').evaluate((el, height) => { el.style.height = `${height + 4}px`; }, height);
  const kit = await page.evaluate(() => window.aiflowParityMeasure('kit'));
  const differences = await page.evaluate(({ kit, library }) => window.aiflowParityCompare(kit, library), { kit, library });
  expect(differences.some(item => item.startsWith('btn · 高'))).toBe(true);
});

test('missing components are reported instead of skipped', async ({ page }) => {
  const library = await parityPage(page, 'element-plus');
  await parityPage(page, 'kit');
  await page.locator('[data-pair="btn-pri"] .btn').evaluate(el => el.remove());
  const kit = await page.evaluate(() => window.aiflowParityMeasure('kit'));
  const differences = await page.evaluate(({ kit, library }) => window.aiflowParityCompare(kit, library), { kit, library });
  expect(differences.some(item => item.startsWith('btn-pri：') && item.includes('没找到元素'))).toBe(true);
});

test('loading buttons do not enlarge real-library table rows', async ({ page }) => {
  const measure = async side => {
    await parityPage(page, side);
    return page.evaluate(async side => {
      const host = document.createElement('div');
      host.style.width = '700px';
      document.body.appendChild(host);
      let app;
      if (side === 'kit') {
        host.innerHTML = `<table class="tbl">
          <tr><td>Ready</td><td><span class="btn sm">Claim</span></td></tr>
          <tr><td>Loading</td><td><span class="btn sm loading">Claim</span></td></tr>
        </table>`;
      } else {
        app = Vue.createApp({
          data: () => ({ rows: [{ loading: false }, { loading: true }] }),
          template: `<el-table :data="rows" :show-header="false">
            <el-table-column label="Status"><template #default="scope">{{ scope.row.loading ? 'Loading' : 'Ready' }}</template></el-table-column>
            <el-table-column label="Action"><template #default="scope">
              <el-button size="small" :loading="scope.row.loading">Claim</el-button>
            </template></el-table-column>
          </el-table>`,
        });
        app.use(ElementPlus).mount(host);
        await Vue.nextTick();
      }
      await new Promise(resolve => requestAnimationFrame(resolve));
      const rows = [...host.querySelectorAll(side === 'kit' ? '.tbl tr' : '.el-table__row')];
      const heights = rows.map(row => row.getBoundingClientRect().height);
      if (app) app.unmount();
      host.remove();
      return heights;
    }, side);
  };
  const library = await measure('element-plus');
  const kit = await measure('kit');
  expect(library).toHaveLength(2);
  expect(kit).toHaveLength(2);
  for (let index = 0; index < 2; index++) {
    expect(Math.abs(kit[index] - library[index]), `row ${index}: kit ${kit[index]}, library ${library[index]}`).toBeLessThanOrEqual(0.75);
  }
  expect(Math.abs(kit[1] - kit[0]), 'loading must not change row height').toBeLessThanOrEqual(0.75);
});
