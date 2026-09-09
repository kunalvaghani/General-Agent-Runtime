import { it, expect, vi, afterEach } from "vitest";
import { connectEvents, type EventSourceLike } from "../lib/events";
class Source implements EventSourceLike {
  onopen: EventSourceLike["onopen"] = null; onmessage: EventSourceLike["onmessage"] = null; onerror: EventSourceLike["onerror"] = null;
  close = vi.fn(); end: EventListener = () => {};
  addEventListener(_type:string, callback:EventListener) {this.end = callback;}
  send(id:number, task_id="t") {this.onmessage?.(new MessageEvent("message", {data:JSON.stringify({id,task_id,event:"step.completed",timestamp:"2026-09-01",data:{}}),lastEventId:String(id)}));}
}
afterEach(() => vi.useRealTimers());
it("deduplicates ordered replay, resumes at cursor, and closes on terminal event", () => {
  vi.useFakeTimers(); const sources:Source[] = []; const urls:string[] = [];
  const onEvent=vi.fn(), onState=vi.fn();
  const stop=connectEvents({url:"http://localhost/events",taskId:"t",onEvent,onState,factory:url=>{urls.push(url); const s=new Source();sources.push(s);return s;}});
  sources[0].send(2); sources[0].send(2); sources[0].send(1);
  expect(onEvent).toHaveBeenCalledTimes(1);
  sources[0].onerror?.(new Event("error")); vi.advanceTimersByTime(1000);
  expect(urls[1]).toContain("after=2"); expect(sources[0].close).toHaveBeenCalledOnce();
  sources[1].send(3); sources[1].end(new Event("end"));
  expect(onState).toHaveBeenLastCalledWith("finished");
  sources[1].send(4); expect(onEvent).toHaveBeenCalledTimes(2);
  vi.advanceTimersByTime(60000); expect(sources).toHaveLength(2); stop();
});
it("rejects malformed or cross-task events without advancing the cursor", () => {
  const source=new Source(), onEvent=vi.fn(), onState=vi.fn();
  connectEvents({url:"http://localhost/events",taskId:"t",onEvent,onState,factory:()=>source});
  source.send(1,"other"); expect(onEvent).not.toHaveBeenCalled(); expect(onState).toHaveBeenLastCalledWith("error");
  expect(source.close).toHaveBeenCalledOnce();
});
it("cancels reconnect timers on unmount", () => {
  vi.useFakeTimers(); const source=new Source(),factory=vi.fn(()=>source);
  const stop=connectEvents({url:"http://localhost/events",taskId:"t",onEvent:vi.fn(),onState:vi.fn(),factory});
  source.onerror?.(new Event("error")); stop();vi.advanceTimersByTime(60000);
  expect(factory).toHaveBeenCalledOnce();
});
