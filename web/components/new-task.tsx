"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { NewTask, Task, Model } from "../lib/types";
import { createTask, validateTaskInput } from "../lib/create-task";
import { api } from "../lib/api";
const discover=async()=>{const [models,settings]=await Promise.all([api<Model[]>("/models"),api<{default_model:string|null}>("/settings")]);return {models,defaultModel:settings.default_model};};
export function NewTaskForm({ save = createTask, loadModels=discover }: { save?: (input: NewTask) => Promise<Task>;loadModels?:typeof discover }) {
  const [goal, setGoal] = useState("");
  const [model, setModel] = useState("");
  const [models,setModels]=useState<Model[]>([]),[discovering,setDiscovering]=useState(true),[discoveryError,setDiscoveryError]=useState(""),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true;setDiscovering(true);setDiscoveryError("");loadModels().then(data=>{if(active){setModels(data.models);setModel(data.models.some(m=>m.id===data.defaultModel)?data.defaultModel!:data.models[0]?.id??"");}}).catch(e=>{if(active)setDiscoveryError(e instanceof Error?e.message:"Model discovery failed");}).finally(()=>{if(active)setDiscovering(false);});return()=>{active=false;};},[loadModels,retry]);
  const [budget, setBudget] = useState("12");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Task | null>(null);
  const submitting = useRef(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); if (submitting.current) return;
    submitting.current = true; setBusy(true); setError("");
    try { setCreated(await save(validateTaskInput({goal, model, max_steps:Number(budget)}))); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to create task. Your inputs are preserved."); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <><Link className="muted" href="/">← Overview</Link><div className="eyebrow" style={{marginTop:28}}>NEW TASK</div>
    <h1>What should we work on?</h1><p className="lead">Describe the outcome and how success should be checked.</p>
    <section className="panel" style={{maxWidth:780}}>{created ? <div role="status"><h2>Task submitted</h2>
      <p>The backend has accepted your task.</p><Link className="button" href={`/tasks/${created.id}`}>View task</Link></div> :
      <form onSubmit={submit} noValidate><label htmlFor="goal">Goal</label><textarea id="goal" value={goal} maxLength={20000}
        placeholder="Build a CSV summary utility and verify it with tests…" onChange={e => setGoal(e.target.value)} required disabled={busy}/>
        <label htmlFor="model">Model</label><select id="model" value={model} onChange={e => setModel(e.target.value)} disabled={busy}>
          <option value="">{discovering?"Discovering models…":"Choose an installed model"}</option>{models.map(m=><option key={`${m.provider}:${m.id}`} value={m.id}>{m.id} · {m.provider}</option>)}</select>
        {discoveryError&&<p className="error" role="alert">{discoveryError}</p>}{!discovering&&!models.length&&<p>No installed models available. Start Ollama and check Models.</p>}
        <button type="button" className="secondary" disabled={discovering||busy} onClick={()=>setRetry(n=>n+1)}>Refresh available models</button>
        <label htmlFor="budget">Maximum steps</label><input id="budget" type="number" min="1" max="1000" step="1"
          value={budget} onChange={e => setBudget(e.target.value)} disabled={busy}/>
        <p className="muted">Submitting starts a bounded task in its own workspace. Actions requiring permission pause for your review.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy||discovering||!models.length}>{busy ? "Submitting…" : "Create task"}</button>
      </form>}</section></>;
}
