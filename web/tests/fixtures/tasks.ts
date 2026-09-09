import type { Task } from "../../lib/types";
// Fixed UI examples, never a simulated agent or evidence of runtime execution.
export const examples: Task[] = [
  { id: "example-approval", goal: "Add tests for the workspace parser", status: "WAITING_APPROVAL",
    model_id: "example-local-model", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:02:00Z",
    current_step: "test", workspace: "preview/workspace", max_steps: 12,
    metadata: { execution: { observations: [], pending: { id: "example-request-1", step_id: "test",
      decision: { tool_name: "terminal.run", arguments: { argv: ["python", "-m", "pytest"] },
        reason: "Run the workspace tests inside the restricted container." } } } } },
  { id: "example-completed", goal: "Create and verify a CSV summary utility", status: "COMPLETED",
    model_id: "example-local-model", created_at: "2026-09-01T09:00:00Z", updated_at: "2026-09-01T09:05:00Z",
    current_step: null, workspace: "preview/workspace", max_steps: 10,
    metadata: { verification: { passed: true, evidence: ["Example: artifact contents matched", "Example: workspace tests passed"], issues: [] } } },
  { id: "example-blocked", goal: "Inspect an unavailable input dataset", status: "BLOCKED",
    model_id: "example-local-model", created_at: "2026-09-01T08:00:00Z", updated_at: "2026-09-01T08:01:00Z",
    current_step: "inspect", workspace: "preview/workspace", max_steps: 8, metadata: {} },
];

