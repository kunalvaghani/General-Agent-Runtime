"""Transactional state changes with optimistic concurrency and durable events."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select, update

from gar.core.events import Event, EventType
from gar.core.state import Plan, Step, StepStatus, Task, TaskStatus, now, validate_transition
from gar.persistence.database import Database
from gar.persistence.models import events, plans, tasks


class TaskNotFound(ValueError):
    pass


class Conflict(ValueError):
    pass


class TaskRepository:
    def finish_verification(self, task_id, result, expected_version):
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            if task.status != TaskStatus.VERIFYING:
                raise Conflict("Task is no longer verifying")
            passed = result["passed"] and bool(result["evidence"]) and not result["issues"]
            target = TaskStatus.COMPLETED if passed else TaskStatus.BLOCKED
            updated = self._save(
                connection,
                task,
                {"status": target, "metadata": {**task.metadata, "verification": result}},
                expected_version,
            )
            self._event(
                connection,
                task_id,
                EventType.VERIFICATION_PASSED if passed else EventType.VERIFICATION_FAILED,
                result,
            )
            self._event(
                connection,
                task_id,
                EventType.TASK_COMPLETED if passed else EventType.TASK_BLOCKED,
                {"status": target.value},
            )
            return updated

    def prepare_retry(self, task_id):
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            state = dict(task.metadata.get("execution", {}))
            if task.status != TaskStatus.BLOCKED:
                raise ValueError("Task is not retryable or retry limit reached")
            plan = self._plan(connection, task_id)
            if plan is None:
                raise ValueError("Planning must be retried separately")
            failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
            if not failed:
                raise ValueError("No failed step to retry; use replan")
            if not plan.can_retry_failed_steps or state.get("decisions", 0) >= task.max_steps:
                raise ValueError("Step retry limit or task decision budget reached")
            new_plan = Plan.model_validate(
                {
                    **plan.model_dump(),
                    "steps": [
                        {**s.model_dump(), "status": StepStatus.PENDING} if s in failed else s
                        for s in plan.steps
                    ],
                }
            )
            state["retries"] = state.get("retries", 0) + 1
            updated = self._save(
                connection,
                task,
                {
                    "status": TaskStatus.RUNNING,
                    "current_step": None,
                    "metadata": {**task.metadata, "execution": state},
                },
                task.version,
            )
            connection.execute(
                update(plans)
                .where(plans.c.task_id == task_id, plans.c.revision == plan.revision)
                .values(snapshot=new_plan.model_dump_json())
            )
            self._event(
                connection,
                task_id,
                EventType.TASK_STATUS_CHANGED,
                {"from": "BLOCKED", "to": "RUNNING", "retry": state["retries"]},
            )
            return updated

    def __init__(self, database: Database) -> None:
        self.database = database

    def checkpoint(
        self, task_id: str, changes: dict, expected_version: int, kind: EventType, data: dict
    ) -> Task:
        """Runtime-owned metadata and telemetry, guarded against stale writers."""
        if set(changes) - {"metadata"}:
            raise ValueError("Checkpoint only accepts runtime metadata")
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            if task.is_terminal:
                raise Conflict("Task is terminal")
            updated = self._save(connection, task, changes, expected_version)
            self._event(connection, task_id, kind, data)
            return updated

    def _get(self, connection: Connection, task_id: str) -> Task:
        raw = connection.execute(select(tasks.c.snapshot).where(tasks.c.id == task_id)).scalar()
        if raw is None:
            raise TaskNotFound("Task not found")
        return Task.model_validate_json(raw)

    def get(self, task_id: str) -> Task:
        with self.database.engine.connect() as connection:
            return self._get(connection, task_id)

    def list(self) -> list[Task]:
        with self.database.engine.connect() as connection:
            result = connection.execute(select(tasks.c.snapshot).order_by(tasks.c.id)).scalars()
            return [Task.model_validate_json(raw) for raw in result]

    def _event(self, connection: Connection, task_id: str, kind: EventType, data: dict) -> None:
        connection.execute(
            insert(events).values(
                task_id=task_id,
                event=kind.value,
                timestamp=now().isoformat(),
                data=json.dumps(data),
            )
        )

    def create(self, task: Task) -> Task:
        task = Task.model_validate_json(task.model_dump_json())
        if task.status != TaskStatus.PENDING or task.version != 0 or task.current_step is not None:
            raise ValueError("New tasks must be pending with version zero and no active step")
        with self.database.engine.begin() as connection:
            connection.execute(
                insert(tasks).values(id=task.id, version=0, snapshot=task.model_dump_json())
            )
            self._event(connection, task.id, EventType.TASK_CREATED, {"status": task.status.value})
        return task

    def _save(
        self, connection: Connection, previous: Task, changes: dict, expected_version: int
    ) -> Task:
        if previous.version != expected_version:
            raise Conflict("Task changed; reload before updating")
        updated = Task.model_validate(
            {
                **previous.model_dump(),
                **changes,
                "version": previous.version + 1,
                "updated_at": now(),
            }
        )
        result = connection.execute(
            update(tasks)
            .where(tasks.c.id == previous.id, tasks.c.version == expected_version)
            .values(version=updated.version, snapshot=updated.model_dump_json())
        )
        if result.rowcount != 1:
            raise Conflict("Task changed; reload before updating")
        return updated

    def transition(self, task_id: str, target: TaskStatus, expected_version: int) -> Task:
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            validate_transition(task.status, target)
            if target == TaskStatus.RUNNING and self._plan(connection, task_id) is None:
                raise ValueError("A saved plan is required before running")
            if target == TaskStatus.VERIFYING:
                plan = self._plan(connection, task_id)
                if plan is None or any(s.status != StepStatus.COMPLETED for s in plan.steps):
                    raise ValueError("All plan steps must complete before verification")
            if target == TaskStatus.COMPLETED:
                # Stage 2 cannot establish objective evidence; Stage 6 owns completion.
                raise ValueError("Completion requires the future evidence-based verifier")
            updated = self._save(connection, task, {"status": target}, expected_version)
            kind = {
                TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
                TaskStatus.FAILED: EventType.TASK_FAILED,
                TaskStatus.BLOCKED: EventType.TASK_BLOCKED,
            }.get(target, EventType.TASK_STATUS_CHANGED)
            self._event(connection, task_id, kind, {"from": task.status.value, "to": target.value})
            return updated

    def _plan(self, connection: Connection, task_id: str) -> Plan | None:
        raw = connection.execute(
            select(plans.c.snapshot)
            .where(plans.c.task_id == task_id)
            .order_by(plans.c.revision.desc())
            .limit(1)
        ).scalar()
        return Plan.model_validate_json(raw) if raw else None

    def get_plan(self, task_id: str) -> Plan | None:
        with self.database.engine.connect() as connection:
            self._get(connection, task_id)
            return self._plan(connection, task_id)

    def snapshot(self, task_id: str) -> dict:
        """One SQLite read transaction prevents mismatched task/plan/event views."""
        with self.database.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            task = self._get(connection, task_id)
            plan = self._plan(connection, task_id)
            rows = list(
                connection.execute(
                    select(events)
                    .where(events.c.task_id == task_id)
                    .order_by(events.c.id.desc())
                    .limit(500)
                ).mappings()
            )
            journal = [
                Event(
                    id=row["id"],
                    task_id=task_id,
                    event=row["event"],
                    timestamp=row["timestamp"],
                    data=json.loads(row["data"]),
                )
                for row in reversed(rows)
            ]
            return {"task": task, "plan": plan, "events": journal}

    def save_plan(self, plan: Plan, expected_version: int) -> Task:
        plan = Plan.model_validate_json(plan.model_dump_json())
        with self.database.engine.begin() as connection:
            task = self._get(connection, plan.task_id)
            if task.status != TaskStatus.PLANNING:
                raise ValueError("Plans can only be saved during planning")
            if len(plan.steps) > task.max_steps:
                raise ValueError("Plan exceeds task step limit")
            previous = self._plan(connection, task.id)
            if plan.revision != (previous.revision + 1 if previous else 1):
                raise Conflict("Plan revision is not the next revision")
            if any(step.status != StepStatus.PENDING or step.attempts for step in plan.steps):
                raise ValueError("New plan steps must start pending without attempts")
            updated = self._save(connection, task, {"current_step": None}, expected_version)
            connection.execute(
                insert(plans).values(
                    task_id=task.id, revision=plan.revision, snapshot=plan.model_dump_json()
                )
            )
            self._event(
                connection,
                task.id,
                EventType.PLAN_REVISED if previous else EventType.PLAN_CREATED,
                {"revision": plan.revision},
            )
            return updated

    def transition_step(
        self, task_id: str, step_id: str, target: StepStatus, expected_version: int
    ) -> Task:
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            plan = self._plan(connection, task_id)
            if task.status != TaskStatus.RUNNING or plan is None:
                raise ValueError("Step changes require a running task with a plan")
            step = next((s for s in plan.steps if s.id == step_id), None)
            if step is None:
                raise ValueError("Step not found")
            allowed = {
                StepStatus.PENDING: {StepStatus.RUNNING},
                StepStatus.RUNNING: {StepStatus.COMPLETED, StepStatus.FAILED},
                StepStatus.FAILED: {StepStatus.RUNNING},
            }
            if target not in allowed.get(step.status, set()):
                raise ValueError("Invalid step transition")
            if target == StepStatus.RUNNING:
                done = {s.id for s in plan.steps if s.status == StepStatus.COMPLETED}
                if not set(step.dependencies) <= done or task.current_step is not None:
                    raise ValueError("Dependencies incomplete or another step is active")
            elif task.current_step != step_id:
                raise ValueError("Step is not active")
            changed = Step.model_validate(
                {
                    **step.model_dump(),
                    "status": target,
                    "attempts": step.attempts + (1 if target == StepStatus.RUNNING else 0),
                }
            )
            new_plan = Plan.model_validate(
                {
                    **plan.model_dump(),
                    "steps": [changed if s.id == step_id else s for s in plan.steps],
                }
            )
            updated = self._save(
                connection,
                task,
                {"current_step": step_id if target == StepStatus.RUNNING else None},
                expected_version,
            )
            connection.execute(
                update(plans)
                .where(plans.c.task_id == task_id, plans.c.revision == plan.revision)
                .values(snapshot=new_plan.model_dump_json())
            )
            kind = {
                StepStatus.RUNNING: EventType.STEP_STARTED,
                StepStatus.COMPLETED: EventType.STEP_COMPLETED,
                StepStatus.FAILED: EventType.STEP_FAILED,
            }[target]
            self._event(
                connection, task_id, kind, {"step_id": step_id, "attempts": changed.attempts}
            )
            return updated

    def get_events(self, task_id: str, after_id: int = 0) -> list[Event]:
        with self.database.engine.connect() as connection:
            self._get(connection, task_id)
            rows = connection.execute(
                select(events)
                .where(events.c.task_id == task_id, events.c.id > after_id)
                .order_by(events.c.id)
            ).mappings()
            return [
                Event(
                    id=row["id"],
                    task_id=row["task_id"],
                    event=row["event"],
                    timestamp=row["timestamp"],
                    data=json.loads(row["data"]),
                )
                for row in rows
            ]

    def record_event(
        self, task_id: str, kind: EventType, data: dict, expected_version: int
    ) -> Task:
        """Append runtime model telemetry without bypassing lifecycle methods."""
        if kind not in (
            EventType.MODEL_REQUESTED,
            EventType.MODEL_RESPONDED,
            EventType.RECOVERY_STARTED,
            EventType.RECOVERY_STOPPED,
        ):
            raise ValueError("Lifecycle events must use their dedicated repository operation")
        with self.database.engine.begin() as connection:
            task = self._get(connection, task_id)
            expected_status = (
                TaskStatus.BLOCKED
                if kind in (EventType.RECOVERY_STARTED, EventType.RECOVERY_STOPPED)
                else (
                    TaskStatus.VERIFYING if data.get("role") == "verifier" else TaskStatus.PLANNING
                )
            )
            if task.status != expected_status:
                raise Conflict("Task state changed before telemetry could be recorded")
            updated = self._save(connection, task, {}, expected_version)
            self._event(connection, task_id, kind, data)
            return updated
