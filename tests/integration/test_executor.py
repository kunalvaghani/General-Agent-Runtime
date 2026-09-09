import asyncio
import json
from unittest.mock import AsyncMock

from gar.core.executor import Executor
from gar.core.state import Plan, Step, Task, TaskStatus
from gar.models.base import Generation
from gar.persistence.database import Database
from gar.persistence.repositories import TaskRepository
from gar.safety.audit import Audit
from gar.tools.registry import ToolRegistry


def prepared(tmp_path):
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
            steps=(Step(id="one", description="Write", expected_output="File exists"),),
        ),
        task.version,
    )
    adapter = AsyncMock()
    tools = ToolRegistry(root, Audit(tmp_path / "audit.db"))
    return db, repo, task, adapter, tools


def test_executor_writes_and_never_claims_completion(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps(
            {
                "action": "tool",
                "reason": "write",
                "tool_name": "filesystem.write",
                "arguments": {"path": "a", "content": "hello"},
            }
        ),
    )
    try:
        result = asyncio.run(Executor(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.VERIFYING
        assert (tools.workspace.root / "a").read_text() == "hello"
    finally:
        db.close()


def test_executor_invalid_decision_blocks(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(model="test", content='{"action":"shell"}')
    try:
        assert asyncio.run(Executor(repo, adapter, tools).run(task.id)).status == TaskStatus.BLOCKED
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
