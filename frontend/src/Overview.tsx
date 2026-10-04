import { useEffect, useState } from 'react';
import { ArrowUpRight, BookOpen, CalendarDays, Check, Clock3, GraduationCap, Plus, Radio, RefreshCw, Target } from 'lucide-react';
import { api, fmt } from './api';
import { LoadingRows, Panel } from './components';
import { CompleteTask } from './feedback';
import { NightScene } from './NightScene';

type Source = { data?: any; error?: string; loading?: boolean };
export const dayKey = (date: string | Date, zone: string) => new Intl.DateTimeFormat('en-CA', {timeZone:zone, year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(date));
export function rankTasks(tasks: any[], now: Date, zone: string) {
  const today = dayKey(now, zone);
  const bucket = (t: any) => !t.due_at ? 2 : dayKey(t.due_at, zone) < today ? 0 : dayKey(t.due_at, zone) === today ? 1 : 3;
  return tasks.filter(t => t.status !== 'done').slice().sort((a,b) => bucket(a)-bucket(b) || (b.priority||0)-(a.priority||0) || (a.due_at || '9999').localeCompare(b.due_at || '9999'));
}
export function Overview({refresh, onRefresh, navigate, onQuick, settings}: any) {
  const [sources, setSources] = useState<Record<string, Source>>({});
  const [, setTick] = useState(0);
  const [wakeCount, setWakeCount] = useState(0);
  useEffect(() => { // Reevaluate day boundaries while the tab stays open.
    const timer = window.setInterval(() => setTick(n => n + 1), 60000);
    const wake = () => { if (!document.hidden) { setTick(n => n + 1); setWakeCount(n => n + 1); } };
    document.addEventListener('visibilitychange', wake);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', wake); };
  }, []);
  const zone = settings.timezone || 'UTC';
  const now = new Date();
  const today = dayKey(now, zone);
  useEffect(() => {
    let active = true;
    const at = new Date();
    const paths = {
      day: '/dashboard', brief: '/assistant/morning', week: '/assistant/weekly',
      agenda: `/calendar/agenda?start=${encodeURIComponent(at.toISOString())}&end=${encodeURIComponent(new Date(at.getTime()+7*86400000).toISOString())}`,
      exams: '/data/exams', reminders: '/reminders',
    };
    for (const [key,path] of Object.entries(paths)) {
      setSources(s => ({...s,[key]:{...s[key],loading:true,error:undefined}}));
      api(path).then(data => {
        if (['day','brief','week'].includes(key) && (Array.isArray(data) || !data || typeof data !== 'object')) throw new Error('Unexpected response');
        if (active) setSources(s => ({...s,[key]:{data,loading:false}}));
      }).catch(() => { if (active) setSources(s => ({...s,[key]:{...s[key],loading:false,error:'Could not refresh'}})); });
    }
    return () => { active = false; };
  }, [refresh, today, zone, wakeCount]);
  const day = sources.day?.data;
  const brief = sources.brief?.data;
  const week = sources.week?.data;
  const tasks = rankTasks(brief?.tasks || day?.tasks || [], now, zone).slice(0,3);
  const overdue = day?.tasks?.filter((t:any) => t.due_at && dayKey(t.due_at,zone)<today).length;
  const due = day?.tasks?.filter((t:any) => t.due_at && dayKey(t.due_at,zone)===today).length;
  const upcoming = (sources.agenda?.data || []).filter((e:any) => (new Date(e.starts_at) >= now || (e.ends_at && new Date(e.ends_at)>now))).slice(0,5);
  const nextEvent = (day?.agenda || []).find((e:any) => new Date(e.ends_at || e.starts_at) > now);
  const topic = brief?.learning_topics?.find((t:any) => t.next_step?.trim() && !['retired','demonstrated'].includes(t.status));
  const goals = (brief?.goals || []).slice(0,2);
  const health = ['sleep','heart_rate'].flatMap(metric => {
    const reading = brief?.latest_metric_readings?.find((r:any) => r.metric===metric && new Date(r.recorded_at)<=now);
    return reading ? [reading] : [];
  });
  const phone = week?.last_successful_phone_delivery || brief?.last_successful_phone_delivery;
  const phoneStale = phone && now.getTime()-new Date(phone).getTime()>86400000;
  const failed = Object.entries(sources).filter(([,s])=>s.error).map(([k])=>({day:'today’s summary',brief:'priorities and learning',week:'weekly activity',agenda:'upcoming dates',exams:'exam labels',reminders:'reminders'}[k]));
  const placeholder = (key: string) => sources[key]?.error ? <p className="muted">This section couldn’t load. Try refreshing.</p> : <LoadingRows />;
  const when = (date:string) => dayKey(date,zone) < today ? 'Overdue' : dayKey(date,zone) === today ? 'Today' : fmt(date);
  const reminders = (sources.reminders?.data || []).filter((r:any)=>r.kind!=='water').slice(0,2);
  return <div className="overview">
    {failed.length > 0 && <div className="notice overview-warning" role="status"><span>Couldn’t refresh {failed.join(', ')}. Previously loaded information may be out of date.</span><button onClick={onRefresh}><RefreshCw size={15}/>Retry</button></div>}
    <section className="overview-welcome">
      <div><span className="eyebrow">A LITTLE CLARITY FOR YOUR DAY</span><h2>{overdue ? 'A few things need your attention.' : nextEvent ? 'Your day has a shape.' : 'Choose what moves you forward.'}</h2><p>{overdue ? `${overdue} overdue ${overdue===1?'task is':'tasks are'} waiting. Start small, then make room for what’s next.` : 'Your plans, your next step, and the progress you’ve actually saved.'}</p><div className="overview-shortcuts"><button className="primary" onClick={()=>onQuick('tasks')}><Plus size={16}/>New task</button><button onClick={()=>onQuick('journal_entries')}><BookOpen size={16}/>Capture a thought</button></div></div>
      <NightScene />
    </section>
    <div className="overview-freshness"><small>From your saved records · {sources.day?.loading ? "Refreshing…" : "Refresh to check for changes"}</small><button className="text-button" aria-label="Refresh overview" disabled={Object.values(sources).some(s=>s.loading)} onClick={onRefresh}><RefreshCw size={14}/>Refresh</button></div>
    <div className="overview-signals" aria-label="Today at a glance">
      <button onClick={()=>navigate('tasks')}><span className="signal-icon amber"><Clock3 size={18}/></span><span><strong>{due ?? '—'}</strong><small>Tasks due today</small></span><ArrowUpRight size={15}/></button>
      <button onClick={()=>navigate('tasks')}><span className="signal-icon rose"><Target size={18}/></span><span><strong>{overdue ?? '—'}</strong><small>Overdue tasks</small></span><ArrowUpRight size={15}/></button>
      <button onClick={()=>navigate('calendar')}><span className="signal-icon blue"><CalendarDays size={18}/></span><span><strong>{day?.agenda?.filter((e:any)=>new Date(e.ends_at||e.starts_at)>now).length ?? '—'}</strong><small>Events remaining today</small></span><ArrowUpRight size={15}/></button>
      <button onClick={()=>navigate('physical')}><span className="signal-icon teal"><Radio size={18}/></span><span><strong className="signal-word">{phone ? phoneStale?'Delayed':'Received' : week||brief?'No delivery':'—'}</strong><small>{phone ? `Last delivery · ${fmt(phone)}` : 'Watch delivery status'}</small></span><ArrowUpRight size={15}/></button>
    </div>
    <div className="overview-columns"><div>
      <Panel title="Start here" action={<button className="text-button" onClick={()=>navigate('tasks')}>All tasks <ArrowUpRight size={15}/></button>}>
        <p className="section-caption">{!brief && sources.brief?.error ? "Only tasks due by today are available. Retry to include unscheduled and upcoming work." : "Overdue first, then today, then your highest-priority unscheduled tasks."}</p>
        {!(brief||day) ? placeholder('brief') : tasks.length ? tasks.map(task=><div className="task-row overview-task" key={task.id}><CompleteTask task={task} compact onRefresh={onRefresh}/><div><strong>{task.title}</strong><small>{task.due_at ? `${when(task.due_at)}${dayKey(task.due_at,zone)<=today?' · '+fmt(task.due_at):''}`:'No deadline · choose a time in To-do list'}</small></div><span className={'priority p'+task.priority}>{['','Low','Normal','High','Urgent'][task.priority]}</span></div>) : <div className="overview-empty"><Check size={24}/><div><strong>{brief ? "No open tasks in this view." : "No tasks due by today."}</strong><p>Add a small next action, or leave the space clear.</p><button className="text-button" onClick={()=>onQuick('tasks')}>Choose a next action <Plus size={14}/></button></div></div>}
        {brief?.tasks?.length>=40 && <small>Priorities selected from the first 40 open tasks. Open All tasks for the complete list.</small>}
      </Panel>
      <Panel title="Coming up" action={<button className="text-button" onClick={()=>navigate('calendar')}>Calendar <ArrowUpRight size={15}/></button>}>
        <p className="section-caption">The next seven days · events, exams, and deadlines.</p>
        {!sources.agenda?.data ? placeholder('agenda') : upcoming.length ? upcoming.map((e:any)=>{
          const exam = sources.exams?.data?.some((x:any)=>x.event_id===e.id || x.event_id===e.master_id);
          const kind = exam ? 'Exam' : e.kind==='tasks'?'Task deadline':e.kind==='assignments'?'Assignment':'Event';
          return <button className="upcoming-row" key={`${e.kind||'event'}-${e.id}-${e.starts_at}`} onClick={()=>navigate(e.kind==='tasks'?'tasks':e.kind==='assignments'?'academics':'calendar')}><span className={'date-tile '+(exam?'exam-date':'')}><small>{new Intl.DateTimeFormat('en',{timeZone:zone,month:'short'}).format(new Date(e.starts_at))}</small><strong>{new Intl.DateTimeFormat('en',{timeZone:zone,day:'numeric'}).format(new Date(e.starts_at))}</strong></span><span><strong>{e.title}</strong><small>{kind} · {e.all_day?'All day':fmt(e.starts_at)}</small></span><ArrowUpRight size={16}/></button>;
        }) : <div className="overview-empty"><CalendarDays size={24}/><div><strong>No upcoming dates saved.</strong><p>Add an event, or share your exam timetable in your Life OS ChatGPT project.</p><button className="text-button" onClick={()=>onQuick('calendar_events')}>Add an event <Plus size={14}/></button></div></div>}
      </Panel>
    </div><div>
      <section className="overview-learning"><span className="eyebrow"><GraduationCap size={15}/>PICK UP WHERE YOU LEFT OFF</span>{!brief ? placeholder('brief') : topic ? <><h2>{topic.title}</h2><p>{topic.next_step}</p><small>Saved next step · {fmt(topic.updated_at)}</small><button onClick={()=>navigate('academics','learning')}>Open learning log <ArrowUpRight size={16}/></button></> : <><h2>Learn anywhere. Keep your place here.</h2><p>Save the next step from a chat, lecture, or video so you know where to return.</p><button onClick={()=>onQuick('learning_topics')}>Save a learning step <Plus size={16}/></button></>}</section>
      <Panel title="Your last seven days">
        {!week ? placeholder('week') : <><div className="week-grid">{[['completed_tasks','Tasks finished'],['learning_sessions','Learning sessions'],['workouts','Workouts logged'],['journal_entries','Journal entries']].map(([key,label])=><div key={key}><strong>{week[key] ?? 0}</strong><span>{label}</span></div>)}</div><small>Saved activity through today. Unlogged activity isn’t counted.</small></>}
        {day?.streaks && <div className="overview-streaks">{Object.entries(day.streaks).map(([name,count]:any)=><span key={name}>{name}<strong>{count}d</strong></span>)}</div>}
      </Panel>
      {health.length>0 && <Panel title="Latest health records" action={<button className="text-button" onClick={()=>navigate('physical')}>Details <ArrowUpRight size={14}/></button>}>
        {health.map((r:any)=><div className="health-glance" key={r.metric}><div><span>{r.metric==='sleep'?'Sleep record':'Heart-rate sample'}</span><strong>{Number(r.value).toLocaleString(undefined,{maximumFractionDigits:2})} <small>{r.unit}</small></strong></div><small>{fmt(r.recorded_at)}{now.getTime()-new Date(r.recorded_at).getTime()>86400000?' · Older than 24h':''}</small></div>)}
        <small>Latest saved samples, not daily averages.</small>
      </Panel>}
      {goals.length>0 && <Panel title="Working toward">{goals.map((g:any)=><button className="goal-link" key={g.id} onClick={()=>navigate(g.domain==='work'?'work':g.domain==='physical'?'physical':'academics','goals')}><Target size={17}/><span><strong>{g.title}</strong><small>{g.target_date?'Target · '+g.target_date:'No target date'}</small></span><ArrowUpRight size={14}/></button>)}</Panel>}
    </div></div>
    {reminders.length>0 && <div className="overview-nudges">{reminders.map((r:any)=><button key={r.id} onClick={()=>r.kind==='journal'?onQuick('journal_entries'):navigate('tasks')}><BookOpen size={17}/><span>{r.title}</span><ArrowUpRight size={15}/></button>)}</div>}
  </div>;
}
