import React, { useEffect, useState } from 'react';
import { api, fmt } from './api';
import { Panel, Records, Empty } from './components';

export function LearningLog(p: any) {
  return <>
    <Panel title="Learning, wherever it happens">
      <p>Learn in ChatGPT, in class or on your own. Keep the useful milestones and your next step here.</p>
      <p className="muted">Studied means you explored it. Practised means you tried it. Demonstrated means you showed understanding. Time is optional.</p>
    </Panel>
    <Records {...p} table="learning_topics" heading="Topics & next steps" columns={['title','course_id','status','next_step']} />
    <Records {...p} table="learning_sessions" heading="Learning log" columns={['topic_id','studied_at','kind','summary','minutes']} />
  </>;
}

export function AssistantSettings(p: any) {
  const [connection,setConnection]=useState<any>();
  const [changes,setChanges]=useState<any[]>([]);
  const [weekly,setWeekly]=useState<any>();
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{Promise.all([api('/assistant/connection'),api('/assistant/changes'),api('/assistant/weekly')]).then(([c,h,w])=>{setConnection(c);setChanges(h);setWeekly(w)}).catch(e=>setError(e.message))},[p.refresh]);
  async function action(path:string,success:string) {
    setBusy(true);setError('');
    try {await api(path,'POST',{});setMessage(success);p.onRefresh()}
    catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  return <>
    {error&&<p className="error" role="alert">{error}</p>}
    {message&&<p className="notice" role="status">{message}</p>}
    <Panel title="Life OS in ChatGPT">
      <p>{connection?.authorized_connections ? 'A private ChatGPT connection is authorized.' : 'ChatGPT is not connected yet.'}</p>
      <p>Use your Life OS project for ongoing tracking. In an ordinary chat, call Life OS when you want to save or retrieve something. Summaries stay concise; insights stay separate from your words.</p>
      <div className="actions">
        <a className="button" href="https://chatgpt.com/g/g-p-6aa79a647e048191bb4ba6add6340a6c/project" target="_blank" rel="noreferrer">Open Life OS project ↗</a>
        {Boolean(connection?.authorized_connections)&&<button disabled={busy} onClick={()=>action('/assistant/disconnect','ChatGPT access revoked. Your saved records are still here.')}>Disconnect ChatGPT</button>}
      </div>
      <p className="muted">Your phone sends watch readings to Life OS. It is not involved in saving chats, tasks or learning progress.</p>
    </Panel>
    <Panel title="Morning brief">
      <strong>Every day · 9:00 am · India time</strong>
      <p>{connection?.schedule_verified ? 'Scheduled in ChatGPT.' : 'Preferred time saved. The ChatGPT schedule has not been verified yet.'}</p>
      {!connection?.schedule_verified&&<button disabled={busy} onClick={()=>action('/assistant/schedule-verification','The active ChatGPT schedule is now recorded as verified.')}>Mark verified</button>}
      <p className="muted">A brief uses saved plans and dated readings. Missing or delayed watch data is labelled, never filled in.</p>
    </Panel>
    <Panel title="Weekly review">
      <p>ChatGPT can now review a dated seven-day snapshot without a separate AI key.</p>
      {weekly&&<div className="metric-strip">
        <span><strong>{weekly.completed_tasks}</strong><small>tasks completed</small></span>
        <span><strong>{weekly.learning_sessions}</strong><small>learning sessions</small></span>
        <span><strong>{weekly.workouts}</strong><small>workouts</small></span>
        <span><strong>{weekly.journal_entries}</strong><small>journal entries</small></span>
      </div>}
      <p className="muted">In the Life OS project, ask “Use Life OS to review my week.” It will label missing or stale watch data and suggest no more than three priorities.</p>
    </Panel>
    <Panel title="Exam timetable assistant">
      <p>Share a timetable in the Life OS project. ChatGPT can match existing courses, preview linked exam and calendar records, and save them only after you approve the dates.</p>
      <p className="muted">Ambiguous course names, dates, times, and timezones must be clarified. Reusing the same timetable import key prevents duplicates.</p>
    </Panel>
    <Panel title="Saved from ChatGPT">
      {!changes.length&&<Empty text="Change receipts will appear here when ChatGPT saves something." />}
      {changes.map(c=><div className="course-row" key={c.id}>
        <div><strong>{c.summary}</strong><small>{fmt(c.created_at)} · {c.status==='applied'?'Saved':c.status}</small>{c.chat_url&&<a href={c.chat_url} target="_blank" rel="noreferrer">Open source chat ↗</a>}</div>
        {c.status==='applied'&&<button disabled={busy} onClick={()=>action('/assistant/undo/'+c.id,'That change has been undone.')}>Undo</button>}
      </div>)}
      <p className="muted">Undo is available for 30 days. It protects anything you edited afterwards.</p>
    </Panel>
  </>;
}
