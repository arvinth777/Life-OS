import {useEffect,useState} from 'react';
import {Leaf,ArrowRight,RotateCcw} from 'lucide-react';
import {api,fmt,todayDate} from './api';
import {Modal,LoadingRows} from './components';
import {LifeMode,modeNames,recordMode} from './contexts';
import {savedFeedback} from './feedback';
export const taskReady=(t:any,day:string)=>t.status!=='done'&&!t.archived&&(!t.focus_after||t.focus_after<=day);
export function RestoreTask({task,onRefresh}:any){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <><button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await api('/data/tasks/'+task.id,'PATCH',{archived:false,focus_after:null});savedFeedback('Task resumed');onRefresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}}><RotateCcw size={15}/>Resume task</button>{error&&<p role="alert" className="error">{error}</p>}</>
}
export function ResetButton({mode,onRefresh}: {mode:LifeMode,onRefresh:()=>void}){
  const [open,setOpen]=useState(false);
  return <><button onClick={()=>setOpen(true)}><Leaf size={16}/>Start fresh</button>{open&&<ResetFlow mode={mode} onRefresh={onRefresh} onClose={()=>setOpen(false)}/>}</>
}
function ResetFlow({mode,onRefresh,onClose}:any){
  const [tasks,setTasks]=useState<any[]|null>(null),[choices,setChoices]=useState<Record<string,{action:string,date:string}>>({});
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[preview,setPreview]=useState<any>(),[receipt,setReceipt]=useState('');
  const [step,setStep]=useState<'choose'|'review'|'done'>('choose');
  useEffect(()=>{api('/data/tasks').then(r=>setTasks(r.filter((t:any)=>t.status!=='done'&&!t.archived&&recordMode(t)===mode))).catch(e=>setError(e.message))},[mode]);
  const selected=Object.entries(choices).filter(([,v])=>v.action!=='leave');
  async function prepare(){setBusy(true);setError('');try{
    const operations=selected.map(([id,c])=>({action:'update',table:'tasks',record_id:id,expected_updated_at:tasks!.find(t=>t.id===id).updated_at,data:{archived:c.action==='archive',focus_after:c.action==='later'?c.date:null}}));
    const batch={source:'Life OS',request_key:crypto.randomUUID(),summary:`Intentional reset · ${modeNames[mode as LifeMode]} · ${operations.length} tasks`,operations};
    await api('/assistant/preview','POST',batch);setPreview(batch);setStep('review');
  }catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function apply(){setBusy(true);setError('');try{const result=await api('/assistant/apply','POST',preview);setReceipt(result.batch_id);setStep('done');savedFeedback('A little breathing room');onRefresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function undo(){setBusy(true);setError('');try{await api('/assistant/undo/'+receipt,'POST');savedFeedback('Reset undone');onRefresh();onClose()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  return <Modal title="A fresh start, at your pace" onClose={()=>{if(!busy)onClose()}}><div className="reset-flow"><div className="reset-steps" aria-label={`Step ${step==='choose'?1:step==='review'?2:3} of 3`}>{['Choose','Review','Breathe'].map((s,i)=><span key={s} className={i===(step==='choose'?0:step==='review'?1:2)?'current':''}>{i+1} · {s}</span>)}</div>
    {step==='choose'&&<><p>Review your unfinished {modeNames[mode as LifeMode].toLowerCase()} tasks. Leave anything you’re unsure about.</p><p className="muted">Later tasks leave your daily focus until your chosen date. Their deadlines stay in the calendar. Archived tasks stay saved and can be restored.</p>{!tasks&&!error?<LoadingRows/>:tasks?.length===0?<p className="reset-breathe">Nothing needs sorting. You can start small whenever you’re ready.</p>:tasks?.map(t=><div className="reset-task" key={t.id}><strong>{t.title}</strong><small>{t.due_at?`Original deadline · ${fmt(t.due_at)}`:'No deadline'}{t.rrule?' · Recurring':''}{t.parent_id?' · Subtask':''}{t.focus_after?` · Revisit ${t.focus_after}`:''}</small><select aria-label={`Plan for ${t.title}`} value={choices[t.id]?.action||'leave'} disabled={busy} onChange={e=>setChoices({...choices,[t.id]:{action:e.target.value,date:choices[t.id]?.date||''}})}><option value="leave">Leave as is</option><option value="resume">Resume now</option><option value="later">Revisit later</option><option value="archive">Archive for now</option></select>{choices[t.id]?.action==='later'&&<label>Bring back on<input required type="date" min={todayDate()} value={choices[t.id].date} onChange={e=>setChoices({...choices,[t.id]:{...choices[t.id],date:e.target.value}})}/></label>}</div>)}<p className="muted">Each task is handled separately; subtasks and recurring instances aren’t changed automatically. Review up to 30 at a time.</p><button className="primary" disabled={busy||!selected.length||selected.length>30||selected.some(([,c])=>c.action==='later'&&(!c.date||c.date<todayDate()))} onClick={prepare}>Review {selected.length} changes <ArrowRight size={16}/></button></>}
    {step==='review'&&<><h3>Here’s what will change</h3>{selected.map(([id,c])=><div className="reset-task" key={id}><strong>{tasks!.find(t=>t.id===id)?.title}</strong><span>{c.action==='archive'?'Archive, keeping history':c.action==='later'?`Return to focus on ${c.date}`:'Return to focus now'}</span></div>)}<p>Original deadlines and completion history stay unchanged. Nothing is marked complete or permanently deleted.</p><div className="actions"><button disabled={busy} onClick={()=>setStep('choose')}>Back</button><button className="primary" disabled={busy} onClick={apply}>{busy?'Saving…':'Apply my reset'}</button></div></>}
    {step==='done'&&<div className="reset-done"><span className="reset-leaf"><Leaf size={40}/></span><h3>You have room to begin again.</h3><p>Choose one small next step. The rest can wait.</p><p className="muted">Find saved tasks in To-do list → Later or Archived. This reset can also be undone from Settings → ChatGPT & history → Saved changes for 30 days, unless a task has since changed.</p><div className="actions"><button disabled={busy} onClick={undo}><RotateCcw size={16}/>Undo reset</button><button className="primary" disabled={busy} onClick={onClose}>Back to my day</button></div></div>}
    {error&&<p role="alert" className="error">{error}{step!=='done'&&' Close and reopen this view if a task changed elsewhere.'}</p>}
  </div></Modal>
}
