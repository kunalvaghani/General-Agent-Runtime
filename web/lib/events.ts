import type { RuntimeEvent } from "./types";
export type ConnectionState = "connecting" | "live" | "reconnecting" | "finished" | "error";
export interface EventSourceLike {
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  addEventListener(type: string, callback: EventListener): void;
  close(): void;
}
export function taskEventsUrl(id: string) {
  const base = process.env.NEXT_PUBLIC_GAR_API_URL || "/api/v1";
  return `${base}/tasks/${encodeURIComponent(id)}/events`;
}
export function connectEvents(options: { url: string; taskId: string; after?: number;
  onEvent: (event: RuntimeEvent) => void; onState: (state: ConnectionState) => void;
  factory?: (url: string) => EventSourceLike }) {
  let cursor = options.after ?? 0;
  let stopped = false;
  let attempt = 0;
  let source: EventSourceLike | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const factory = options.factory ?? (url => new EventSource(url));
  function fail() { if (stopped) return; stopped = true; source?.close(); options.onState("error"); }
  function open() {
    if (stopped) return;
    options.onState(attempt ? "reconnecting" : "connecting");
    const url = new URL(options.url, window.location.href); url.searchParams.set("after",String(cursor));
    try { source = factory(url.toString()); } catch { fail(); return; }
    const current = source;
    current.onopen = () => { if (!stopped && source === current) options.onState("live"); };
    current.onmessage = message => {
      if (stopped || source !== current) return;
      let event: RuntimeEvent;
      try {
        event = JSON.parse(message.data);
        if (!event || !Number.isSafeInteger(event.id) || event.id < 1 || event.task_id !== options.taskId ||
          typeof event.event !== "string" || typeof event.timestamp !== "string" || !event.data || typeof event.data !== "object" || Array.isArray(event.data) ||
          (message.lastEventId && message.lastEventId !== String(event.id))) throw new Error("Invalid event");
      } catch { fail(); return; }
      // Backend replays in journal order. Older IDs are duplicate/stale deliveries.
      if (event.id <= cursor) return;
      try { options.onEvent(event); } catch { fail(); return; }
      cursor = event.id; attempt = 0;
    };
    current.onerror = () => {
      if (stopped || source !== current) return;
      current.close(); source = undefined; options.onState("reconnecting");
      timer = setTimeout(open, Math.min(1000 * 2 ** attempt++, 15000));
    };
    current.addEventListener("end", () => {
      if (stopped || source !== current) return;
      stopped = true; current.close(); options.onState("finished");
    });
  }
  open();
  return () => { stopped = true; clearTimeout(timer); source?.close(); };
}
