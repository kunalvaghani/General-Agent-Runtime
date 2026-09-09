import { api } from "./api";
import type { Task } from "./types";
export interface ApprovalChoice { taskId: string; requestId: string; approve: boolean; }
export async function submitApproval(choice: ApprovalChoice): Promise<void> {
  await api<Task>(`/tasks/${encodeURIComponent(choice.taskId)}/approve`, {
    method:"POST",body:JSON.stringify({request_id:choice.requestId,approve:choice.approve}) });
}
