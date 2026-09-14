import { test, expect } from '@playwright/test';
const password = process.env.LIFE_OS_TEST_PASSWORD;
test('Samsung-only water refreshes without logging and watch coverage stays honest', async ({ page }) => {
  test.skip(!password, 'Local owner login required');
  await page.route('**/api/data/settings', async route => {
    const response = await route.fetch(); const rows = await response.json();
    const row = rows.find((r: any) => r.key === 'water_source');
    if (row) row.value = 'samsung_health'; else rows.push({ key: 'water_source', value: 'samsung_health' });
    await route.fulfill({ response, json: rows });
  });
  let added = 0;
  page.on('request', request => { if (request.url().endsWith('/api/ingest')) added++; });
  await page.goto('/');
  await page.getByLabel('Password', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Physical goals', exact: true }).click();
  const refresh = page.getByRole('button', { name: 'Refresh Samsung Health water total' });
  await expect(refresh).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Add 250 ml of water' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Different amount' })).toHaveCount(0);
  await refresh.click(); await expect(refresh).toBeEnabled(); expect(added).toBe(0);
  await page.getByRole('button', { name: 'Health reading', exact: true }).click();
  await expect(page.getByLabel('Metric').locator('option[value="water"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Watch data', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Heart Rate', exact: true })).toBeVisible();
  await expect(page.getByText('Samsung cloud connection needed · Not connected')).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(38);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.screenshot({ path: '/tmp/life-os-watch-coverage.png', fullPage: true });
});
