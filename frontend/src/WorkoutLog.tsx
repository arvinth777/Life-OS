import React,{useEffect,useState} from 'react';
import {Play,Square,Plus,Pencil,Trophy,Trash2} from 'lucide-react';
import {api,fmt} from './api';
import {Panel,Editor,Empty} from './components';
import {savedFeedback} from './feedback';
import {ActivityGrid} from './ActivityGrid';

function Elapsed({start,end}:{start:string;end?:string}) {
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{if(end)return;const timer=setInterval(()=>setNow(Date.now()),1000);return ()=>clearInterval(timer)},[end]);
  const seconds=Math.max(0,Math.floor(((end?new Date(end).getTime():now)-new Date(start).getTime())/1000));
  return <span className="session-clock" aria-label={`${end?'Duration':'Elapsed time'} ${Math.floor(seconds/60)} minutes`}>{String(Math.floor(seconds/3600)).padStart(2,'0')}:{String(Math.floor(seconds/60)%60).padStart(2,'0')}:{String(seconds%60).padStart(2,'0')}</span>;
}
export function WorkoutLog(p:any) {
  const [workouts,setWorkouts]=useState<any[]>([]),[sets,setSets]=useState<any[]>([]),[exercises,setExercises]=useState<any[]>([]);
  const [selected,setSelected]=useState(''),[edit,setEdit]=useState<any>(),[name,setName]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[loaded,setLoaded]=useState(false);
  useEffect(()=>{let cancelled=false;Promise.all(['workouts','workout_sets','exercises'].map(t=>api('/data/'+t))).then(([w,s,e])=>{
    if(cancelled)return;setWorkouts(w.sort((a:any,b:any)=>b.performed_at.localeCompare(a.performed_at)));setSets(s);setExercises(e);setLoaded(true);setError('');
    setSelected(old=>w.some((r:any)=>r.id===old)?old:w.find((r:any)=>r.started_at&&!r.ended_at)?.id||w[0]?.id||'');
  }).catch(e=>{if(!cancelled)setError(e.message)});return()=>{cancelled=true}},[p.refresh]);
  const active=workouts.find(w=>w.started_at&&!w.ended_at), current=workouts.find(w=>w.id===selected);
  async function action(path:string,body?:any) {
    setBusy(true);setError('');
    try {const w=await api(path,'POST',body);setSelected(w.id);p.onRefresh();savedFeedback(w.ended_at?'Workout finished':'Workout started')}
    catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  return <>
    <Panel title={active?'Workout in progress':'Your next session'} className="session-start">
      {error&&<p className="error" role="alert">{error}</p>}
      {!loaded?<p role="status">Loading workouts…</p>:active?<div className="session-live"><div><strong>{active.title}</strong><small>Started {fmt(active.started_at)} · elapsed time includes rests</small></div><Elapsed start={active.started_at}/><div className="actions"><button onClick={()=>setSelected(active.id)}>Open session</button><button disabled={busy} className="primary" onClick={()=>action('/physical/sessions/'+active.id+'/finish')}><Square size={16}/>Finish workout</button></div></div>:<form className="session-start-form" onSubmit={e=>{e.preventDefault();action('/physical/sessions/start',{title:name.trim()||'Workout'})}}>
        <label>Session name<input placeholder="e.g. Upper body" value={name} maxLength={200} onChange={e=>setName(e.target.value)}/></label>
        <button className="primary" disabled={busy}><Play size={16}/>Start workout</button>
        <button type="button" onClick={()=>setEdit({table:'workouts'})}><Plus size={16}/>Log past workout</button>
      </form>}
      <p className="muted">The timer stays saved when you close Life OS. Forgot to stop it? Edit the session’s start and end times.</p>
    </Panel>
    <div className="session-layout">
      <Panel title="Sessions"><div className="session-list">{workouts.length?workouts.map(w=><button key={w.id} className={w.id===selected?'selected':''} onClick={()=>setSelected(w.id)} aria-pressed={w.id===selected}><strong>{w.title}</strong><small>{fmt(w.performed_at)}</small><span>{sets.filter(s=>s.workout_id===w.id).length} sets · {w.started_at?w.ended_at?`${Math.round((new Date(w.ended_at).getTime()-new Date(w.started_at).getTime())/60000)} min`:'In progress':'Time not recorded'}</span></button>):<Empty text="Start a workout or log a past one."/>}</div></Panel>
      <Panel title={current?.title||'Session details'} action={current&&<button onClick={()=>setEdit({table:'workouts',row:current})}><Pencil size={15}/>Edit session</button>}>
        {current?<><div className="session-meta"><span>{fmt(current.performed_at)}</span>{current.started_at&&<Elapsed start={current.started_at} end={current.ended_at}/>}</div>{current.notes&&<p>{current.notes}</p>}
          <div className="section-head"><h3>Sets</h3><button className="primary" onClick={()=>setEdit({table:'workout_sets',initial:{workout_id:current.id}})}><Plus size={16}/>Add set</button></div>
          {sets.filter(s=>s.workout_id===current.id).sort((a,b)=>a.created_at.localeCompare(b.created_at)).map((s,i)=><div className="session-set" key={s.id}><span className="set-number">{i+1}</span><div><strong>{exercises.find(e=>e.id===s.exercise_id)?.name||'Exercise'}</strong><span>{s.reps} reps × {s.weight_kg} kg{s.rpe!=null?` · RPE ${s.rpe}`:''}</span></div><button aria-label={`Edit set ${i+1}`} onClick={()=>setEdit({table:'workout_sets',row:s})}><Pencil size={15}/></button><button disabled={busy} aria-label={`Delete set ${i+1}`} onClick={async()=>{if(!confirm('Delete this set? Its personal records will be recalculated.'))return;setBusy(true);try{await api('/data/workout_sets/'+s.id,'DELETE');p.onRefresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}}><Trash2 size={15}/></button></div>)}
          {!sets.some(s=>s.workout_id===current.id)&&<Empty text="Add your first set to this session."/>}
          <button className="text-button" disabled={busy} onClick={async()=>{if(!confirm('Delete this workout and all its sets? Its records and activity will be recalculated.'))return;setBusy(true);try{await api('/data/workouts/'+current.id,'DELETE');p.onRefresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}}><Trash2 size={15}/>Delete session</button>
          <p className="muted">Weight is the load you enter, in kilograms. Use the same convention each time. Enter 0 for unweighted sets.</p>
        </>:<Empty text="Choose a session to see its sets and timing."/>}
      </Panel>
    </div>
    <ActivityGrid kind="physical" refresh={p.refresh}/>
    {edit&&<Editor table={edit.table} schema={p.schema} row={edit.row} initial={edit.initial} onSaved={p.onRefresh} onClose={()=>setEdit(undefined)}/>}
  </>;
}

export function PersonalRecords({refresh}:any) {
  const [records,setRecords]=useState<any[]>(),[selected,setSelected]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let cancelled=false;api('/physical/records').then(r=>{if(!cancelled){setRecords(r);setSelected(old=>r.some((x:any)=>x.exercise_id===old)?old:r[0]?.exercise_id||'')}}).catch(e=>{if(!cancelled)setError(e.message)});return()=>{cancelled=true}},[refresh]);
  const record=records?.find(r=>r.exercise_id===selected);
  return <Panel title="Personal records" action={<Trophy size={22} aria-hidden="true"/>}>
    <p className="muted">Calculated from your saved sets, including past workouts. Editing or deleting a set updates its records. Future-dated workouts are excluded.</p>
    {error?<p role="alert" className="error">{error}</p>:!records?<p role="status">Loading records…</p>:!records.length?<Empty text="Log a workout and its sets to establish your first records."/>:<>
      <label className="record-picker">Exercise<select value={selected} onChange={e=>setSelected(e.target.value)}>{records.map(r=><option value={r.exercise_id} key={r.exercise_id}>{r.exercise}</option>)}</select></label>
      {record&&<><div className="pr-headline"><Trophy aria-hidden="true"/><div><span>Heaviest recorded weight</span><strong>{record.heaviest?`${record.heaviest.weight_kg} kg`:'Unweighted sets only'}</strong><small>{record.heaviest?`${record.heaviest.reps} reps · ${fmt(record.heaviest.performed_at)}`:'Rep records are shown below.'}</small></div></div>
        <h3>Best reps at each weight</h3><div className="rep-records">{record.rep_bests.map((r:any)=><div key={r.weight_kg}><span>{r.weight_kg===0?'Unweighted':`${r.weight_kg} kg`}</span><strong>{r.reps} reps</strong><small>{fmt(r.performed_at)}</small></div>)}</div>
        <h3>Record history</h3><ol className="record-history">{record.history.map((r:any)=><li key={r.id}><span className="record-mark" aria-hidden="true"/><div><strong>{r.weight_kg} kg × {r.reps} reps</strong><span>{r.reasons.join(' · ')}</span><small>{r.workout} · {fmt(r.performed_at)}</small></div></li>)}</ol>
      </>}
    </>}
  </Panel>;
}
