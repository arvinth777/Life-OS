import { test, expect } from '@playwright/test';

test.beforeEach(async ({page}) => {
  // Never let the fixture access an actual service, even if local settings exist.
  await page.route('**/api/**', route => route.fulfill({json: []}));
});

test('tab marker tracks selection and resize; modal dismiss restores focus', async ({page}) => {
  await page.goto('/tests/motion.html');
  const marker = page.locator('.tab-marker');
  await page.getByRole('button', {name:'Progress and history', exact:true}).click();
  await expect(page.getByRole('button', {name:'Progress and history', exact:true})).toHaveAttribute('aria-pressed', 'true');
  async function aligned() {
    return page.locator('.motion-tabs').evaluate(el => {
      const a = el.querySelector('button.active')!.getBoundingClientRect();
      const b = el.querySelector('.tab-marker')!.getBoundingClientRect();
      return Math.abs(a.left - b.left) < 1 && Math.abs(a.width - b.width) < 1;
    });
  }
  await expect.poll(aligned).toBe(true);
  await page.setViewportSize({width:390, height:844});
  await page.getByRole('button', {name:'Personal targets', exact:true}).click();
  await expect.poll(aligned).toBe(true);
  expect(await marker.evaluate(el => getComputedStyle(el).transitionDuration)).not.toBe('0s');
  await page.getByRole('button', {name:'Open editor'}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByLabel('Goal', {exact:true})).toBeFocused();
  await page.getByLabel('Goal', {exact:true}).press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', {name:'Open editor'})).toBeFocused();
  await page.getByRole('button', {name:'Open editor'}).click();
  await page.getByRole('button', {name:'Close', exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('loading, confirmed completion and error feedback reflect the actual request', async ({page}) => {
  let release: (() => void) | undefined;
  await page.route('**/api/data/projects', async route => {
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({json:[{id:'p1', title:'Reading plan'}]});
  });
  await page.goto('/tests/motion.html');
  await expect(page.getByRole('status', {name:'Loading your records…'})).toBeVisible();
  await expect(page.getByText('No Projects yet.')).toHaveCount(0);
  await expect.poll(() => !!release).toBe(true); release!();
  await expect(page.getByText('Reading plan')).toBeVisible();
  await expect(page.locator('.loading-rows')).toHaveCount(0);
  await page.route('**/api/tasks/motion-task/complete', route => route.fulfill({status:409,json:{detail:'Complete the subtasks first'}}));
  const complete = page.locator('.complete-action');
  await complete.click();
  await expect(page.getByRole('alert')).toHaveText('Complete the subtasks first');
  await expect(page.locator('.save-receipt')).toHaveCount(0);
  let requests = 0; release = undefined;
  await page.route('**/api/tasks/motion-task/complete', async route => {
    requests++;
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({json:{ok:true}});
  });
  await complete.click();
  await expect(complete).toBeDisabled();
  await expect(complete).toHaveAttribute('aria-busy','true');
  await expect(page.locator('.save-receipt')).toHaveCount(0);
  await expect.poll(() => !!release).toBe(true); release!();
  await expect(page.locator('.save-receipt')).toContainText('Task completed');
  await expect(page.locator('.task-row')).toHaveCount(0);
  expect(requests).toBe(1);
  await page.getByRole('button', {name:'Dismiss confirmation'}).click();
  await expect(page.locator('.save-receipt')).toHaveCount(0);
  await page.getByRole('button', {name:'Update reading'}).click();
  await expect(page.locator('.metric-value')).toHaveText('17');
});

test('reduced motion keeps feedback functional with no animated surfaces', async ({page}) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/tests/motion.html');
  await page.getByRole('button', {name:'Save confirmation'}).click();
  await page.getByRole('button', {name:'Open editor'}).click();
  for (const selector of ['dialog', '.metric-value', '.chart-line', '.save-receipt', '.success-pixels i']) {
    const names = await page.locator(selector).evaluateAll(els => els.map(el => getComputedStyle(el).animationName));
    expect(names.every(name => name === 'none')).toBe(true);
  }
  await page.getByLabel('Goal', {exact:true}).press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
