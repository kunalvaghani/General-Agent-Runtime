"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { readDetail, type TaskDetail as Detail } from "../lib/task-detail";
import { EventFeed } from "./event-feed";
import { Approval } from "./approval";
import { Desktop } from "./desktop";
import { api } from "../lib/api";
import { taskEventsUrl } from "../lib/events";
export function TaskDetail({ id, load = readDetail, live=true }: { id: string; load?: (id:string) => Promise<Detail | null>; live?:boolean }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkedAt, setCheckedAt] = useState(0);
  const [actionError,setActionError]=useState(""),[busy,setBusy]=useState(false);
  const pendingRead=useRef(false), needsRead=useRef(false), mounted=useRef(true);
  const refresh = useCallback(async () => {
    if(pendingRead.current){needsRead.current=true;return;}pendingRead.current=true;
    do {needsRead.current=false;try{const data=await load(id);if(mounted.current){setDetail(data);setError("");setCheckedAt(Date.now());}}
      catch(e){if(mounted.current)setError(e instanceof Error?e.message:"Unable to load task");}finally{if(mounted.current)setLoading(false);}
    } while(needsRead.current&&mounted.current);pendingRead.current=false;
  }, [id,load]);
  useEffect(() => {mounted.current=true;void refresh();const timer=live?setInterval(refresh,3000):undefined;return()=>{mounted.current=false;clearInterval(timer);};}, [refresh,live]);
  async function control(action:"cancel"|"resume"){if(busy)return;setBusy(true);setActionError("");try{await api(`/tasks/${encodeURIComponent(id)}/${action}`,{method:"POST"});await refresh();}
    catch(e){setActionError(e instanceof Error?e.message:"Task action failed");}finally{setBusy(false);}}
  if (error&&!detail) return <section className="panel"><div role="alert" className="error">{error}</div><button onClick={refresh}>Retry</button></section>;
  if (loading) return <p role="status">Loading task…</p>;
  if (!detail) return <section className="panel"><h1>Task not found</h1><p>The backend has no task with this ID.</p><Link href="/">Back to overview</Link></section>;
  const { task, plan, events } = detail;
  const verification = task.metadata.verification;
  const observations = task.metadata.execution?.observations ?? [];
  return <><Link href="/" className="muted">← Overview</Link><div className="row" style={{marginTop:24}}>
    <div className="eyebrow">TASK / {task.id}</div><button className="secondary" onClick={refresh}>Refresh</button></div>
    <h1>{task.goal}</h1>{error&&<p className="error" role="alert">{error} · Showing the last received snapshot.</p>}{actionError&&<p className="error" role="alert">{actionError}</p>}
    <div className="row"><span data-testid="task-status" className={`badge ${task.status}`}>{task.status.replaceAll("_"," ")}</span>
      <small>{task.model_id} · Budget {task.max_steps} decisions</small></div>
    <p className="lead">Current step: <strong>{task.current_step ?? "None"}</strong></p>
    {live&&<div className="row" style={{justifyContent:"flex-start",marginBottom:20}}>
      {!["COMPLETED","FAILED","CANCELLED"].includes(task.status)&&<button className="secondary" disabled={busy} onClick={()=>control("cancel")}>Cancel task</button>}
      {["BLOCKED","PENDING"].includes(task.status)&&<button disabled={busy} onClick={()=>control("resume")}>Resume task</button>}</div>}
    {task.status === "WAITING_APPROVAL" && task.metadata.execution?.pending && <Approval key={task.metadata.execution.pending.id} taskId={task.id} pending={task.metadata.execution.pending} onRefresh={refresh}/>}
    <div className="detail-grid"><div><section className="panel"><h2>Execution plan</h2>{!plan ? <p>No plan has been saved yet.</p> : <>
      <small>Revision {plan.revision}</small><ol className="steps">{plan.steps.map(step => <li key={step.id} aria-current={step.id === task.current_step ? "step" : undefined}>
        <div className="row"><h3>{step.description}</h3><span className={`badge ${step.status}`}>{step.status}</span></div>
        <p>{step.expected_output}</p><small>{step.id} · Requires {step.dependencies.join(", ") || "no prior steps"} · Attempts {step.attempts}</small>
      </li>)}</ol><h3>Completion criteria</h3><ul>{plan.completion_criteria.map((c,i) => <li key={i}>{c}</li>)}</ul></>}</section>
      <section className="panel"><h2>Tool calls</h2>{!observations.length ? <p className="muted">No tool results recorded.</p> : observations.map((o,i) =>
        <details key={o.call_id ?? i}><summary>{o.tool || "Model response"} · {o.status} · {o.step_id}</summary>
          <small>Call {o.call_id ?? "unverified"}</small><pre>{typeof o.output === "string" ? o.output : JSON.stringify(o.output,null,2)}</pre>
          {o.error && <p className="error">{o.error}</p>}</details>)}</section></div>
      <div><section className="panel"><h2>Verification</h2>{!verification ? <p className="muted">No verification evidence yet.</p> : <>
        <span className={`badge ${verification.passed ? "COMPLETED" : "BLOCKED"}`}>{verification.passed ? "PASSED" : "NOT PASSED"}</span>
        <ul>{verification.evidence.map((e,i) => <li key={i}>{e}</li>)}</ul>{verification.issues.map((issue,i) => <p className="error" key={i}>{issue}</p>)}</>}</section>
      <section className="panel"><h2>Workspace</h2><pre>{task.workspace}</pre><small>Created {task.created_at}<br/>Updated {task.updated_at}</small></section></div></div>
    {live&&<Desktop key={`desktop-${id}`} taskId={id} verified={task.status==="COMPLETED"&&!!verification?.passed}/>}
    <EventFeed key={`events-${id}`} taskId={id} initial={events} url={live?taskEventsUrl(id):undefined} onChange={refresh}
      task={task} checkedAt={checkedAt} error={error}/>
  </>;
}
