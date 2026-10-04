import {test,expect} from '@playwright/test';
const stamp=(days:number)=>new Date(Date.now()+days*86400000).toISOString();
async function setup(page:any,{empty=false,failed=false}={}){
 const responses:Record<string,any>={
  '/api/auth/login':{token:'mock-only'},'/api/auth/me':{username:'owner'},'/api/schema':{},
  '/api/data/settings':[{key:'timezone',value:'Asia/Kolkata'}],
  '/api/data/tasks':empty?[]:[{id:'p',title:'Personal task',status:'open',priority:2,tags:['context:personal']},{id:'w',title:'Work task',status:'open',priority:3,tags:['context:work']}],
  '/api/data/learning_topics':empty?[]:[{id:'t',title:'Linear algebra',next_step:'Practise two examples',status:'studying'}],
  '/api/data/workouts':[], '/api/data/journal_entries':[],
  '/api/calendar/agenda':empty?[]:[{id:'e',title:'Team meeting',description:'Context: Work',starts_at:stamp(1),ends_at:stamp(1)}],
  '/api/assistant/morning':{latest_metric_readings:empty?[]:[{metric:'sleep',value:420,unit:'min',recorded_at:stamp(-3)}]},
 };
 await page.route('**/api/**',(route:any)=>{const path=new URL(route.request().url()).pathname;if(failed&&path==='/api/data/tasks')return route.fulfill({status:503,json:{detail:'Unavailable'}});if(path.startsWith('/api/activity/'))return route.fulfill({json:{today:new Date().toISOString().slice(0,10),days:{},active_days:0,total:0,timezone:'Asia/Kolkata'}});return route.fulfill({json:responses[path]||[]})});
 await page.goto('/');await page.getByLabel('Password',{exact:true}).fill('mock-only');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('heading',{name:'Next up',exact:true})).toBeVisible();
}
test('context homes isolate records and label stale readings',async({page})=>{
 await setup(page);await expect(page.getByText('Personal task',{exact:true})).toBeVisible();await expect(page.getByText('Work task',{exact:true})).toHaveCount(0);await expect(page.locator('.context-recovery')).toContainText('420 min');await expect(page.locator('.context-recovery')).toContainText('Older than 24 hours');
 await page.getByRole('group',{name:'Workspace mode'}).getByRole('button',{name:'Work',exact:true}).click();await expect(page.getByText('Work task',{exact:true})).toBeVisible();await expect(page.getByText('Personal task',{exact:true})).toHaveCount(0);await expect(page.getByText('Team meeting',{exact:true})).toBeVisible();
 await page.getByRole('group',{name:'Workspace mode'}).getByRole('button',{name:'Academics',exact:true}).click();await expect(page.getByRole('heading',{name:'Linear algebra'})).toBeVisible();await page.getByRole('button',{name:'Open learning log'}).click();await expect(page.getByRole('heading',{name:'Learning, wherever it happens'})).toBeVisible();
});
test('empty modes offer actions without invented progress',async({page})=>{
 await setup(page,{empty:true});await expect(page.getByText('No open tasks here. A little breathing room.')).toBeVisible();await expect(page.getByText('No sleep reading saved.',{exact:false})).toBeVisible();await expect(page.getByRole('button',{name:'Quick add',exact:true}).first()).toBeEnabled();await expect(page.locator('.activity-summary')).toContainText('0 active days');
});
test('partial service failures keep navigation and other data usable',async({page})=>{
 await setup(page,{failed:true});await expect(page.locator('.context-tasks [role="alert"]')).toContainText('Couldn’t load this section');await expect(page.locator('.context-recovery')).toContainText('420 min');await expect(page.getByRole('button',{name:'Retry',exact:true})).toBeEnabled();await page.getByRole('group',{name:'Workspace mode'}).getByRole('button',{name:'Academics',exact:true}).click();await expect(page.getByRole('heading',{name:'Linear algebra'})).toBeVisible();
});
