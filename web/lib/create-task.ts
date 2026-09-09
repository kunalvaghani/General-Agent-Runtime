import type { NewTask, Task } from "./types";
import { api } from "./api";
export function validateTaskInput(input: NewTask): NewTask {
  const value = {...input, goal: input.goal.trim(), model: input.model.trim()};
  if (!value.goal || value.goal.length > 20000) throw new Error("Enter a goal between 1 and 20,000 characters.");
  if (!value.model || value.model.length > 200) throw new Error("Choose a model.");
  if (!Number.isInteger(value.max_steps) || value.max_steps < 1 || value.max_steps > 1000)
    throw new Error("Step budget must be a whole number from 1 to 1,000.");
  return value;
}
export async function createTask(input: NewTask): Promise<Task> {
  return api<Task>("/tasks",{method:"POST",body:JSON.stringify({...validateTaskInput(input),start:true})});
}
