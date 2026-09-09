"use client";
import { useEffect, useRef, useState } from "react";
import { connectEvents, type ConnectionState } from "../lib/events";
import type { RuntimeEvent } from "../lib/types";
import type { Task } from "../lib/types";
import { ActivityPanel } from "./activity-panel";
export function EventFeed({taskId, initial, url, onChange, task, checkedAt=0, error=""}: {taskId:string; initial:RuntimeEvent[];
  url?:string; onChange?: () => void; task?:Task; checkedAt?:number; error?:string}) {
  const [events,setEvents] = useState(initial);
  const [state,setState] = useState<ConnectionState>("connecting");
  const [retry,setRetry] = useState(0);
  const cursor=useRef(Math.max(0,...initial.map(e=>e.id)));
  const notify=useRef(onChange);notify.current=onChange;
  useEffect(() => {
    setEvents(old => [...new Map([...old,...initial].map(event => [event.id,event])).values()]
      .sort((a,b)=>a.id-b.id).slice(-500));
  }, [initial]);
  useEffect(() => {
    if (!url) return;
    return connectEvents({url,taskId,after:cursor.current,onState:state=>{setState(state);if(state==="finished")notify.current?.();},
      onEvent:event => {cursor.current=event.id;setEvents(old => [...old.filter(e => e.id !== event.id),event].sort((a,b)=>a.id-b.id).slice(-500)); notify.current?.();}});
  }, [taskId,url,retry]);
  return <><section className="panel"><div className="row"><h2>Event log</h2><span role="status" className="badge">
    {url ? state.toUpperCase() : "SAVED RECORDS"}</span></div>
    {state === "reconnecting" && url && <p role="status">Connection lost. Reconnecting from the last event…</p>}
    {state === "error" && url && <div role="alert" className="error">Unable to read the event stream. <button onClick={()=>setRetry(n=>n+1)}>Reconnect</button></div>}
    {state === "finished" && url && <p>Task event stream finished.</p>}
    {!events.length ? <p>No events recorded.</p> : events.map(e => <details key={e.id}><summary>#{e.id} · {e.event} · {e.timestamp}</summary><pre>{JSON.stringify(e.data,null,2)}</pre></details>)}
    {events.length >= 500 && <small>Showing the latest 500 events.</small>}
  </section>{task && <><div className="activity-spacer"/><ActivityPanel task={task} events={events} connection={state}
    checkedAt={checkedAt} error={error} live={!!url}/></>}</>;
}
