import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TaskDetail } from "../components/task-detail";
import { examples } from "./fixtures/tasks";
it("renders backend evidence separately from task status", async () => {
  render(<TaskDetail id="example-completed" live={false} load={async()=>({task:examples[1],plan:null,events:[]})}/>);
  await screen.findByText("Example: artifact contents matched");
  expect(screen.getByText("PASSED")).toBeInTheDocument();
});
it("handles missing tasks without inventing a plan", async () => {
  render(<TaskDetail id="missing" live={false} load={async () => null}/>);
  await screen.findByRole("heading",{name:"Task not found"});
});
it("escapes untrusted tool text and distinguishes missing verification", async () => {
  const task = structuredClone(examples[0]);
  task.metadata.execution!.observations = [{step_id:"test",tool:"terminal.run",status:"error",output:"<script>bad()</script>",error:"Test failed"}];
  render(<TaskDetail id={task.id} live={false} load={async () => ({task,plan:null,events:[]})}/>);
  await screen.findByText("<script>bad()</script>");
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByText("No verification evidence yet.")).toBeInTheDocument();
});

