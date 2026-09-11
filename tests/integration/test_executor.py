import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from gar.core.executor import Executor
from gar.core.state import Plan, Step, Task, TaskStatus
from gar.models.base import Generation
from gar.persistence.database import Database
from gar.persistence.repositories import TaskRepository
from gar.safety.audit import Audit
from gar.tools.registry import ToolRegistry


def prepared(tmp_path, steps=None):
    db = Database(tmp_path / "gar.db")
    db.initialize()
    repo = TaskRepository(db)
    root = tmp_path / "workspace"
    root.mkdir()
    task = repo.create(Task(goal="Write", model_id="test", workspace=str(root)))
    task = repo.transition(task.id, TaskStatus.PLANNING, task.version)
    repo.save_plan(
        Plan(
            task_id=task.id,
            objective="Write",
            steps=steps or (Step(id="one", description="Write", expected_output="File exists"),),
        ),
        task.version,
    )
    adapter = AsyncMock()
    tools = ToolRegistry(root, Audit(tmp_path / "audit.db"))
    return db, repo, task, adapter, tools


@pytest.mark.parametrize("path", ["a", "/workspace/a"])
def test_executor_writes_and_never_claims_completion(tmp_path, path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "write",
                "tool_name": "filesystem.write",
                "arguments": {"path": path, "content": "hello"},
            }
        ),
    )
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.VERIFYING
        assert (tools.workspace.root / "a").read_text() == "hello"
        prompt = json.loads(adapter.generate.call_args.args[1][-1].content)
        assert prompt["replanning_available"] is False
        variants = adapter.generate.call_args.kwargs["response_schema"]["anyOf"]
        assert not any(v["properties"]["action"].get("const") == "replan" for v in variants)
    finally:
        db.close()


def test_executor_invalid_decision_blocks(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(model="test", content='{"action":"shell"}')
    try:
        assert asyncio.run(Executor(repo, adapter, tools).run(task.id)).status == TaskStatus.BLOCKED
    finally:
        db.close()


@pytest.mark.parametrize("has_repository", [False, True])
def test_git_advertising_matches_workspace_capability(tmp_path, has_repository):
    db, repo, task, adapter, tools = prepared(tmp_path)
    if has_repository:
        (tools.workspace.root / ".git").mkdir()
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "respond",
                "reason": "Inspect capabilities",
                "output": "Unverified",
            }
        ),
    )
    try:
        asyncio.run(Executor(repo, adapter, tools).run(task.id))
        call = adapter.generate.call_args
        prompt = json.loads(call.args[1][-1].content)
        names = {spec["name"] for spec in prompt["tools"]}
        assert ("git.status" in names) == has_repository
        assert ("git.diff" in json.dumps(call.kwargs["response_schema"])) == has_repository
        assert prompt["tests_require_repair_before_rerun"] is False
    finally:
        db.close()


def test_unavailable_git_is_rejected_without_running_a_container(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    tools.sandbox = AsyncMock()
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "Inspect",
                "tool_name": "git.status",
                "arguments": {},
            }
        ),
    )
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert "no Git repository" in result.metadata["execution"]["last_failure"]["output"]
        tools.sandbox.run.assert_not_called()
    finally:
        db.close()


def test_read_cannot_complete_an_implementation_step(tmp_path):
    from gar.core.state import Step

    db, repo, task, adapter, tools = prepared(
        tmp_path,
        (
            Step(
                id="implement",
                description="Implement",
                expected_output="Working code",
                tool_hint="filesystem.write",
            ),
        ),
    )
    (tools.workspace.root / "app.py").write_text("pass\n")
    adapter.generate.side_effect = [
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Read",
                    "tool_name": "filesystem.read",
                    "arguments": {"path": "app.py"},
                    "step_complete": True,
                }
            ),
        ),
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Implement",
                    "tool_name": "filesystem.write",
                    "arguments": {"path": "app.py", "content": "print(4)\n"},
                    "step_complete": True,
                }
            ),
        ),
    ]
    try:
        executor = Executor(repo, adapter, tools)
        result = asyncio.run(executor.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert repo.get_plan(task.id).steps[0].status.value == "RUNNING"
        prompt = json.loads(adapter.generate.call_args.args[1][-1].content)
        assert prompt["step_evidence_ids"] == []
        result = asyncio.run(executor.run(task.id, result.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.VERIFYING
        assert (tools.workspace.root / "app.py").read_text() == "print(4)\n"
    finally:
        db.close()


def test_inspection_can_finish_using_real_evidence_without_another_tool_call(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    (tools.workspace.root / "a.txt").write_text("existing")

    async def generate(*args, **kwargs):
        prompt = json.loads(args[1][-1].content)
        evidence = prompt["step_evidence_ids"]
        value = (
            {
                "action": "complete_step",
                "reason": "Inspection finished",
                "output": "The existing file contains the expected text.",
                "evidence_ids": evidence,
            }
            if evidence
            else {
                "action": "tool",
                "reason": "Inspect existing file",
                "tool_name": "filesystem.read",
                "arguments": {"path": "a.txt"},
                "step_complete": False,
            }
        )
        return Generation(model="test", content=json.dumps(value))

    adapter.generate.side_effect = generate
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.VERIFYING  # Final verification is still required.
        state = result.metadata["execution"]
        assert len(state["observations"]) == 1
        assert state["step_reports"][0]["evidence_ids"] == [state["observations"][0]["call_id"]]
        assert adapter.generate.await_count == 2
    finally:
        db.close()


def test_completion_cannot_invent_evidence(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "complete_step",
                "reason": "Done",
                "output": "Claimed success",
                "evidence_ids": ["invented"],
            }
        ),
    )
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert not result.metadata["execution"]["observations"]
    finally:
        db.close()


def test_repair_write_cannot_finish_a_test_step_before_tests_pass(tmp_path):
    steps = (
        Step(
            id="verify",
            description="Run and fix tests",
            expected_output="Tests pass",
            tool_hint="terminal.run",
        ),
    )
    db, repo, task, adapter, tools = prepared(tmp_path, steps)
    adapter.generate.side_effect = [
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Repair",
                    "tool_name": "filesystem.write",
                    "arguments": {"path": "a.txt", "content": "fixed"},
                    "step_complete": True,
                }
            ),
        ),
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Verify",
                    "tool_name": "terminal.run",
                    "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
                    "step_complete": True,
                }
            ),
        ),
    ]
    tools.sandbox = AsyncMock()
    tools.sandbox.run.return_value = (0, "1 passed", False)
    try:
        executor = Executor(repo, adapter, tools)
        result = asyncio.run(executor.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert repo.get_plan(task.id).steps[0].status.value == "RUNNING"
        prompt = json.loads(adapter.generate.call_args.args[1][-1].content)
        assert prompt["step_evidence_ids"] == []
        result = asyncio.run(executor.run(task.id, result.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.VERIFYING
        assert len(result.metadata["execution"]["observations"]) == 2
    finally:
        db.close()


def test_identical_inspections_stop_with_actionable_recovery_feedback(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    (tools.workspace.root / "a.txt").write_text("unchanged")
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "Read again",
                "tool_name": "filesystem.read",
                "arguments": {"path": "a.txt"},
                "step_complete": False,
            }
        ),
    )
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert adapter.generate.await_count == 3
        assert result.metadata["execution"]["last_failure"]["error"] == "no_progress"
    finally:
        db.close()


def test_unchanged_failing_tests_are_rejected_before_requesting_another_approval(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "Run tests",
                "tool_name": "terminal.run",
                "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
                "step_complete": True,
            }
        ),
    )
    tools.sandbox = AsyncMock()
    tools.sandbox.run.return_value = (1, "A failing test", False)
    executor = Executor(repo, adapter, tools)
    try:
        result = asyncio.run(executor.run(task.id))
        result = asyncio.run(executor.run(task.id, result.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.BLOCKED
        repo.prepare_retry(task.id)
        result = asyncio.run(executor.run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert "repair" in result.metadata["execution"]["last_failure"]["output"]
        tools.sandbox.run.assert_awaited_once()
    finally:
        db.close()


def test_inspection_and_approved_edit_continue_the_same_step(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    (tools.workspace.root / "a.txt").write_text("old")
    adapter.generate.side_effect = [
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Inspect before editing",
                    "tool_name": "filesystem.read",
                    "arguments": {"path": "a.txt"},
                    "step_complete": False,
                }
            ),
        ),
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "Save complete result",
                    "tool_name": "filesystem.write",
                    "arguments": {"path": "a.txt", "content": "new"},
                    "step_complete": True,
                }
            ),
        ),
    ]
    try:
        executor = Executor(repo, adapter, tools)
        result = asyncio.run(executor.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert repo.get_plan(task.id).steps[0].attempts == 1
        assert (tools.workspace.root / "a.txt").read_text() == "old"
        result = asyncio.run(executor.run(task.id, result.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.VERIFYING
        assert len(result.metadata["execution"]["observations"]) == 2
        assert adapter.generate.await_count == 2
        assert (tools.workspace.root / "a.txt").read_text() == "new"
    finally:
        db.close()


def test_executor_prompt_uses_current_attempt_and_running_state(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(model="test", content="malformed")
    try:
        executor = Executor(repo, adapter, tools)
        asyncio.run(executor.run(task.id))
        prompt = json.loads(adapter.generate.call_args.args[1][-1].content)
        assert prompt["step"]["status"] == "RUNNING"
        assert prompt["step"]["attempts"] == 1
        repo.prepare_retry(task.id)
        asyncio.run(executor.run(task.id))
        prompt = json.loads(adapter.generate.call_args.args[1][-1].content)
        assert prompt["step"]["attempts"] == 2
        assert prompt["previous_failure"]["error"] == "invalid_arguments"
        assert "No tool ran" in prompt["previous_failure"]["output"]
    finally:
        db.close()


def test_budget_exhaustion_stops_before_model(tmp_path):
    from gar.core.events import EventType

    db, repo, task, adapter, tools = prepared(tmp_path)
    task = repo.get(task.id)
    repo.checkpoint(
        task.id,
        {"metadata": {"execution": {"decisions": 50, "observations": []}}},
        task.version,
        EventType.MODEL_RESPONDED,
        {},
    )
    try:
        assert asyncio.run(Executor(repo, adapter, tools).run(task.id)).status == TaskStatus.BLOCKED
        adapter.generate.assert_not_called()
    finally:
        db.close()


def test_exact_approval_is_not_blanket_permission(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    (tools.workspace.root / "a").write_text("old")
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "write",
                "tool_name": "filesystem.write",
                "arguments": {"path": "a", "content": "new"},
            }
        ),
    )
    try:
        executor = Executor(repo, adapter, tools)
        result = asyncio.run(executor.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert (tools.workspace.root / "a").read_text() == "old"
        import pytest

        with pytest.raises(ValueError):
            asyncio.run(executor.run(task.id, "wrong"))
        approval = result.metadata["execution"]["pending"]["id"]
        assert asyncio.run(executor.run(task.id, approval)).status == TaskStatus.VERIFYING
        assert adapter.generate.await_count == 1
    finally:
        db.close()
