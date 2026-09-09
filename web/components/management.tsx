"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { Model } from "../lib/types";
export interface MemoryItem { id:string;type:string;content:string;source_task_id:string;importance:number;created_at:number;expires_at:number|null; }
export interface RuntimeSettings { default_model:string|null;model_timeout:number; }
function message(error:unknown) { return error instanceof Error ? error.message : "The request failed. Try again."; }
export function Models() {
  const [models,setModels]=useState<Model[]>([]),[busy,setBusy]=useState(true),[error,setError]=useState("");
  const refresh=useCallback(async()=>{setBusy(true);setError("");try{setModels(await api<Model[]>("/models/refresh",{method:"POST"}));}
    catch(e){setError(message(e));}finally{setBusy(false);}},[]);
  useEffect(()=>{void refresh();},[refresh]);
  return <><div className="eyebrow">MODEL LIBRARY</div><h1>Your available models.</h1><p className="lead">Discover the models installed in your configured provider.</p>
    <section className="panel"><div className="row"><h2>Installed models</h2><button onClick={refresh} disabled={busy}>Refresh models</button></div>
      {error && <p role="alert" className="error">{error}</p>}{busy ? <p role="status">Discovering models…</p> : !models.length ? <p>No models found. Start Ollama and install a model, then refresh.</p> :
      <ul className="task-list">{models.map(m=><li key={`${m.provider}:${m.id}`}><h3>{m.id}</h3><p className="muted">Provider: {m.provider}</p></li>)}</ul>}
      <Link href="/settings">Choose your default model in settings →</Link></section></>;
}
export function Memory() {
  const [items,setItems]=useState<MemoryItem[]>([]),[query,setQuery]=useState(""),[category,setCategory]=useState("");
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[confirm,setConfirm]=useState<string|null>(null);
  const generation=useRef(0);
  const refresh=useCallback(async()=>{const request=++generation.current;setBusy(true);setError("");
    try {const rows=await api<MemoryItem[]>(`/memory?${new URLSearchParams({query,...(category?{category}:{})})}`);if(request===generation.current)setItems(rows);}
    catch(e){if(request===generation.current)setError(message(e));}finally{if(request===generation.current)setBusy(false);}},[query,category]);
  useEffect(()=>{void refresh();return()=>{generation.current++;};},[refresh]);
  async function remove(id:string) {if(busy)return;setBusy(true);setError("");try{await api(`/memory/${encodeURIComponent(id)}`,{method:"DELETE"});setConfirm(null);await refresh();}
    catch(e){setError(message(e));}finally{setBusy(false);}}
  return <><div className="eyebrow">ATTRIBUTED MEMORY</div><h1>What the runtime remembers.</h1><p className="lead">Inspect saved knowledge and its source. Procedural candidates remain unreviewed.</p>
    <section className="panel"><label htmlFor="memory-search">Search memory</label><input id="memory-search" value={query} onChange={e=>setQuery(e.target.value)}/>
      <label htmlFor="memory-category">Memory type</label><select id="memory-category" value={category} onChange={e=>setCategory(e.target.value)}>
        <option value="">All types</option>{["working","episodic","semantic","procedural"].map(c=><option key={c}>{c}</option>)}</select>
      {error && <p role="alert" className="error">{error}</p>}<button className="secondary" disabled={busy} onClick={refresh}>Refresh memory</button>
      {busy && <p role="status">Loading memory…</p>}{!busy&&!items.length&&<p>No matching memories.</p>}
      {items.map(item=><article key={item.id} className="memory-item"><span className="badge">{item.type}</span><pre>{item.content}</pre>
        <p><Link href={`/tasks/${encodeURIComponent(item.source_task_id)}`}>Source task: {item.source_task_id}</Link></p>
        <small>Importance {item.importance} · Created {new Date(item.created_at*1000).toISOString()}{item.expires_at ? ` · Expires ${new Date(item.expires_at*1000).toISOString()}`:""}</small>
        <div>{confirm===item.id ? <><p>Delete this memory permanently?</p><button className="danger" disabled={busy} onClick={()=>remove(item.id)}>Delete memory</button> <button className="secondary" onClick={()=>setConfirm(null)}>Keep memory</button></> :
          <button className="secondary" disabled={busy} onClick={()=>setConfirm(item.id)}>Remove</button>}</div></article>)}</section></>;
}
export function SettingsForm() {
  const [value,setValue]=useState<RuntimeSettings|null>(null),[model,setModel]=useState(""),[timeout,setTimeoutValue]=useState("120");
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[saved,setSaved]=useState(false);
  const load=useCallback(async()=>{setBusy(true);try{const data=await api<RuntimeSettings>("/settings");setValue(data);setModel(data.default_model??"");setTimeoutValue(String(data.model_timeout));setError("");}
    catch(e){setError(message(e));}finally{setBusy(false);}},[]);
  useEffect(()=>{void load();},[load]);
  async function save(e:React.FormEvent){e.preventDefault();if(busy)return;setSaved(false);setError("");
    const seconds=Number(timeout);if(!Number.isFinite(seconds)||seconds<=0||seconds>3600){setError("Timeout must be greater than 0 and at most 3,600 seconds.");return;}
    setBusy(true);try{const data=await api<RuntimeSettings>("/settings",{method:"PATCH",body:JSON.stringify({default_model:model.trim()||null,model_timeout:seconds})});setValue(data);setSaved(true);}
    catch(e){setError(message(e));}finally{setBusy(false);}}
  return <><div className="eyebrow">RUNTIME CONFIGURATION</div><h1>Make it your workspace.</h1><p className="lead">Settings are saved by the backend and apply to subsequent work.</p>
    <section className="panel">{error&&<p role="alert" className="error">{error}</p>}{!value ? <><p>Loading settings…</p><button onClick={load} disabled={busy}>Retry settings</button></> :
      <form onSubmit={save} noValidate><label htmlFor="default-model">Default model</label><input id="default-model" value={model} maxLength={200} disabled={busy} onChange={e=>{setModel(e.target.value);setSaved(false);}}/>
        <small>Use an installed model name. Leave blank to choose for each task.</small><label htmlFor="timeout">Model timeout (seconds)</label>
        <input id="timeout" type="number" value={timeout} disabled={busy} onChange={e=>{setTimeoutValue(e.target.value);setSaved(false);}}/>
        <button disabled={busy}>{busy?"Saving…":"Save settings"}</button>{saved&&<p role="status">Settings saved.</p>}</form>}</section></>;
}
