"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
type Session = {id:string;state:string;entry:string;workspace:string;image:string;files:Record<string,string>;test_output?:string;output?:string};
export function Desktop({taskId, verified}:{taskId:string;verified:boolean}) {
  const [entry,setEntry]=useState("app.py"),[session,setSession]=useState<Session|null>(null);
  const [attach,setAttach]=useState(""),[text,setText]=useState("");
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[frame,setFrame]=useState("");
  const frameRef=useRef("");
  const base=`/tasks/${encodeURIComponent(taskId)}/desktop`;
  async function perform(action:()=>Promise<Session>) {
    setBusy(true);setError("");try{setSession(await action());}catch(e){setError(e instanceof Error?e.message:"Desktop request failed");}finally{setBusy(false);}
  }
  useEffect(()=>{
    if(session?.state!=="running")return;
    let stopped=false;
    let timer:ReturnType<typeof setTimeout>;
    const abort=new AbortController();
    async function refresh(){
      try{
        const current=await api<Session>(`${base}/${session!.id}`,{signal:abort.signal});
        if(stopped)return;
        setSession(current);
        if(current.state!=="running")return;
        const response=await fetch(`/api/v1${base}/${current.id}/frame`,{cache:"no-store",signal:abort.signal});
        if(!response.ok)throw new Error("Desktop is starting or its display is unavailable.");
        const blob=await response.blob();if(stopped)return;
        const url=URL.createObjectURL(blob);URL.revokeObjectURL(frameRef.current);frameRef.current=url;setFrame(url);setError("");
      }catch(e){if(!stopped)setError(e instanceof Error?e.message:"Desktop disconnected");}
      finally{if(!stopped)timer=setTimeout(refresh,1000);}
    }
    void refresh();return()=>{stopped=true;abort.abort();clearTimeout(timer);URL.revokeObjectURL(frameRef.current);};
  },[session?.id,session?.state,base]);
  async function input(data:object){
    try{await api(`${base}/${session!.id}/input/send`,{method:"POST",body:JSON.stringify(data)});}
    catch(e){setError(e instanceof Error?e.message:"Input failed");}
  }
  return <section className="panel"><h2>Isolated desktop</h2>
    <p>Run a Python GUI in Docker. No network or writable host folders. Changes inside the desktop are temporary.</p>
    {!verified&&<p>Task verification must pass first.</p>}
    <label>Python entry file<input value={entry} onChange={e=>setEntry(e.target.value)} placeholder="calculator.py"/></label>
    <button disabled={!verified||busy||session?.state==="running"} onClick={()=>perform(()=>api(base,{method:"POST",body:JSON.stringify({entry}),signal:AbortSignal.timeout(150000)}))}>
      {busy?"Working…":"Test frozen copy"}</button>
    {session?.state==="awaiting_approval"&&<div className="approval panel" style={{marginTop:16}}>
      <h3>Tests passed — approve desktop launch?</h3><p>Launch <strong>{session.entry}</strong> from the tested copy of {session.workspace}.</p>
      <p>Only this copy is shared, read-only. The app runs as a non-root user inside Docker. No host shell, network, or clipboard sharing.</p>
      <pre>{session.test_output}</pre><details><summary>Review tested file hashes and image</summary><pre>{session.image}{"\n"}{JSON.stringify(session.files,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>perform(()=>api(`${base}/${session.id}/approve`,{method:"POST"}))}>Approve and open isolated desktop</button>{" "}
      <button className="secondary" disabled={busy} onClick={()=>perform(()=>api(`${base}/${session.id}/stop`,{method:"POST"}))}>Reject</button>
    </div>}
    {session&&<p role="status">Desktop: {session.state.replaceAll("_"," ")} · {session.id}</p>}
    {session?.output&&<pre>{session.output}</pre>}
    {session?.state==="running"&&<>
      <button className="secondary" disabled={busy} onClick={()=>perform(()=>api(`${base}/${session.id}/stop`,{method:"POST"}))}>Stop desktop</button>
      {frame&&<img src={frame} alt="Isolated desktop. Click to interact with the app." style={{width:"100%",marginTop:12,border:"1px solid #ccc"}} onClick={e=>{
        const rect=e.currentTarget.getBoundingClientRect();void input({kind:"click",x:Math.min(1023,Math.floor((e.clientX-rect.left)/rect.width*1024)),y:Math.min(767,Math.floor((e.clientY-rect.top)/rect.height*768))});
      }}/>}
      <label>Text to type inside the desktop<input value={text} maxLength={200} onChange={e=>setText(e.target.value)}/></label>
      <button className="secondary" onClick={()=>{void input({kind:"text",value:text});setText("");}}>Send text</button>{" "}
      {(["Return","Tab","BackSpace","Escape"] as const).map(key=><button key={key} className="secondary" onClick={()=>input({kind:"key",value:key})}>{key}</button>)}
    </>}
    <details><summary>Attach an existing CLI desktop session</summary>
      <p>Only for a session already created with gar desktop prepare. Use its desktop session ID, not the task ID from this page. To create a new session here, use Test frozen copy after verification passes.</p>
      <label>Desktop session ID<input value={attach} onChange={e=>setAttach(e.target.value.trim())}/></label>
      <button disabled={busy||!attach} onClick={()=>{
        if(attach===taskId){setError("This is the task ID. Enter the desktop session ID returned by gar desktop prepare.");return;}
        void perform(()=>api(`${base}/${encodeURIComponent(attach)}`));
      }}>Attach</button></details>
    {error&&<p role="alert" className="error">{error}</p>}
  </section>;
}
