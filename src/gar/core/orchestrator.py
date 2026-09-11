"""Single bounded runtime shared by CLI and API."""

import json

from gar.core.events import EventType
from gar.core.executor import Executor
from gar.core.planner import Planner, PlanningService
from gar.core.state import Plan, StepStatus, TaskStatus
from gar.core.verifier import Verifier
from gar.models.base import ModelError


class Orchestrator:
    def __init__(self, repo, adapter, tools, memory=None):
        self.repo, self.adapter, self.tools = repo, adapter, tools
        self.memory = memory

    @staticmethod
    def repair_context(task, plan):
        """Keep current failure and prior work instead of slicing raw metadata."""
        execution = task.metadata.get("execution", {})
        observations = execution.get("observations", [])
        failure = execution.get("last_failure") or {}
        if not failure:
            for result in reversed(observations):
                if result.get("status") == "ok" and result.get("tool") in (
                    "filesystem.write",
                    "python.run",
                    "terminal.run",
                ):
                    break
                if result.get("status") == "error":
                    failure = result
                    break
        context = {
            "mode": "repair_existing_work",
            "reason": str(execution.get("replan_requested", ""))[:1000],
            "failure": {
                "error": str(failure.get("error", ""))[:100],
                "output": str(failure.get("output", ""))[:2000],
            },
            "verification_issues": [
                str(issue)[:300]
                for issue in task.metadata.get("verification", {}).get("issues", [])[:8]
            ],
            "previous_steps": [
                {"id": s.id, "status": s.status.value, "description": s.description[:200]}
                for s in (plan.steps[:20] if plan else [])
            ],
            "written_files": list(
                dict.fromkeys(
                    str(o.get("arguments", {}).get("path", ""))[:200]
                    for o in observations
                    if o.get("tool") == "filesystem.write" and o.get("status") == "ok"
                )
            )[-20:],
            "recent_results": [
                {
                    "tool": o.get("tool"),
                    "status": o.get("status"),
                    "error": o.get("error"),
                    "output": str(o.get("output", ""))[:500],
                }
                for o in observations[-4:]
            ],
        }
        # Retain valid JSON and failure evidence even for unusually escaped output.
        while len(json.dumps(context, ensure_ascii=False)) > 20000:
            for key in ("recent_results", "written_files", "previous_steps", "verification_issues"):
                if context[key]:
                    context[key].pop(0)
                    break
            else:
                context["failure"]["output"] = context["failure"]["output"][:1000]
                context["reason"] = context["reason"][:500]
        return json.dumps(context, ensure_ascii=False)

    async def run(self, task_id, approval_id=None, retry=False):
        task = self.repo.get(task_id)
        if self.repo.get_plan(task_id) is None:
            context = ""
            if self.memory:
                context = "\n".join(
                    i.content for i in self.memory.search(source=task_id, category="working")
                )[:20000]
            await PlanningService(self.repo, Planner(self.adapter)).plan_task(task_id, context)
        if retry:
            task = self.repo.get(task_id)
            execution = task.metadata.get("execution", {})
            plan = self.repo.get_plan(task_id)
            if not plan.can_retry_failed_steps:
                if execution.get("decisions", 0) >= task.max_steps:
                    return task
                if task.metadata.get("replans", 0) >= 2:
                    return task
                task = await self.replan(task_id)
                if task.status == TaskStatus.BLOCKED:
                    return task
            else:
                self.repo.prepare_retry(task_id)
        task = self.repo.get(task_id)
        if task.status != TaskStatus.VERIFYING:
            task = await Executor(self.repo, self.adapter, self.tools).run(task_id, approval_id)
        while task.status == TaskStatus.BLOCKED:
            state = task.metadata.get("execution", {})
            if state.get("replan_requested"):
                if (
                    state.get("decisions", 0) >= task.max_steps
                    or task.metadata.get("replans", 0) >= 2
                ):
                    break
                task = self.repo.record_event(
                    task_id,
                    EventType.RECOVERY_STARTED,
                    {
                        "strategy": "replan",
                        "message": "Revising the plan as requested by the executor.",
                    },
                    task.version,
                )
                task = await self.replan(task_id)
                if task.status == TaskStatus.BLOCKED:
                    break
                task = await Executor(self.repo, self.adapter, self.tools).run(task_id)
                continue
            observations = state.get("observations", [])
            latest = state.get("last_failure") or (observations[-1] if observations else {})
            recoverable = latest.get("error") in {
                "command_denied",
                "command_failed",
                "invalid_arguments",
                "unknown_tool",
                "timeout",
                "no_progress",
            }
            if not recoverable or state.get("decisions", 0) >= task.max_steps:
                break
            if self.repo.get_plan(task_id).can_retry_failed_steps:
                task = self.repo.record_event(
                    task_id,
                    EventType.RECOVERY_STARTED,
                    {
                        "strategy": "retry",
                        "reason": latest.get("error"),
                        "message": "Using failure evidence to choose a different permitted action.",
                    },
                    task.version,
                )
                try:
                    self.repo.prepare_retry(task_id)
                except ValueError:
                    break
            elif task.metadata.get("replans", 0) < 2:
                task = self.repo.record_event(
                    task_id,
                    EventType.RECOVERY_STARTED,
                    {
                        "strategy": "replan",
                        "reason": latest.get("error"),
                        "message": "Revising the plan after unsuccessful attempts.",
                    },
                    task.version,
                )
                task = await self.replan(task_id)
                if task.status == TaskStatus.BLOCKED:
                    break
            else:
                break
            task = await Executor(self.repo, self.adapter, self.tools).run(task_id)
        if task.status == TaskStatus.BLOCKED:
            state = task.metadata.get("execution", {})
            if state.get("decisions", 0) >= task.max_steps:
                reason = "Execution decision budget exhausted."
            elif state.get("replan_requested"):
                reason = "Replan limit reached: " + str(state["replan_requested"])
            else:
                failure = state.get("last_failure", {})
                reason = str(
                    failure.get("output")
                    or failure.get("error")
                    or "No permitted recovery remains; inspect the latest tool or verification"
                    " result."
                )
            self.repo.record_event(
                task_id,
                EventType.RECOVERY_STOPPED,
                {"message": "Stopped: " + reason},
                task.version,
            )
        if task.status == TaskStatus.VERIFYING:
            verification = await Verifier().verify(self.repo, task_id, self.tools, self.adapter)
            task = self.repo.get(task_id)
            if (
                not verification.passed
                and task.metadata.get("replans", 0) < 2
                and task.metadata.get("execution", {}).get("decisions", 0) < task.max_steps
            ):
                return await self.run(task_id, retry=True)
        result = self.repo.get(task_id)
        if result.is_terminal and self.memory:
            from gar.learning.reflection import reflect

            reflect(result, self.memory)
        return result

    async def replan(self, task_id):
        task = self.repo.get(task_id)
        if task.status != TaskStatus.BLOCKED:
            raise ValueError("Only blocked tasks can replan")
        count = task.metadata.get("replans", 0)
        if count >= 2:
            raise ValueError("Replan limit reached")
        previous = self.repo.get_plan(task_id)
        task = self.repo.transition(task_id, TaskStatus.PLANNING, task.version)
        task = self.repo.checkpoint(
            task_id,
            {"metadata": {**task.metadata, "replans": count + 1}},
            task.version,
            EventType.MODEL_REQUESTED,
            {"role": "replanner"},
        )
        try:
            proposal = await Executor(self.repo, self.adapter, self.tools).waiting(
                Planner(self.adapter).create_plan(
                    task,
                    self.repair_context(task, previous),
                    completed_step_ids=[
                        s.id for s in previous.steps if s.status == StepStatus.COMPLETED
                    ]
                    if previous
                    else [],
                ),
                task_id,
            )
            proposal = Plan.model_validate(
                {**proposal.model_dump(), "revision": previous.revision + 1 if previous else 1}
            )
        except (ModelError, ValueError):
            return self.repo.transition(task_id, TaskStatus.BLOCKED, task.version)
        task = self.repo.record_event(
            task_id, EventType.MODEL_RESPONDED, {"role": "replanner"}, task.version
        )
        self.repo.save_plan(proposal, task.version)
        return self.repo.get(task_id)
