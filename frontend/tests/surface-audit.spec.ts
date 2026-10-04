import {test,expect} from '@playwright/test';
const password=process.env.LIFE_OS_TEST_PASSWORD;
test('every module tab loads, editors open, scrollbar and keyboard behavior remain usable',async ({page})=>{
 test.skip(!password,'Disposable local database required');
 test.setTimeout(180000);
 const errors:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await page.getByLabel('Password',{exact:true}).fill(password!);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Start here'})).toBeVisible();
 const visited:string[]=[];
 for(const route of ['home','journal','personality','academics','work','dsa','physical','calendar','tasks','settings']) {
  await page.goto('/#'+route);
  await page.locator('.page-content').waitFor();
  await page.waitForLoadState('networkidle');
  const tabs=page.locator('.page-content > .tabs > button');
  const labels=await tabs.allTextContents();
  for(const label of labels.length?labels:['default']) {
   if(label!=='default')await tabs.filter({hasText:new RegExp('^'+label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$')}).click();
   await page.waitForLoadState('networkidle');
   visited.push(route+': '+label);
   await expect(page.locator('.page-content [role="alert"]')).toHaveCount(0);
   const add=page.locator('.page-content').getByRole('button',{name:/^(Add|New entry|Log workout|New task|Health reading|Event)$/}).first();
   if(await add.count() && await add.isVisible() && await add.isEnabled()) {
    await add.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('dialog').press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
   }
  }
 }
 expect(visited.length).toBeGreaterThan(40);
 console.log('Audited sections:',visited.join(' | '));
 expect(errors).toEqual([]);
 await page.goto('/#settings');
 await page.getByRole('button',{name:'Preferences',exact:true}).click();
 await page.waitForLoadState('networkidle');
 const style=await page.evaluate(()=>({color:getComputedStyle(document.documentElement).scrollbarColor,width:getComputedStyle(document.documentElement).scrollbarWidth}));
 expect(style.width).toBe('thin');expect(style.color).toContain('83, 96, 120');
 await page.screenshot({path:'/tmp/life-os-audit-scrollbar.png',animations:'disabled'});
 await page.locator('main').focus();
 await page.keyboard.press('End');
 await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(0);
 await page.emulateMedia({forcedColors:'active'});
 expect(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollbarColor)).toBe('auto');
});

test('login continuity survives reload and a second tab; sign-out revokes its token',async ({page,context})=>{
 test.skip(!password,'Disposable local database required');
 await page.goto('/');
 await page.getByLabel('Password',{exact:true}).fill(password!);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Start here'})).toBeVisible();
 const token=await page.evaluate(()=>localStorage.getItem('life-os-token'));
 expect(token).toBeTruthy();
 await page.reload();await expect(page.getByRole('heading',{name:'Start here'})).toBeVisible();
 const other=await context.newPage();await other.goto('/');
 await expect(other.getByRole('heading',{name:'Start here'})).toBeVisible();
 await other.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(other.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 const result=await page.request.get('/api/auth/me',{headers:{Authorization:'Bearer '+token}});
 expect(result.status()).toBe(401);
 await page.reload();await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
});

test('module surfaces meet automated accessibility checks',async ({page})=>{
 test.skip(!password || !process.env.LIFE_OS_AXE_SCRIPT,'Requires local owner and an axe-core installation');
 test.setTimeout(120000);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');await page.getByLabel('Password',{exact:true}).fill(password!);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Start here'})).toBeVisible();
 const issues:any[]=[];
 for(const route of ['home','journal','personality','academics','work','dsa','physical','calendar','tasks','settings']) {
  await page.goto('/#'+route);
  await expect(page.locator('main h1')).toHaveText(({home:'Overview',journal:'Journal',personality:'Personal growth',academics:'Academics',work:'Work',dsa:'DSA in Python',physical:'Physical goals',calendar:'Calendar',tasks:'To-do list',settings:'Settings'} as any)[route]);
  await page.waitForLoadState('networkidle');
  await page.addScriptTag({path:process.env.LIFE_OS_AXE_SCRIPT!});
  const result=await page.evaluate(async()=> (await (window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map((v:any)=>({id:v.id,targets:v.nodes.map((n:any)=>n.target)})));
  if(result.length)issues.push({route,violations:result});
 }
 expect(issues).toEqual([]);
});
