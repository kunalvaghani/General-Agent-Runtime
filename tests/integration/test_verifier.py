import asyncio
import json

from test_executor import prepared

from gar.core.executor import Executor
from gar.core.state import TaskStatus
from gar.core.verifier import Verifier
from gar.models.base import Generation


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
