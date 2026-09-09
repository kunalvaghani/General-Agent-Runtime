"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Task } from "../lib/types";
import { api } from "../lib/api";
const readTasks=()=>api<Task[]>("/tasks");
export function Dashboard({ load = readTasks }: { load?: () => Promise<Task[]> }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("ALL");
  async function refresh() { try { setTasks(await load()); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load tasks"); } }
  useEffect(() => { let active=true; const update=async()=>{try{const rows=await load();if(active){setTasks(rows);setError("");}}catch(e){if(active)setError(e instanceof Error?e.message:"Unable to load tasks");}};void update();const timer=setInterval(update,5000);return()=>{active=false;clearInterval(timer);}; }, [load]);
  const visible = tasks?.filter(t => filter === "ALL" || t.status === filter);
  return <><div className="row"><div><div className="eyebrow">RUNTIME OVERVIEW</div><h1>Your agent workspace.</h1></div>
    <Link className="button" href="/tasks/new">+ New task</Link></div>
    <p className="lead">Track the plan. Review the evidence. Stay in control.</p>
    <div className="stats"><section className="panel"><small>Total tasks</small><strong>{tasks?.length ?? "—"}</strong></section>
      <section className="panel"><small>Needs your review</small><strong>{tasks?.filter(t => t.status === "WAITING_APPROVAL").length ?? "—"}</strong></section>
      <section className="panel"><small>Verified complete</small><strong>{tasks?.filter(t => t.status === "COMPLETED").length ?? "—"}</strong></section></div>
    <section className="panel runtime"><div><h2>Local runtime</h2><small>Task state refreshes every five seconds. Model readiness is shown in Models.</small></div>
      <span className="badge">API · {error ? "UNAVAILABLE" : tasks ? "CONNECTED" : "CONNECTING"}</span></section>
    <section className="panel"><div className="row"><h2>Tasks</h2><label>Status<select value={filter} onChange={e => setFilter(e.target.value)}>
      {["ALL","PENDING","PLANNING","RUNNING","WAITING_APPROVAL","VERIFYING","BLOCKED","COMPLETED","FAILED","CANCELLED"].map(s => <option key={s}>{s}</option>)}</select></label></div>
      {error ? <div role="alert" className="error">{error} <button className="secondary" onClick={refresh}>Retry</button></div> :
        tasks === null ? <p role="status">Loading tasks…</p> : !visible?.length ? <p>No tasks match this view.</p> :
        <ul className="task-list">{visible.map(t => <li key={t.id}><Link href={`/tasks/${encodeURIComponent(t.id)}`}>
          <div><h3>{t.goal}</h3><small>{t.model_id} · {t.id}</small></div><span className={`badge ${t.status}`}>{t.status.replaceAll("_"," ")}</span>
        </Link></li>)}</ul>}
    </section></>;
}
