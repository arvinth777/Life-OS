import { test, expect } from '@playwright/test';
const now = new Date();
const stamp = (days: number) => new Date(now.getTime()+days*86400000).toISOString();
const dueTasks = [
  {id:'late',title:'Submit the lab report',priority:3,due_at:stamp(-2),status:'open'},
  {id:'today',title:'Review lecture notes',priority:2,due_at:stamp(0),status:'open'},
];
const tasks = [...dueTasks,{id:'free',title:'Choose a revision resource',priority:4,status:'open'},{id:'future',title:'Prepare presentation',priority:2,due_at:stamp(4),status:'open'}];
async function setup(page: any, options: {empty?: boolean,failed?: boolean} = {}) {
  const responses: Record<string, any> = {
    '/api/auth/login':{token:'mock-only'}, '/api/auth/me':{username:'owner'},
    '/api/schema':{tasks:{editable:true,fields:[{name:'title',type:'text',required:true}]}},
    '/api/data/settings':[{key:'timezone',value:'Asia/Kolkata'}],
    '/api/dashboard':{tasks:options.empty?[]:dueTasks,agenda:[],streaks:{Journal:3,DSA:0,Workout:2},timezone:'Asia/Kolkata'},
    '/api/assistant/morning':{tasks:options.empty?[]:tasks,learning_topics:options.empty?[]:[{id:'t1',title:'Linear algebra',status:'studying',next_step:'Try two examples of matrix multiplication, then explain the order of operations.',updated_at:stamp(-1)}],goals:[],latest_metric_readings: options.empty?[]:[{metric:'sleep',value:420,unit:'min',recorded_at:stamp(-3)},{metric:'heart_rate',value:74,unit:'bpm',recorded_at:stamp(-1)}]},
    '/api/assistant/weekly':{completed_tasks:options.empty?0:8,learning_sessions:options.empty?0:4,workouts:options.empty?0:2,journal_entries:options.empty?0:3,last_successful_phone_delivery:options.empty?null:stamp(-3)},
    '/api/calendar/agenda':options.empty?[]:[{id:'exam1',title:'Linear algebra exam',starts_at:stamp(2),ends_at:stamp(2)},{id:'assignment',kind:'assignments',title:'Submit design assignment',starts_at:stamp(3)}],
    '/api/data/exams':options.empty?[]:[{id:'exam',event_id:'exam1'}],
  };
  await page.route('**/api/**', (route:any) => {
    const path = new URL(route.request().url()).pathname;
    if (options.failed && path==='/api/assistant/morning') return route.fulfill({status:503,json:{detail:'Unavailable'}});
    return route.fulfill({json:responses[path] || []});
  });
  await page.goto('/');
  await page.getByLabel('Password', {exact:true}).fill('mock-only');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Start here'})).toBeVisible();
}

test('overview prioritizes real tasks, dates and learning, with stale watch data labelled',async ({page})=>{
  await setup(page);
  await expect(page.locator('.overview-task strong')).toHaveText(['Submit the lab report','Review lecture notes','Choose a revision resource']);
  await expect(page.getByRole('heading',{name:'Linear algebra',exact:true})).toBeVisible();
  await expect(page.locator('.upcoming-row').first()).toContainText('Exam');
  await expect(page.locator('.overview-signals')).toContainText('Delayed');
  await expect(page.locator('.week-grid')).toContainText('8');
  await expect(page.locator('.health-glance').first()).toContainText('420 min');
  await expect(page.locator('.health-glance').first()).toContainText('Older than 24h');
  await expect(page.getByText('Python practice',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Water today',{exact:true})).toHaveCount(0);
  await page.screenshot({path:'/tmp/life-os-night-overview-desktop.png',fullPage:true,animations:'disabled'});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'/tmp/life-os-night-overview-mobile.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Open learning log'}).click();
  await expect(page.getByRole('heading',{name:'Learning, wherever it happens'})).toBeVisible();
});

test('empty overview offers actions without fabricated progress',async ({page})=>{
  await setup(page,{empty:true});
  await expect(page.getByText('No open tasks in this view.',{exact:true})).toBeVisible();
  await expect(page.getByText('No upcoming dates saved.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Save a learning step'})).toBeVisible();
  await expect(page.locator('.week-grid strong')).toHaveText(['0','0','0','0']);
  await expect(page.locator('.overview-signals')).toContainText('No delivery');
});

test('partial service failure preserves the dashboard and explains limited priorities',async ({page})=>{
  await setup(page,{failed:true});
  await expect(page.locator('.overview-warning')).toContainText('priorities and learning');
  await expect(page.locator('.overview-task strong')).toHaveText(['Submit the lab report','Review lecture notes']);
  await expect(page.getByText('Only tasks due by today are available.',{exact:false})).toBeVisible();
  await expect(page.locator('.upcoming-row')).toHaveCount(2);
  await expect(page.getByRole('button',{name:'Retry',exact:true})).toBeEnabled();
});
