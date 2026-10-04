// Development-only harness: exercises production components without private data.
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Tabs, Modal, Metric, Records, Trend } from '../src/components';
import { CompleteTask, SuccessFeedback, ValueBar, savedFeedback } from '../src/feedback';
import '../src/style.css';
import '../src/pixel.css';
import '../src/interactions.css';
import '../src/night.css';
function Fixture() {
  const [active, setActive] = useState('one');
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(12);
  const [done, setDone] = useState(false);
  return <main style={{padding: 24, maxWidth: 900, margin: 'auto'}}>
    <h1>Interaction checks</h1>
    <Tabs items={[["one", "Overview"], ["two", "Progress and history"], ["three", "Personal targets"]]} active={active} onChange={setActive} />
    <button onClick={() => setOpen(true)}>Open editor</button>
    {open && <Modal title="Edit a goal" onClose={() => setOpen(false)}><label>Goal<input autoFocus defaultValue="Read a chapter" /></label></Modal>}
    <Metric label="Steps" value={value} unit="steps"><ValueBar ratio={value / 50} /></Metric>
    <button onClick={() => setValue(v => v + 5)}>Update reading</button>
    <Trend values={[2, 4, 3, 8]} label="Progress" />
    {!done && <div className="task-row"><CompleteTask task={{id:'motion-task', title:'Read a chapter'}} onRefresh={() => setDone(true)} /><strong>Read a chapter</strong></div>}
    <button onClick={() => savedFeedback('Goal saved')}>Save confirmation</button>
    <Records table="projects" schema={{ projects: { editable: false, fields: [{name:'title', type:'text'}] } }} refresh={0} />
    <SuccessFeedback />
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Fixture /></React.StrictMode>);
