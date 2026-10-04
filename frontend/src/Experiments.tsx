import {useEffect, useState} from 'react';
import {FlaskConical, Plus, Check, ArrowRight} from 'lucide-react';
import {api, todayDate} from './api';
import {Modal, LoadingRows, Panel} from './components';
import {savedFeedback} from './feedback';

const addDays=(day:string,n:number)=>new Date(Date.parse(day+'T12:00:00Z')+n*86400000).toISOString().slice(0,10);
export function Experiments({refresh,onRefresh}:any){
  const [rows,setRows]=useState<any[]|null>(null),[logs,setLogs]=useState<any[]>([]),[error,setError]=useState('');
  const [past,setPast]=useState(false),[editing,setEditing]=useState<any>(),[selected,setSelected]=useState<any>();
  useEffect(()=>{let alive=true;Promise.all([api('/data/experiments'),api('/data/experiment_checkins')]).then(([a,b])=>{if(alive){setRows(a);setLogs(b);setError('')}}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[refresh]);
  const today=todayDate();
  return <div className="experiments"><Panel title="Try a small change" action={<button className="primary" onClick={()=>setEditing({})}><Plus size={16}/>New experiment</button>}><p>Choose one thing to try, notice how it feels, and decide what deserves to stay.</p><div className="energy-filter"><button aria-pressed={!past} onClick={()=>setPast(false)}>In progress</button><button aria-pressed={past} onClick={()=>setPast(true)}>What I learned</button></div></Panel>
    {error&&<p role="alert" className="error">{error} <button onClick={onRefresh}>Retry</button></p>}
    {!rows&&!error?<LoadingRows/>:null}
    <div className="experiment-grid">{rows?.filter(r=>(r.status!=='active')===past).map(r=>{
      const entries=logs.filter(l=>l.experiment_id===r.id),checked=entries.some(l=>l.on_date===today);
      const length=Math.round((Date.parse(r.ends_on)-Date.parse(r.starts_on))/86400000)+1;
      const elapsed=Math.max(0,Math.min(length,Math.floor((Date.parse(today)-Date.parse(r.starts_on))/86400000)+1));
      return <article className="experiment-card" key={r.id}><div className="experiment-card-top"><span className="experiment-orb"><FlaskConical size={24}/></span><small>{r.status==='active'?(today>r.ends_on?'Ready to reflect':today<r.starts_on?'Starts '+r.starts_on:`Day ${elapsed} of ${length}`):({keep:'Keep it',change:'Adjust it',stop:'Let it go'} as any)[r.status]}</small></div><h2>{r.title}</h2><p>{r.action}</p><div className="experiment-progress" aria-label={`${elapsed} of ${length} calendar days elapsed`}><span style={{width:`${elapsed/length*100}%`}}/></div><small>{r.starts_on} → {r.ends_on} · {entries.length} {entries.length===1?'check-in':'check-ins'}</small>{r.conclusion&&<blockquote>{r.conclusion}</blockquote>}<div className="actions"><button onClick={()=>setSelected(r)}>{past?'Read reflections':checked?<><Check size={16}/>Today saved</>:today>r.ends_on?'Reflect & decide':'Open experiment'}<ArrowRight size={16}/></button><button className="text-button" onClick={()=>setEditing(r)}>Edit</button></div></article>
    })}</div>
    {rows&&!rows.some(r=>(r.status!=='active')===past)&&<div className="experiment-empty"><FlaskConical size={38}/><h3>{past?'Your discoveries will live here.':'A question, not a commitment.'}</h3><p>{past?'Finish an experiment with a reflection to keep what you learned.':'For example: does a short walk before studying make starting easier?'}</p>{!past&&<button onClick={()=>setEditing({})}>Try my first experiment</button>}</div>}
    {editing&&<ExperimentForm row={editing} onClose={()=>setEditing(undefined)} onSaved={onRefresh}/>}
    {selected&&<ExperimentDetail row={rows?.find(r=>r.id===selected.id)||selected} logs={logs.filter(l=>l.experiment_id===selected.id)} onClose={()=>setSelected(undefined)} onSaved={onRefresh}/>}
  </div>
}
function ExperimentForm({row,onClose,onSaved}:any){
  const [form,setForm]=useState({title:row.title||'',hypothesis:row.hypothesis||'',action:row.action||'',starts_on:row.starts_on||todayDate(),ends_on:row.ends_on||addDays(todayDate(),13)});
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const field=(key:keyof typeof form)=>(e:any)=>setForm({...form,[key]:e.target.value});
  async function save(e:any){e.preventDefault();setBusy(true);setError('');try{await api('/data/experiments'+(row.id?'/'+row.id:''),row.id?'PATCH':'POST',form);savedFeedback('Experiment saved');onSaved();onClose()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  return <Modal title={row.id?'Edit experiment':'A small experiment'} onClose={()=>{if(!busy)onClose()}}><form className="experiment-form" onSubmit={save}><label>Name<input required maxLength={200} value={form.title} onChange={field('title')} placeholder="A calmer start to the morning"/></label><label>What will you try?<textarea required maxLength={2000} value={form.action} onChange={field('action')} placeholder="Keep my phone away until after breakfast."/></label><label>What do you hope to notice?<textarea maxLength={2000} value={form.hypothesis} onChange={field('hypothesis')} placeholder="Whether I feel less rushed."/></label><div className="experiment-dates"><label>Start<input required type="date" value={form.starts_on} onChange={field('starts_on')}/></label><label>End<input required type="date" min={form.starts_on} value={form.ends_on} onChange={field('ends_on')}/></label></div><p className="muted">A two-week window is a starting point. Missing a day doesn’t reset anything.</p>{error&&<p className="error" role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'Saving…':'Save experiment'}</button></form></Modal>
}
function ExperimentDetail({row,logs,onClose,onSaved}:any){
  const today=todayDate(),last=today<row.ends_on?today:row.ends_on;
  const [day,setDay]=useState(last),[tried,setTried]=useState(false),[feeling,setFeeling]=useState(''),[note,setNote]=useState('');
  const [decision,setDecision]=useState(row.status==='active'?'keep':row.status),[conclusion,setConclusion]=useState(row.conclusion||'');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const entry=logs.find((l:any)=>l.on_date===day);
  useEffect(()=>{setTried(entry?.tried||false);setFeeling(entry?.feeling?String(entry.feeling):'');setNote(entry?.note||'')},[day,entry?.id,entry?.updated_at]);
  async function save(kind:'checkin'|'finish',e:any){e.preventDefault();setBusy(true);setError('');try{if(kind==='checkin')await api('/data/experiment_checkins'+(entry?'/'+entry.id:''),entry?'PATCH':'POST',{experiment_id:row.id,on_date:day,tried,feeling:feeling?Number(feeling):null,note});else await api('/data/experiments/'+row.id,'PATCH',{status:decision,conclusion});savedFeedback(kind==='checkin'?'Check-in saved':'Reflection saved');onSaved()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  return <Modal title={row.title} onClose={()=>{if(!busy)onClose()}}><p>{row.action}</p>{row.hypothesis&&<p className="muted">Looking for: {row.hypothesis}</p>}
    {row.starts_on<=today&&row.status==='active'&&<form className="experiment-form" onSubmit={e=>save('checkin',e)}><h3>Notice how it went</h3><label>Day<input type="date" required min={row.starts_on} max={last} value={day} onChange={e=>setDay(e.target.value)}/></label><label className="experiment-check"><input type="checkbox" checked={tried} onChange={e=>setTried(e.target.checked)}/> I tried the change this day</label><label>How did it feel?<select value={feeling} onChange={e=>setFeeling(e.target.value)}><option value="">Not rated</option>{['Very difficult','Difficult','Neutral','Good','Very good'].map((l,i)=><option key={l} value={i+1}>{i+1} · {l}</option>)}</select></label><label>What did you notice?<textarea maxLength={3000} value={note} onChange={e=>setNote(e.target.value)}/></label><button disabled={busy}>{entry?'Update check-in':'Save check-in'}</button></form>}
    {row.starts_on>today&&<p className="notice">Check-ins open on {row.starts_on}.</p>}
    <section className="experiment-log"><h3>Your observations</h3>{logs.length?logs.slice().sort((a:any,b:any)=>b.on_date.localeCompare(a.on_date)).map((l:any)=><article key={l.id}><strong>{l.on_date}</strong><small>{l.tried?'Tried it':'Didn’t try it'}{l.feeling?` · Feeling ${l.feeling}/5`:''}</small><p>{l.note||'No written note.'}</p></article>):<p className="muted">No observations yet. A sentence is enough.</p>}</section>
    <form className="experiment-form" onSubmit={e=>save('finish',e)}><h3>{row.status==='active'?'When you’re ready, decide':'Your conclusion'}</h3><label>What comes next?<select value={decision} onChange={e=>setDecision(e.target.value)}><option value="keep">Keep it</option><option value="change">Adjust it</option><option value="stop">Let it go</option></select></label><label>What did you learn?<textarea required maxLength={4000} value={conclusion} onChange={e=>setConclusion(e.target.value)}/></label><p className="muted">This saves your own reflection. It doesn’t prove cause and effect or create a new habit automatically.</p><button className="primary" disabled={busy}>{row.status==='active'?'Finish experiment':'Update reflection'}</button></form>{error&&<p role="alert" className="error">{error}</p>}
  </Modal>
}
