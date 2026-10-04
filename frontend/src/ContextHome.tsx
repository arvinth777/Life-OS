import {useEffect, useState} from 'react';
import {Briefcase, BookOpen, Dumbbell, GraduationCap, RefreshCw, Heart, MessageSquare, Plus} from 'lucide-react';
import {api, fmt} from './api';
import {Editor, LoadingRows, Modal, Panel} from './components';
import {CompleteTask, savedFeedback} from './feedback';
import {ActivityGrid} from './ActivityGrid';
import {energyNames, LifeMode, localDay, modeNames, modes, recordMode, taskEnergy} from './contexts';
import {ResetButton} from './Reset';
import {rankTasks} from './Overview';

export function TaskPlacement({task,onRefresh}:any){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function update(key:string,value:string){
    setBusy(true);setError('');
    try{await api('/data/tasks/'+task.id,'PATCH',{tags:[...(task.tags||[]).filter((t:any)=>typeof t!=='string'||!t.startsWith(key+':')),...(value?[`${key}:${value}`]:[])]});savedFeedback('Task updated');onRefresh()}
    catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  return <div className="task-placement">
    <select aria-label={`Context for ${task.title}`} disabled={busy} value={recordMode(task)} onChange={e=>update('context',e.target.value)}>{modes.map(m=><option key={m} value={m}>{modeNames[m]}</option>)}</select>
    <select aria-label={`Energy for ${task.title}`} disabled={busy} value={taskEnergy(task)} onChange={e=>update('energy',e.target.value)}><option value="">Energy: any</option>{Object.entries(energyNames).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
    {error&&<small className="error" role="alert">{error}</small>}
  </div>;
}
export function EnergyFilter({value,onChange}:any){return <div className="energy-filter" role="group" aria-label="Filter by energy">{[['','Any energy'],...Object.entries(energyNames)].map(([v,l])=><button key={v} aria-pressed={value===v} onClick={()=>onChange(v)}>{l}</button>)}</div>}

export function ContextHome(p:any){
  const mode:LifeMode=p.mode;
  const [sources,setSources]=useState<Record<string,{data?:any,error?:string}>>({});
  const [energy,setEnergy]=useState('');
  const [grid,setGrid]=useState<'academics'|'dsa'>('academics');
  const [edit,setEdit]=useState<any>();
  const [review,setReview]=useState(false);
  const [copyError,setCopyError]=useState('');
  const [,setTick]=useState(0);
  const zone=p.settings.timezone||'UTC';
  const now=new Date(),today=localDay(now,zone);
  useEffect(()=>{const id=setInterval(()=>setTick(t=>t+1),60000);return()=>clearInterval(id)},[]);
  useEffect(()=>{
    let active=true;setSources({});
    const start=new Date(),end=new Date(start.getTime()+7*86400000);
    const paths:Record<string,string>={tasks:'/data/tasks',agenda:`/calendar/agenda?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`};
    if(mode==='work'){paths.projects='/data/projects';paths.notes='/data/work_notes';}
    if(mode==='academics'){paths.topics='/data/learning_topics';paths.exams='/data/exams';paths.notes='/data/journal_entries';}
    if(mode==='personal'){paths.workouts='/data/workouts';paths.notes='/data/journal_entries';paths.health='/assistant/morning';}
    for(const [key,path] of Object.entries(paths))api(path).then(data=>{if(active)setSources(s=>({...s,[key]:{data}}))}).catch(e=>{if(active)setSources(s=>({...s,[key]:{error:e.message}}))});
    return()=>{active=false};
  },[mode,p.refresh,today,zone]);
  const rows=(key:string):any[]=>Array.isArray(sources[key]?.data)?sources[key].data:[];
  const status=(key:string)=>sources[key]?.error?<p className="error" role="alert">Couldn’t load this section. <button onClick={p.onRefresh}>Retry</button></p>:!sources[key]?<LoadingRows/>:null;
  const tasks=rankTasks(rows('tasks').filter(t=>recordMode(t)===mode),now,zone);
  const shown=tasks.filter(t=>!energy||taskEnergy(t)===energy);
  const notes=rows('notes').filter(r=>mode==='work'||recordMode(r)===mode).slice(0,3);
  const exams=rows('exams');
  const agenda=rows('agenda').filter(e=>{
    if(e.kind==='tasks')return recordMode(e)===mode;
    if(e.kind==='assignments'||exams.some(x=>x.event_id===(e.master_id||e.id)))return mode==='academics';
    const match=e.description?.match(/^Context: (Work|Academics|Personal)\b/i);
    return match?.[1]?.toLowerCase()===mode;
  }).filter(e=>new Date(e.ends_at||e.starts_at)>=now).slice(0,5);
  const currentTopics=rows('topics').filter(t=>!['retired','demonstrated'].includes(t.status));
  const next=currentTopics.find(t=>t.next_step?.trim());
  const workouts=rows('workouts').filter(w=>new Date(w.performed_at)<=now).sort((a,b)=>b.performed_at.localeCompare(a.performed_at));
  const health=sources.health?.data;
  const lastSleep=health?.latest_metric_readings?.find((r:any)=>r.metric==='sleep'&&new Date(r.recorded_at)<=now);
  const titles={work:['Make room for good work.','Projects and the next actions that move them.'],academics:['Pick up your next chapter.','Your learning, deadlines, and the place you left off.'],personal:['A little time for yourself.','Movement, reflection, and whatever matters to you.']};
  const Icon=mode==='work'?Briefcase:mode==='academics'?GraduationCap:Heart;
  return <div className={`context-home context-${mode}`}>
    <section className="context-intro"><span className="context-emblem"><Icon size={28}/></span><div><h2>{titles[mode][0]}</h2><p>{titles[mode][1]}</p></div><button className="icon" aria-label="Refresh workspace" onClick={p.onRefresh}><RefreshCw size={18}/></button></section>
    <div className="context-layout">
      <section className="context-focus">
        {mode==='work'?<><div className="context-kicker">WORKBENCH</div><h2>{sources.tasks?.data ? tasks.length : "—"} open {tasks.length===1?'action':'actions'}</h2><p>Pick one. Everything else can wait here.</p><button onClick={()=>p.navigate('work')}>Open projects</button></>:mode==='academics'?<><div className="context-kicker">CONTINUE LEARNING</div>{status('topics')||<><h2>{next?.title||'Keep your place.'}</h2><p>{next?.next_step||'Save the next step from a video, lecture, or ChatGPT session.'}</p>{next&&<small>Saved {fmt(next.updated_at)}</small>}<button onClick={()=>p.navigate('academics','learning')}>{next?'Open learning log':'Save a learning step'}</button></>}</>:<><div className="context-kicker">MOVE AT YOUR PACE</div><h2>{workouts[0]?'Ready for your next session?':'Make space for movement.'}</h2><p>{workouts[0]?`Last logged: ${workouts[0].title||'Workout'} · ${fmt(workouts[0].performed_at)}`:'Start a workout when you’re ready. Rest days belong here too.'}</p>{status('workouts')}<button onClick={()=>p.navigate('physical','workouts')}><Dumbbell size={17}/>Open workouts</button></>}
      </section>
      <Panel title="Next up" className="context-tasks" action={<button className="text-button" onClick={()=>p.navigate('tasks')}>All {mode==='academics'?'study':mode} tasks</button>}>
        <p className="muted">Unfinished tasks stay here. Your original deadlines stay unchanged.</p>
        <EnergyFilter value={energy} onChange={setEnergy}/>
        {status('tasks')||<>{shown.length?shown.slice(0,6).map(t=><div key={t.id} className="context-task task-row"><div className="context-task-line"><CompleteTask task={t} onRefresh={p.onRefresh} compact/><button className="task-title" onClick={()=>setEdit({table:'tasks',row:t})}><strong>{t.title}</strong><small>{t.due_at?`Deadline · ${fmt(t.due_at)}`:'No deadline'}</small></button></div><TaskPlacement task={t} onRefresh={p.onRefresh}/></div>):<div className="context-empty"><p>{energy?'No tasks at this energy level.':'No open tasks here. A little breathing room.'}</p><button onClick={p.onCapture}><Plus size={16}/>Quick add</button></div>}{shown.length>6&&<small>Showing 6 of {shown.length}. Open your task list for the rest.</small>}</>}
      </Panel>
      <Panel title={mode==='work'?'Projects in motion':'On the horizon'} className="context-dates">
        {mode==='work'?status('projects')||<>{rows('projects').filter(r=>r.status==='active').slice(0,5).map(r=><button className="context-link" key={r.id} onClick={()=>p.navigate('work')}><Briefcase size={17}/><span><strong>{r.name}</strong><small>{r.deadline?`Deadline · ${fmt(r.deadline)}`:'No deadline'}</small></span></button>)}{!rows('projects').some(r=>r.status==='active')&&<p className="muted">No active projects. Add one in Work.</p>}</>:null}
        {mode==='work'&&<h3 className="context-subheading">Coming up</h3>}
        {(mode==='academics'&&status('exams'))||status('agenda')||<>{agenda.map(e=><button className="context-link context-date" key={`${e.id}-${e.starts_at}`} onClick={()=>p.navigate(e.kind==='tasks'?'tasks':e.kind==='assignments'?'academics':'calendar')}><span className="context-day"><small>{new Intl.DateTimeFormat('en',{timeZone:zone,month:'short'}).format(new Date(e.starts_at))}</small><strong>{new Intl.DateTimeFormat('en',{timeZone:zone,day:'numeric'}).format(new Date(e.starts_at))}</strong></span><span><strong>{e.title}</strong><small>{e.all_day?'All day':fmt(e.starts_at)}</small></span></button>)}{!agenda.length&&<p className="muted">No dates assigned to this mode in the next seven days.</p>}</>}
        <button className="text-button" onClick={()=>p.navigate('calendar')}>All agenda · every context</button>
      </Panel>
      {mode!=='work'&&<div className="context-activity">{mode==='academics'&&<div className="energy-filter" role="group" aria-label="Activity type"><button aria-pressed={grid==='academics'} onClick={()=>setGrid('academics')}>Course study</button><button aria-pressed={grid==='dsa'} onClick={()=>setGrid('dsa')}>DSA practice</button></div>}<ActivityGrid key={mode==='personal'?'physical':grid} kind={mode==='personal'?'physical':grid} refresh={p.refresh}/></div>}
      <Panel title={mode==='work'?'Notes & ideas':mode==='academics'?'Study notes':'Room to reflect'} className="context-notes" action={<button className="text-button" onClick={()=>p.navigate(mode==='work'?'work':'journal',mode==='work'?'work_notes':'')}>Open notes</button>}>
        {status('notes')||<>{notes.map(n=><button className="context-link" key={n.id} onClick={()=>setEdit({table:mode==='work'?'work_notes':'journal_entries',row:n})}><BookOpen size={17}/><span><strong>{n.title||'Untitled thought'}</strong><small>{fmt(n.created_at)}</small></span></button>)}{!notes.length&&<p className="muted">A thought doesn’t need five fields. Use Quick add and start with “Note:” or “Journal:”.</p>}</>}
        {mode==='personal'&&<button onClick={()=>setReview(true)}><MessageSquare size={16}/>Reflect on my week</button>}
      </Panel>
      {mode==='personal'&&<Panel title="Latest sleep record" className="context-recovery">{status('health')||<>{lastSleep?<><strong className="context-reading">{Number(lastSleep.value).toLocaleString(undefined,{maximumFractionDigits:1})} <small>{lastSleep.unit}</small></strong><p className="muted">{fmt(lastSleep.recorded_at)} · {now.getTime()-new Date(lastSleep.recorded_at).getTime()>86400000?'Older than 24 hours':'Latest saved sample'}</p></>:<p className="muted">No sleep reading saved. You can always enter one by hand.</p>}<button className="text-button" onClick={()=>p.navigate('physical')}>Physical goals</button></>}</Panel>}
    </div>
    <div className="context-reset"><div><strong>Coming back after a break?</strong><p className="muted">Choose what still matters, one task at a time.</p></div><ResetButton mode={mode} onRefresh={p.onRefresh}/></div>
    {mode==='personal'&&<button className="context-experiment-link" onClick={()=>p.navigate('personality','experiments')}>Personal experiments · try a small change</button>}
    {edit&&<Editor {...p} table={edit.table} row={edit.row} onSaved={p.onRefresh} onClose={()=>setEdit(undefined)}/>}
    {review&&<Modal title="Reflect on your week" onClose={()=>setReview(false)}><p>Use your existing Life OS connection in ChatGPT. Nothing is sent when you open this panel.</p><blockquote className="review-prompt">Use Life OS to review my last seven days: what went well, what felt difficult, and up to three small adjustments. Use saved records, label missing data, and ask before saving any changes.</blockquote><div className="actions"><button onClick={async()=>{try{await navigator.clipboard.writeText('Use Life OS to review my last seven days: what went well, what felt difficult, and up to three small adjustments. Use saved records, label missing data, and ask before saving any changes.');savedFeedback('Review prompt copied')}catch{setCopyError('Select and copy the prompt above.')}}}>Copy prompt</button><a className="button" href="https://chatgpt.com/g/g-p-6aa79a647e048191bb4ba6add6340a6c/project" target="_blank" rel="noreferrer">Open Life OS in ChatGPT</a></div>{copyError&&<p role="status">{copyError}</p>}</Modal>}
  </div>;
}
