"""Validated domain snapshots and deterministic lifecycle rules."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


def now() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.PLANNING, TaskStatus.CANCELLED},
    TaskStatus.PLANNING: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.BLOCKED,
        TaskStatus.VERIFYING,
        TaskStatus.PLANNING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_APPROVAL: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,
        TaskStatus.RUNNING,
        TaskStatus.PLANNING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
}


class InvalidTransition(ValueError):
    pass


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"Cannot transition from {current} to {target}")


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def trim_labels_only(cls, value, info):
        # JSON payloads contain exact code, tool arguments and evidence. Never trim them.
        if info.field_name in ("metadata", "data"):
            return value
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list | tuple) and all(isinstance(v, str) for v in value):
            return type(value)(v.strip() for v in value)
        return value


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Step(Snapshot):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: StepStatus = StepStatus.PENDING
    dependencies: tuple[str, ...] = ()
    expected_output: str = Field(min_length=1)
    tool_hint: str | None = None
    attempts: int = Field(default=0, ge=0, strict=True)


class Plan(Snapshot):
    task_id: str
    objective: str = Field(min_length=1)
    steps: tuple[Step, ...] = Field(min_length=1, max_length=1000)
    revision: int = Field(default=1, ge=1, strict=True)
    # Default preserves Stage 2 snapshots; the planner requires criteria for new plans.
    completion_criteria: tuple[str, ...] = ()

    @property
    def can_retry_failed_steps(self) -> bool:
        """At most three execution attempts per step; task budgets also apply."""
        failed = [step for step in self.steps if step.status == StepStatus.FAILED]
        return bool(failed) and all(step.attempts < 3 for step in failed)

    @model_validator(mode="after")
    def valid_dependencies(self) -> Self:
        ids = {step.id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Step IDs must be unique")
        resolved: set[str] = set()
        pending = {step.id: set(step.dependencies) for step in self.steps}
        for step in self.steps:
            if len(step.dependencies) != len(set(step.dependencies)):
                raise ValueError("Duplicate dependency")
            if not set(step.dependencies) <= ids:
                raise ValueError("Unknown dependency")
        while pending:
            ready = {key for key, deps in pending.items() if deps <= resolved}
            if not ready:
                raise ValueError("Dependency cycle")
            resolved.update(ready)
            pending = {key: deps for key, deps in pending.items() if key not in ready}
        return self


class Task(Snapshot):
    id: str = Field(default_factory=lambda: uuid4().hex)
    goal: str = Field(min_length=1, max_length=20000)
    status: TaskStatus = TaskStatus.PENDING
    model_id: str = Field(min_length=1)
    workspace: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    current_step: str | None = None
    max_steps: int = Field(default=50, ge=1, le=1000, strict=True)
    version: int = Field(default=0, ge=0, strict=True)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL
