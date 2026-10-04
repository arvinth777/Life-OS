import { test, expect } from '@playwright/test';
// Run against a production build: LIFE_OS_PRODUCTION_TEST=1 LIFE_OS_UI_URL=http://127.0.0.1:4173
// API calls are intercepted; no credentials or real records are used.
test.skip(!process.env.LIFE_OS_PRODUCTION_TEST, "Requires the configured production build.");
test('configured production login hides server setup and reports failed sign-in', async ({page}) => {
  await page.route('**/api/**', route => route.fulfill({status:401,json:{detail:'Incorrect username or password'}}));
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Welcome back.'})).toBeVisible();
  await expect(page.getByText('API connection', {exact:true})).toHaveCount(0);
  await page.setViewportSize({width:390, height:844});
  await page.getByLabel('Password', {exact:true}).fill('test-only-not-a-password');
  await page.getByRole('button', {name:'Sign in', exact:true}).click();
  await expect(page.getByRole('alert')).toHaveText('Incorrect username or password');
  await expect(page.getByRole('button', {name:'Sign in', exact:true})).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel('Password', {exact:true}).fill('');
  await page.screenshot({path:'/tmp/life-os-login-mobile.png',fullPage:true});
});

test('production workspace renders and opens its actual editor', async ({page}) => {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const responses: Record<string, unknown> = {
      '/api/auth/login': {token:'local-mocked-session'},
      '/api/auth/me': {username:'owner'},
      '/api/schema': { tasks:{editable:true,fields:[{name:'title',type:'text',required:true}]} },
      '/api/data/settings': [{key:'timezone',value:'Asia/Kolkata'}],
      '/api/dashboard': {tasks:[{id:'task1',title:'Prepare for the week',priority:2}], agenda:[],reviews_due:0,streaks:{Journal:4,DSA:2,Workout:3},timezone:'Asia/Kolkata'},
    };
    return route.fulfill({json:responses[path] || []});
  });
  await page.goto('/');
  await page.getByLabel('Password', {exact:true}).fill('test-only-not-a-password');
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading', {name:'Your focus today'})).toBeVisible();
  await page.screenshot({path:'/tmp/life-os-workspace-motion.png',fullPage:true});
  await page.getByRole('button', {name:'New task',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog').getByLabel(/Title/)).toBeFocused();
  await page.getByRole('dialog').getByLabel(/Title/).press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', {name:'New task',exact:true})).toBeFocused();
});
