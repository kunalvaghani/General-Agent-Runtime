import { it, expect, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NewTaskForm } from "../components/new-task";
import { createTask, validateTaskInput } from "../lib/create-task";
const loadModels=async()=>({models:[{id:"m",provider:"ollama"}],defaultModel:"m"});
afterEach(()=>vi.unstubAllGlobals());
it("rejects empty goals and invalid step budgets", () => {
  expect(() => validateTaskInput({goal:" ", model:"m", max_steps:1})).toThrow("Enter a goal");
  for (const max_steps of [0, 1001, 1.5, NaN]) expect(() => validateTaskInput({goal:"x",model:"m",max_steps})).toThrow("whole number");
});
it("submits a real task with bounded steps and explicit start", async () => {
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:"backend-id"})});vi.stubGlobal("fetch",fetch);
  const task = await createTask({goal:" Check data ",model:"m",max_steps:3});
  expect(task.id).toBe("backend-id");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({goal:"Check data",model:"m",max_steps:3,start:true});
});
it("preserves inputs on failure and prevents repeated submission", async () => {
  let reject!: (e: Error) => void;
  const save = vi.fn(() => new Promise<never>((_, fail) => {reject = fail;}));
  render(<NewTaskForm save={save} loadModels={loadModels}/>);
  const button=screen.getByRole("button",{name:"Create task"});
  await waitFor(()=>expect(button).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Goal"), {target:{value:"Keep my goal"}});
  fireEvent.click(button); fireEvent.click(button);
  expect(save).toHaveBeenCalledTimes(1); expect(button).toBeDisabled();
  reject(new Error("API unavailable"));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("API unavailable"));
  expect(screen.getByLabelText("Goal")).toHaveValue("Keep my goal");
});

