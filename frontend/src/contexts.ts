export type LifeMode = 'work' | 'academics' | 'personal';
export const modes: LifeMode[] = ['work', 'academics', 'personal'];
export const modeNames = {work:'Work', academics:'Academics', personal:'Personal'};
export const energyNames = {focus:'Focus', light:'Light', quick:'Quick'};
export const moduleMode: Record<string, LifeMode> = {work:'work', academics:'academics', dsa:'academics', personality:'personal', physical:'personal'};
export function recordMode(row: any): LifeMode {
  const tags = (Array.isArray(row.tags) ? row.tags : []).map((s:any)=>String(s).toLowerCase());
  const explicit = tags.find((tag:string)=>tag.startsWith('context:'))?.slice(8);
  if (modes.includes(explicit)) return explicit;
  if (row.project_id) return 'work';
  if (tags.some((s:string)=>['academics','academic','study','dsa','context:academics'].includes(s))) return 'academics';
  if (tags.some((s:string)=>['work','career','context:work'].includes(s))) return 'work';
  return 'personal';
}
export const taskEnergy = (row:any):string => (Array.isArray(row.tags)?row.tags:[]).find((t:any)=>typeof t==='string'&&t.startsWith('energy:'))?.slice(7)||'';
export const taskDefaults = (mode: LifeMode) => ({tags:[`context:${mode}`]});
export const localDay = (date: Date, zone: string) => new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
// Convert wall-clock input in the owner's zone, not the browser's zone. Round-trip
// validation rejects nonexistent DST times instead of silently shifting the event.
export function zonedISO(value:string, zone:string):string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error('Choose a date and time.');
  const target = Date.parse(value+'Z');
  if(!Number.isFinite(target))throw new Error('Choose a valid date and time.');
  let guess=target;
  const parts=(ms:number)=>Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(ms)).map(p=>[p.type,p.value]));
  const wall=(ms:number)=>{const p=parts(ms);return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`};
  for(let i=0;i<4;i++)guess+=target-Date.parse(wall(guess)+'Z');
  if(!Number.isFinite(guess)||wall(guess)!==value)throw new Error('That local time does not exist. Choose another time.');
  // A repeated clock time has two possible instants. Require a non-ambiguous choice.
  if([guess-3600000,guess+3600000].some(t=>wall(t)===value))throw new Error('That time occurs twice when clocks change. Choose a time outside the clock change.');
  return new Date(guess).toISOString();
}
export type CaptureKind = 'task'|'note'|'journal'|'event';
export function parseCapture(text:string, mode:LifeMode, zone:string, now=new Date()) {
  const context:LifeMode = /\b(?:for|at) work\b|\bwork:/i.test(text)?'work':/\bfor (?:uni|college|study)\b|\bacademics?:/i.test(text)?'academics':mode;
  const kind:CaptureKind = /^task:/i.test(text)?'task':/^journal:/i.test(text)?'journal':/^(?:note|idea):/i.test(text)?'note':/\b(meeting|appointment|lecture|class|event)\b/i.test(text)?'event':'task';
  let day='', clock='', hint='';
  const today=localDay(now,zone);
  const dateMatch=text.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  if(dateMatch)day=dateMatch[1];
  else if(/\btomorrow\b/i.test(text))day=new Date(Date.parse(today+'T12:00:00Z')+86400000).toISOString().slice(0,10);
  else if(/\btoday\b/i.test(text))day=today;
  const time=text.match(/\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i) || text.match(/\bat\s+(\d{1,2}):(\d{2})\b/i);
  if(time){let h=Number(time[1]);const m=Number(time[2]||0);const mer=time[3]?.toLowerCase();if(m<60&&((mer&&h>=1&&h<=12)||(!mer&&h<24))){if(mer)h=h%12+(mer==='pm'?12:0);clock=`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;}}
  if(clock&&!day)hint='Choose a date for the time you mentioned.';
  else if(day&&!clock)hint='Choose a time; a date alone is not a deadline time.';
  else if(!day&&!clock)hint='No date recognised. Leave a task unscheduled, or set a date below.';
  return {context,kind,title:text.replace(/^(?:task|note|idea|journal):\s*/i,'').trim(),when:day&&clock?`${day}T${clock}`:'',hint};
}
