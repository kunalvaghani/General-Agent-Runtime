import type { Plan, RuntimeEvent, Task } from "./types";
import { api, ApiError } from "./api";
export interface TaskDetail { task: Task; plan: Plan | null; events: RuntimeEvent[]; }
export async function readDetail(id: string): Promise<TaskDetail | null> {
  try {return await api<TaskDetail>(`/tasks/${encodeURIComponent(id)}/snapshot`);}
  catch(e){if(e instanceof ApiError && e.status===404)return null;throw e;}
}
