import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from test_executor import prepared

from gar.core.executor import Executor
from gar.core.state import TaskStatus
from gar.core.verifier import Verifier
from gar.models.base import Generation


@pytest.mark.parametrize(
    "outcome", ["pass", "placeholder", "invented", "missing", "timeout", "large"]
)
def test_goal_review_is_required_after_passing_tests(tmp_path, outcome):
    from gar.core.state import Step
    from gar.models.base import ModelTimeout

    steps = (
        Step(id="write", description="Write GUI", expected_output="Working controls"),
        Step(id="test", description="Run tests", expected_output="Pass", dependencies=("write",)),
    )
    db, repo, task, adapter, tools = prepared(tmp_path, steps)
    source = "def create_widgets():\n    pass\n"
    if outcome == "large":
        source += "#" + "x" * 41000
    adapter.generate.side_effect = [
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "write",
                    "tool_name": "filesystem.write",
                    "arguments": {"path": "app.py", "content": source},
                }
            ),
        ),
        Generation(
            model="test",
            content=json.dumps(
                {
                    "action": "tool",
                    "reason": "test",
                    "tool_name": "terminal.run",
                    "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
                }
            ),
        ),
    ]
    tools.sandbox = AsyncMock()
    tools.sandbox.run.return_value = (0, "1 passed", False)
    try:
        executor = Executor(repo, adapter, tools)
        pending = asyncio.run(executor.run(task.id))
        result = asyncio.run(executor.run(task.id, pending.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.VERIFYING
        seen = []

        async def review(model, messages, **kwargs):
            if outcome == "timeout":
                raise ModelTimeout("timeout")
            context = json.loads(messages[-1].content)
            seen.append(context)
            assert context["artifacts"][0]["content"] == source
            assert "do not" in messages[0].content.lower()
            checks = {
                key: {
                    "passed": outcome != "placeholder",
                    "reason": "GUI has no implemented controls"
                    if outcome == "placeholder"
                    else "Reviewed",
                    "evidence_ids": [
                        "invented"
                        if outcome == "invented"
                        else context["artifacts"][0]["evidence_id"]
                    ],
                }
                for key in context["criteria"]
            }
            if outcome == "missing":
                checks = {}
            return Generation(model="test", content=json.dumps({"checks": checks}))

        adapter.generate.side_effect = review
        result = asyncio.run(Verifier().verify(repo, task.id, tools, adapter))
        assert result.passed == (outcome == "pass")
        assert repo.get(task.id).status == (
            TaskStatus.COMPLETED if outcome == "pass" else TaskStatus.BLOCKED
        )
        if outcome == "placeholder":
            assert "GUI has no implemented controls" in result.issues[0]
            assert result.goal_review["checks"]["goal"]["passed"] is False
        if outcome == "large":
            assert not seen
            assert "review limit" in result.issues[0]
    finally:
        db.close()


def test_verification_uses_latest_canonical_write_and_current_plan_evidence(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock

    db, _, _, _, tools = prepared(tmp_path)
    try:
        (tools.workspace.root / "app.py").write_text("new")
        observations = [
            {
                "step_id": "write",
                "plan_revision": 1,
                "tool": "filesystem.write",
                "status": "ok",
                "call_id": "old",
                "arguments": {"path": "/workspace/app.py", "content": "old"},
            },
            {
                "step_id": "write",
                "plan_revision": 2,
                "tool": "filesystem.write",
                "status": "ok",
                "call_id": "new",
                "arguments": {"path": "app.py", "content": "new"},
            },
            {
                "step_id": "test",
                "plan_revision": 2,
                "tool": "terminal.run",
                "status": "ok",
                "call_id": "tests",
                "exit_code": 0,
            },
        ]
        task = SimpleNamespace(
            status=TaskStatus.VERIFYING,
            version=1,
            metadata={"execution": {"observations": observations}},
        )
        plan = SimpleNamespace(
            revision=2, steps=[SimpleNamespace(id="write"), SimpleNamespace(id="test")]
        )
        repo = Mock(get=Mock(return_value=task), get_plan=Mock(return_value=plan))
        result = asyncio.run(Verifier().verify(repo, "task", tools))
        assert result.issues == ["A separate goal review is required before completion"]
        plan.revision = 3
        result = asyncio.run(Verifier().verify(repo, "task", tools))
        assert not result.passed
        assert "No successful tool evidence for write" in result.issues
    finally:
        db.close()


def test_model_text_cannot_complete_task(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(
        model="test",
        content=json.dumps({"action": "respond", "reason": "done", "output": "All tests pass"}),
    )
    try:
        asyncio.run(Executor(repo, adapter, tools).run(task.id))
        result = asyncio.run(Verifier().verify(repo, task.id, tools))
        assert not result.passed
        assert repo.get(task.id).status == TaskStatus.BLOCKED
    finally:
        db.close()


def test_tool_write_read_roundtrip_preserves_line_endings(tmp_path):
    db, _, _, _, tools = prepared(tmp_path)
    try:
        content = "def sample():\n    return 1\n\n"
        result = asyncio.run(
            tools.execute("filesystem.write", {"path": "code.py", "content": content})
        )
        assert result.status == "ok"
        read = asyncio.run(tools.execute("filesystem.read", {"path": "code.py"}))
        assert read.output == content
        assert (tools.workspace.root / "code.py").read_bytes() == content.encode()
    finally:
        db.close()


def test_failed_step_retry_is_bounded(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = Generation(model="test", content="bad")
    try:
        executor = Executor(repo, adapter, tools)
        for _ in range(2):
            asyncio.run(executor.run(task.id))
            repo.prepare_retry(task.id)
        asyncio.run(executor.run(task.id))
        import pytest

        with pytest.raises(ValueError):
            repo.prepare_retry(task.id)
    finally:
        db.close()
