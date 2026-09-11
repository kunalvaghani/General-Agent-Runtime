"""Persisted event envelope; streaming delivery will be added in later stages."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, JsonValue

from gar.core.state import Snapshot, now


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_BLOCKED = "task.blocked"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_COMPLETED = "task.completed"
    PLAN_CREATED = "plan.created"
    PLAN_REVISED = "plan.revised"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    MODEL_REQUESTED = "model.requested"
    MODEL_RESPONDED = "model.responded"
    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_RECEIVED = "approval.received"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    MEMORY_SAVED = "memory.saved"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_STOPPED = "recovery.stopped"


class Event(Snapshot):
    id: int = Field(ge=1)
    task_id: str
    event: EventType
    timestamp: datetime = Field(default_factory=now)
    data: dict[str, JsonValue] = Field(default_factory=dict)
