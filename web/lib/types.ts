export type Status = "PENDING" | "PLANNING" | "RUNNING" | "WAITING_APPROVAL" | "BLOCKED" |
  "VERIFYING" | "COMPLETED" | "FAILED" | "CANCELLED";
export interface Step { id: string; description: string; expected_output: string;
  dependencies: string[]; status: string; attempts: number; }
export interface Plan { objective: string; revision: number; steps: Step[]; completion_criteria: string[]; }
export interface Pending { id: string; step_id: string; decision: { reason: string;
  tool_name: string; arguments: Record<string, unknown> }; }
export interface Observation { call_id?: string; step_id: string; tool: string; status: string;
  output: string; exit_code?: number; error?: string; }
export interface Task { id: string; goal: string; model_id: string; status: Status;
  created_at: string; updated_at: string; current_step: string | null; workspace: string;
  max_steps: number; metadata: { execution?: { pending?: Pending; observations: Observation[] };
    verification?: { passed: boolean; evidence: string[]; issues: string[] } }; }
export interface RuntimeEvent { id: number; event: string; task_id: string; timestamp: string;
  data: Record<string, unknown>; }
export interface Model { id: string; provider: string; local?: boolean; }
export interface NewTask { goal: string; model: string; max_steps: number; }
