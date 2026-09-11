import pytest
from jsonschema import ValidationError, validate

from gar.core.executor import Executor
from gar.tools.registry import ToolRegistry


def test_exhausted_replanning_is_not_offered_to_the_model():
    executor = Executor(None, None, ToolRegistry)
    decision = {"action": "replan", "reason": "Try another plan"}
    validate(decision, executor.decision_schema())
    with pytest.raises(ValidationError):
        validate(decision, executor.decision_schema(allow_replan=False))
    validate(
        {
            "action": "tool",
            "reason": "Inspect before repairing",
            "step_complete": False,
            "tool_name": "filesystem.read",
            "arguments": {"path": "app.py"},
        },
        executor.decision_schema(allow_replan=False),
    )


def test_tool_arguments_are_constrained_by_selected_tool():
    schema = Executor(None, None, ToolRegistry).decision_schema()
    valid = {
        "action": "tool",
        "reason": "Create source",
        "step_complete": True,
        "tool_name": "filesystem.write",
        "arguments": {"path": "calculator.py", "content": "print(4)"},
    }
    validate(valid, schema)
    for arguments in (
        {},
        {"path": "a"},
        {"content": "print(4)"},
        {"code": "pass"},
        {"path": "a", "content": "x", "approved": True},
    ):
        with pytest.raises(ValidationError):
            validate({**valid, "arguments": arguments}, schema)
    with pytest.raises(ValidationError):
        validate({**valid, "tool_name": "shell.exec"}, schema)
    terminal = {
        **valid,
        "tool_name": "terminal.run",
        "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
    }
    validate(terminal, schema)
    with pytest.raises(ValidationError):
        validate({**terminal, "arguments": {"argv": ["python", "app.py"]}}, schema)


def test_failed_test_requires_repair_and_test_steps_require_test_evidence():
    executor = Executor(None, None, ToolRegistry)
    terminal = {
        "action": "tool",
        "reason": "Rerun tests",
        "tool_name": "terminal.run",
        "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
        "step_complete": True,
    }
    with pytest.raises(ValidationError):
        validate(terminal, executor.decision_schema(unavailable_tools=("terminal.run",)))
    write = {
        **terminal,
        "tool_name": "filesystem.write",
        "arguments": {"path": "app.py", "content": "print(1)"},
    }
    with pytest.raises(ValidationError):
        validate(write, executor.decision_schema(require_tests=True))
    validate({**write, "step_complete": False}, executor.decision_schema(require_tests=True))
    validate(terminal, executor.decision_schema(require_tests=True))
    state = {
        "observations": [{"tool": "terminal.run", "status": "error", "error": "command_failed"}]
    }
    assert executor.test_retry_needs_changes(state)
    state["observations"].append({"tool": "filesystem.read", "status": "ok"})
    assert executor.test_retry_needs_changes(state)
    state["observations"].append({"tool": "filesystem.write", "status": "ok"})
    assert not executor.test_retry_needs_changes(state)


def test_failed_python_execution_requires_a_successful_file_repair():
    executor = Executor(None, None, ToolRegistry)
    state = {"observations": [
        {"tool": "python.run", "status": "error", "error": "command_failed"}
    ]}
    for observation in (
        {"tool": "filesystem.read", "status": "ok"},
        {"tool": "filesystem.write", "status": "error"},
    ):
        state["observations"].append(observation)
        assert executor.test_retry_needs_changes(state, "python.run")
    decision = {
        "action": "request_approval", "reason": "Rerun unchanged tests",
        "tool_name": "python.run", "arguments": {"code": "raise TypeError()"},
        "step_complete": False,
    }
    with pytest.raises(ValidationError):
        validate(decision, executor.decision_schema(unavailable_tools=("python.run",)))
    state["observations"].append({"tool": "filesystem.write", "status": "ok"})
    assert not executor.test_retry_needs_changes(state, "python.run")
    validate(decision, executor.decision_schema())


def test_write_step_cannot_finish_with_a_read_or_unused_output():
    schema = Executor(None, None, ToolRegistry).decision_schema(require_write=True)
    read = {
        "action": "tool",
        "reason": "Inspect",
        "tool_name": "filesystem.read",
        "arguments": {"path": "app.py"},
        "step_complete": False,
    }
    validate(read, schema)
    with pytest.raises(ValidationError):
        validate({**read, "step_complete": True}, schema)
    with pytest.raises(ValidationError):
        validate({**read, "output": "Invented implementation"}, schema)
