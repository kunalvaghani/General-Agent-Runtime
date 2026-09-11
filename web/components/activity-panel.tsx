"use client";
import { useEffect, useState } from "react";
import type { ConnectionState } from "../lib/events";
import type { RuntimeEvent, Task } from "../lib/types";

export function describeEvent(event: RuntimeEvent): string {
  const data = event.data;
  const text = (key: string) => typeof data[key] === "string" ? String(data[key]) : "";
  switch (event.event) {
    case "recovery.started": return text("message") || "Trying a different permitted approach";
    case "recovery.stopped": return text("message") || "Automatic recovery stopped";
    case "model.requested": return `Waiting for ${text("model") || "the model"} · ${text("role") || "generation"}`;
    case "model.responded": return text("message") || `Model response received · ${text("role") || "generation"}`;
    case "plan.created": return "Execution plan saved";
    case "plan.revised": return "Execution plan updated";
    case "step.started": return `Started step ${text("step_id")}`;
    case "step.completed": return `Completed step ${text("step_id")}`;
    case "step.failed": return `Step ${text("step_id")} failed`;
    case "tool.started": case "tool.requested": return `Running tool: ${text("tool") || text("tool_name") || "requested tool"}`;
    case "tool.completed": return `Tool finished: ${text("tool") || "tool"}`;
    case "tool.failed": return `Tool failed: ${text("tool") || "tool"} · ${text("error") || "See tool output"}`;
    case "approval.required": return "Paused for your approval";
    case "task.status_changed": return `Task is ${text("to").toLowerCase().replaceAll("_", " ")}`;
    default: return event.event.replaceAll(".", " · ").replaceAll("_", " ");
  }
}

const stopped: Record<string, string> = {
  COMPLETED: "Completed — execution finished",
  FAILED: "Failed — execution stopped",
  CANCELLED: "Cancelled — no longer running",
  BLOCKED: "Blocked — action needed before continuing",
  WAITING_APPROVAL: "Paused — waiting for your approval",
  PENDING: "Pending — waiting to start",
};
function age(now: number, timestamp: string | number) {
  const seconds = Math.max(0, Math.floor((now - new Date(timestamp).getTime()) / 1000));
  if (!Number.isFinite(seconds)) return "unknown";
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function ActivityPanel({ task, events, connection, checkedAt, error, live }: {
  task: Task; events: RuntimeEvent[]; connection: ConnectionState;
  checkedAt: number; error: string; live: boolean;
}) {
  const [now, setNow] = useState(Date.now);
  const [expanded, setExpanded] = useState(true);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const latest = events.at(-1);
  const stale = !!error || !checkedAt || now - checkedAt > 20000;
  const headline = stopped[task.status] || (latest ? describeEvent(latest) : `Task is ${task.status.toLowerCase()}`);
  const active = !stopped[task.status] && live && !stale;
  return <section className="activity-panel" aria-label="Live task activity">
    <div className="row"><div role="status" aria-live="polite">
      <span className={`activity-dot ${active ? "active" : ""}`} aria-hidden="true"/>
      <strong>{stale && live ? "Connection uncertain — last reported: " : ""}{headline}</strong>
    </div><button className="secondary" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      {expanded ? "Hide updates" : "Show updates"}</button></div>
    <p className="activity-meta">
      {live ? (stale ? "Server status unavailable" : `Server checked ${age(now, checkedAt)} ago`) : "Saved snapshot"}
      {" · "}{latest ? `Last event ${age(now, latest.timestamp)} ago` : "No events yet"}
      {live && ` · Event stream: ${connection}`}
    </p>
    {expanded && <div className="activity-updates">
      {active && latest?.event === "model.requested" && <p>Waiting for a model response. No new output yet; elapsed time does not confirm model progress.</p>}
      {error && <p className="error">{error}</p>}
      <ol aria-label="Recent task updates">{events.slice(-5).map(event => <li key={event.id}>
        <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString()}</time>
        <span>{describeEvent(event)}</span>
      </li>)}</ol>
    </div>}
  </section>;
}
