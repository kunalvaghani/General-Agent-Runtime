import pytest
from pydantic import ValidationError

from gar.core.state import (
    TERMINAL,
    InvalidTransition,
    Plan,
    Step,
    Task,
    TaskStatus,
    validate_transition,
)


@pytest.mark.parametrize(
    "flow",
    [
        ["PENDING", "PLANNING", "RUNNING", "VERIFYING", "COMPLETED"],
        ["PENDING", "PLANNING", "RUNNING", "WAITING_APPROVAL", "RUNNING"],
        ["PENDING", "PLANNING", "BLOCKED", "PLANNING", "RUNNING", "FAILED"],
        ["PENDING", "PLANNING", "RUNNING", "VERIFYING", "PLANNING", "CANCELLED"],
    ],
)
def test_supported_lifecycle_flows(flow):
    for current, target in zip(flow, flow[1:], strict=False):
        validate_transition(TaskStatus(current), TaskStatus(target))


@pytest.mark.parametrize(
    "current,target",
    [
        ("PENDING", "COMPLETED"),
        ("RUNNING", "COMPLETED"),
        ("PENDING", "RUNNING"),
        ("PLANNING", "VERIFYING"),
        ("RUNNING", "RUNNING"),
    ],
)
def test_forbidden_shortcuts(current, target):
    with pytest.raises(InvalidTransition):
        validate_transition(TaskStatus(current), TaskStatus(target))


@pytest.mark.parametrize("status", list(TERMINAL))
def test_terminal_states(status):
    assert Task(goal="test", model_id="test", workspace="workspace", status=status).is_terminal
    for target in TaskStatus:
        with pytest.raises(InvalidTransition):
            validate_transition(status, target)


@pytest.mark.parametrize(
    "steps",
    [
        [],
        [Step(id="a", description="a", expected_output="a", dependencies=("missing",))],
        [Step(id="a", description="a", expected_output="a", dependencies=("a",))],
        [
            Step(id="a", description="a", expected_output="a"),
            Step(id="a", description="a", expected_output="a"),
        ],
        [
            Step(id="a", description="a", expected_output="a", dependencies=("b",)),
            Step(id="b", description="b", expected_output="b", dependencies=("a",)),
        ],
    ],
)
def test_invalid_plans(steps):
    with pytest.raises(ValidationError):
        Plan(task_id="test", objective="test", steps=steps)


@pytest.mark.parametrize(
    "changes",
    [
        {"goal": " "},
        {"max_steps": 0},
        {"max_steps": True},
        {"status": "UNKNOWN"},
        {"unexpected": "value"},
    ],
)
def test_invalid_task(changes):
    with pytest.raises(ValidationError):
        Task(**{"goal": "test", "model_id": "test", "workspace": "workspace", **changes})
