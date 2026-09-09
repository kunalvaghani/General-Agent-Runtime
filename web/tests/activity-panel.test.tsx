import { afterEach, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { ActivityPanel } from "../components/activity-panel";
import { EventFeed } from "../components/event-feed";
import { examples } from "./fixtures/tasks";
import type { RuntimeEvent, Task } from "../lib/types";

afterEach(() => vi.useRealTimers());
const event: RuntimeEvent = {id:1,task_id:"t",event:"model.requested",timestamp:"2026-09-09T18:00:00Z",data:{model:"local-model",role:"planner"}};
const task: Task = {...examples[0],id:"t",status:"PLANNING"};
it("counts waiting time without presenting elapsed time as model progress", () => {
  vi.useFakeTimers(); vi.setSystemTime(new Date(event.timestamp));
  render(<ActivityPanel task={task} events={[event]} connection="live" checkedAt={Date.now()} error="" live/>);
  expect(screen.getByText(/elapsed time does not confirm model progress/)).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(10000));
  expect(screen.getByText(/Last event 10s ago/)).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(11000));
  expect(screen.getByText(/Connection uncertain/)).toBeInTheDocument();
});
it("shows cancellation even if the last model event is still a request", () => {
  render(<ActivityPanel task={{...task,status:"CANCELLED"}} events={[event]} connection="finished" checkedAt={Date.now()} error="" live/>);
  expect(screen.getByText("Cancelled — no longer running")).toBeInTheDocument();
  expect(document.querySelector(".activity-dot.active")).toBeNull();
});
it("shows connection failures without inventing a stopped task", () => {
  render(<ActivityPanel task={task} events={[event]} connection="reconnecting" checkedAt={Date.now()} error="Backend unavailable" live/>);
  expect(screen.getByText(/Connection uncertain/)).toBeInTheDocument();
  expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
});
it("updates saved events when snapshot polling discovers events missing from the stream", () => {
  const {rerender}=render(<EventFeed taskId="t" initial={[event]}/>);
  const failed={...event,id:2,event:"tool.failed",data:{tool:"python.run",error:"command_failed"}};
  rerender(<EventFeed taskId="t" initial={[event,failed]}/>);
  expect(screen.getByText(/#2 · tool.failed/)).toBeInTheDocument();
});
