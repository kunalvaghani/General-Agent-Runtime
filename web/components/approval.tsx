"use client";
import { useRef, useState } from "react";
import { ApiError } from "../lib/api";
import { submitApproval, type ApprovalChoice } from "../lib/approval";
import type { Pending } from "../lib/types";
export function Approval({taskId,pending,submit=submitApproval,onRefresh}: {
  taskId:string;pending:Pending;submit?:(choice:ApprovalChoice)=>Promise<void>;onRefresh?:()=>void;
}) {
  const [busy,setBusy] = useState(false), [done,setDone] = useState(false), [stale,setStale] = useState(false);
  const [error,setError] = useState(""); const lock=useRef(false);
  async function choose(approve:boolean) {
    if(lock.current || done || stale) return;
    lock.current=true;setBusy(true);setError("");
    try {await submit({taskId,requestId:pending.id,approve});setDone(true);onRefresh?.();}
    catch(e) {
      if(e instanceof ApiError && e.status===409) {setStale(true);setError("This request has changed or was already handled. Refresh to review the current request.");}
      else setError(e instanceof Error ? e.message : "Could not send your decision. Review the request and retry.");
    } finally {lock.current=false;setBusy(false);}
  }
  return <section className="panel approval" aria-labelledby="approval-title"><div className="row"><h2 id="approval-title">Permission requested</h2>
    <span className="badge WAITING_APPROVAL">REQUIRES YOUR REVIEW</span></div>
    <p>Review the exact action before granting permission for this request.</p>
    <dl><dt>Action</dt><dd>{pending.decision.tool_name}</dd><dt>Reason</dt><dd>{pending.decision.reason}</dd>
      <dt>Step</dt><dd>{pending.step_id}</dd><dt>Request ID</dt><dd><code>{pending.id}</code></dd></dl>
    <h3>Exact arguments</h3><pre>{JSON.stringify(pending.decision.arguments,null,2)}</pre>
    <p className="muted">Permission applies once to this request. Rejecting a live request cancels the task. The backend validates the request and remains authoritative.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {stale && <button className="secondary" onClick={onRefresh}>Refresh request</button>}
    {done ? <p role="status">Decision sent. Waiting for the backend’s task update.</p> :
      <div className="row" style={{justifyContent:"flex-start"}}><button onClick={()=>choose(true)} disabled={busy||stale}>{busy ? "Sending…" : "Approve once"}</button>
        <button className="secondary" onClick={()=>choose(false)} disabled={busy||stale}>Reject</button></div>}
  </section>;
}
