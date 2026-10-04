import {useEffect, useRef, useState} from 'react';
import {Check, Sparkles} from 'lucide-react';
import {api} from './api';
import {Modal} from './components';
import {savedFeedback} from './feedback';
import {CaptureKind, LifeMode, energyNames, modeNames, modes, parseCapture, zonedISO} from './contexts';

export function QuickCapture({open,onClose,mode,zone,onSaved}:any){
  const [text,setText]=useState('');
  const [preview,setPreview]=useState<ReturnType<typeof parseCapture>>();
  const [energy,setEnergy]=useState('');
  const [minutes,setMinutes]=useState(60);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const locked=useRef(false);
  const previewInput=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(preview)previewInput.current?.focus()},[!!preview]);
  if(!open)return null;
  const close=()=>{if(!busy)onClose()};
  function review(e:any){e.preventDefault();setError('');setPreview(parseCapture(text,mode,zone));}
  async function save(e:any){
    e.preventDefault();if(!preview||locked.current)return;
    locked.current=true;setBusy(true);setError('');
    try{
      const at=preview.when?zonedISO(preview.when,zone):null;
      let table='tasks',payload:any;
      if(preview.kind==='event'){
        if(!at)throw new Error('Choose the event date and time.');
        if(!Number.isFinite(minutes)||minutes<5||minutes>1440)throw new Error('Choose a duration from 5 to 1440 minutes.');
        table='calendar_events';payload={title:preview.title,description:`Context: ${modeNames[preview.context]}\n\n${text}`,starts_at:at,ends_at:new Date(Date.parse(at)+minutes*60000).toISOString(),timezone:zone};
      }else if(preview.kind==='task'){
        payload={title:preview.title,notes:text,due_at:at,tags:[`context:${preview.context}`,...(energy?[`energy:${energy}`]:[])]};
      }else{
        table=preview.kind==='note'&&preview.context==='work'?'work_notes':'journal_entries';
        payload={title:preview.title,body:text,tags:[`context:${preview.context}`,preview.kind]};
      }
      await api('/data/'+table,'POST',payload);
      savedFeedback(preview.kind==='event'?'Event saved':preview.kind==='task'?'Task added':'Thought saved',`${modeNames[preview.context]} · ${preview.kind==='event'?'Calendar':preview.kind==='task'?'Next up':table==='work_notes'?'Work notes':'Journal'}`);
      setText('');setPreview(undefined);setEnergy('');onSaved();onClose();
    }catch(e:any){setError(e.message)}finally{locked.current=false;setBusy(false)}
  }
  return <Modal title="Quick add" onClose={close}>
    {!preview?<form onSubmit={review} className="capture-form">
      <p className="muted">Capture in {modeNames[mode as LifeMode]}. Check where it goes before saving.</p>
      <label>What’s on your mind?<textarea autoFocus value={text} onChange={e=>setText(e.target.value)} placeholder="Meeting tomorrow at 3pm for work" rows={5} required maxLength={10000}/></label>
      <small>Try “Task: review chapter 2”, “Idea: …”, or “Journal: …”. Dates: today, tomorrow, or YYYY-MM-DD, with a time. No AI call. Unsaved drafts last until you refresh or close this tab.</small>
      <div className="form-actions"><button type="button" onClick={close}>Keep draft & close</button><button className="primary" disabled={!text.trim()}><Sparkles size={16}/>Review capture</button></div>
    </form>:<form onSubmit={save} className="capture-form">
      <div className="capture-preview-label"><Check size={16}/>Review before saving</div>
      <label>Title<input ref={previewInput} required value={preview.title} onChange={e=>setPreview({...preview,title:e.target.value})}/></label>
      <div className="capture-fields">
        <label>Save as<select value={preview.kind} onChange={e=>setPreview({...preview,kind:e.target.value as CaptureKind})}>{[['task','Task'],['note','Note / idea'],['journal','Journal entry'],['event','Calendar event']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
        <label>Context<select value={preview.context} onChange={e=>setPreview({...preview,context:e.target.value as LifeMode})}>{modes.map(m=><option key={m} value={m}>{modeNames[m]}</option>)}</select></label>
      </div>
      {(preview.kind==='task'||preview.kind==='event')&&<>
        <label>{preview.kind==='event'?'Starts at':'Deadline (optional)'} · {zone}<input type="datetime-local" required={preview.kind==='event'} value={preview.when} onChange={e=>setPreview({...preview,when:e.target.value})}/></label>
        {!preview.when&&<small>{preview.hint}</small>}
        {preview.kind==='event'?<label>Duration in minutes<input type="number" min={5} max={1440} value={minutes} onChange={e=>setMinutes(Number(e.target.value))}/></label>:<label>Energy<select value={energy} onChange={e=>setEnergy(e.target.value)}><option value="">Not set</option>{Object.entries(energyNames).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>}
      </>}
      <small>Your original text is kept with the record.{(preview.kind==='note'||preview.kind==='journal')&&` Find it in ${preview.kind==='note'&&preview.context==='work'?'Work notes':'the journal'}, under ${modeNames[preview.context]}.`}</small>
      {error&&<p className="error" role="alert">{error}</p>}
      <div className="form-actions"><button type="button" disabled={busy} onClick={()=>setPreview(undefined)}>Edit text</button><button className="primary" disabled={busy||!preview.title.trim()}>{busy?'Saving…':'Save capture'}</button></div>
    </form>}
  </Modal>;
}
