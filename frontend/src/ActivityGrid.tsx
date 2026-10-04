import React, {useEffect, useRef, useState} from 'react';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import {api, fmt, todayDate} from './api';
import {Panel} from './components';

const definitions = {
  physical: ['Workout activity', 'Logged workouts. Empty squares mean no workout logged; rest days belong here too.'],
  academics: ['Study activity', 'Study sessions linked to a course through their topic. Add them in Learning; deadlines and grades do not count as study.'],
  dsa: ['DSA activity', 'Problem attempts, concept reviews, and study sessions linked to a pattern through their topic.'],
};
const dayLabel = (day: string) => new Date(day+'T12:00:00Z').toLocaleDateString(undefined, {timeZone:'UTC',weekday:'short',month:'short',day:'numeric',year:'numeric'});
export function ActivityGrid({kind, refresh}: {kind: keyof typeof definitions; refresh: any}) {
  const [year,setYear] = useState(()=>Number(todayDate().slice(0,4)));
  const [data,setData] = useState<any>();
  const [error,setError] = useState('');
  const [selected,setSelected] = useState(todayDate());
  const scroll = useRef<HTMLDivElement>(null);
  useEffect(()=>{
    let cancelled=false;
    setData(undefined);setError('');
    api(`/activity/${kind}?year=${year}`).then(value=>{
      if(cancelled)return;
      setData(value);
      setSelected(year===Number(value.today.slice(0,4)) ? value.today : `${year}-12-31`);
    }).catch(e=>{if(!cancelled)setError(e.message)});
    return ()=>{cancelled=true};
  },[kind,year,refresh]);
  useEffect(()=>{if(data && scroll.current){
    const last=year===Number(data.today.slice(0,4))?data.today:`${year}-12-31`;
    const week=Math.floor(((new Date(last+'T12:00:00Z').getTime()-Date.UTC(year,0,1))/86400000+(new Date(Date.UTC(year,0,1)).getUTCDay()+6)%7)/7);
    scroll.current.scrollLeft=Math.max(0,week*22-scroll.current.clientWidth+30);
  }},[data,year]);
  const start = new Date(Date.UTC(year,0,1));
  const offset = (start.getUTCDay()+6)%7;
  const count = (Date.UTC(year+1,0,1)-start.getTime())/86400000;
  const cells=Array.from({length:Math.ceil((offset+count)/7)*7},(_,i)=>{
    if(i<offset || i>=offset+count)return null;
    return new Date(start.getTime()+(i-offset)*86400000).toISOString().slice(0,10);
  });
  const detail=data?.days[selected];
  const [heading,definition]=definitions[kind];
  return <Panel title={heading} className="activity-panel" action={<div className="activity-year">
    <button aria-label={`Previous year for ${heading}`} disabled={year<=1900} onClick={()=>setYear(year-1)}><ChevronLeft size={17}/></button>
    <strong>{year}</strong>
    <button aria-label={`Next year for ${heading}`} disabled={year>=Number(todayDate().slice(0,4))} onClick={()=>setYear(year+1)}><ChevronRight size={17}/></button>
  </div>}>
    <p className="muted">{definition}</p>
    {error ? <p className="error" role="alert">{error} <button onClick={()=>{setError('');api(`/activity/${kind}?year=${year}`).then(setData).catch(e=>setError(e.message))}}>Retry</button></p> : !data ? <p role="status">Loading activity…</p> : <>
      <div className="activity-summary"><strong>{data.active_days} active {data.active_days===1?'day':'days'}</strong><span>{data.total} logged activities · {data.timezone}</span></div>
      <div ref={scroll} className="activity-scroll">
        <div className="activity-months" style={{gridTemplateColumns:`repeat(${cells.length/7},18px)`}} aria-hidden="true">{cells.map((d,i)=>d?.endsWith('-01')?<span style={{gridColumn:Math.floor(i/7)+1}} key={d}>{new Date(d+'T12:00:00Z').toLocaleDateString(undefined,{timeZone:'UTC',month:'short'})}</span>:null)}</div>
        <div className="activity-grid" role="group" aria-label={`${heading}, ${year}. Arrow keys move between days.`}>
          {cells.map((day,i)=>{
            if(!day)return <span key={i}/>;
            const n=data.days[day]?.count||0, future=day>data.today;
            const label=`${dayLabel(day)}: ${future?'Future date':n?`${n} logged activities`:'Nothing logged'}`;
            return <button key={day} className="activity-day" data-level={Math.min(n,4)} disabled={future}
              aria-label={label} title={label} aria-pressed={day===selected} tabIndex={day===selected?0:-1}
              onClick={()=>setSelected(day)} onFocus={()=>setSelected(day)}
              onKeyDown={e=>{
                const delta=({ArrowUp:-1,ArrowDown:1,ArrowLeft:-7,ArrowRight:7} as any)[e.key];
                if(delta===undefined)return;
                e.preventDefault();
                const next=e.currentTarget.parentElement?.children[i+delta] as HTMLButtonElement;
                if(next?.tagName==='BUTTON'&&!next.disabled)next.focus();
              }}/>
          })}
        </div>
      </div>
      <div className="activity-legend"><span>Nothing logged</span>{[0,1,2,3,4].map(n=><i key={n} data-level={n}/>)}<span>4+ activities</span></div>
      <div className="activity-detail" aria-live="polite">
        <strong>{dayLabel(selected)}</strong>
        {detail ? <><span>{detail.count} activities{detail.timed_entries>0?` · ${detail.minutes} recorded min`:''}</span><ul>{detail.entries.map((entry:any)=><li key={entry.id}><span>{entry.label}</span><small>{fmt(entry.at)}{entry.minutes!=null?` · ${Math.round(entry.minutes*10)/10} min`:''}</small></li>)}</ul></> : <p className="muted">{selected>data.today?'Future date.':'Nothing logged for this day.'}</p>}
      </div>
    </>}
  </Panel>;
}
