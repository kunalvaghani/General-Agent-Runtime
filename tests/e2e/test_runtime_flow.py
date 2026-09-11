import asyncio
import json
from unittest.mock import AsyncMock

from gar.core.orchestrator import Orchestrator
from gar.core.state import Task, TaskStatus
from gar.models.base import Generation
from gar.persistence.database import Database
from gar.persistence.repositories import TaskRepository
from gar.safety.audit import Audit
from gar.tools.registry import ToolRegistry


def test_full_runtime_with_real_files_and_test_evidence(tmp_path, request):
    db = Database(tmp_path / "gar.db")
    db.initialize()
    repo = TaskRepository(db)
    root = tmp_path / "workspace"
    root.mkdir()
    task = repo.create(Task(goal="Write tested addition", model_id="test", workspace=str(root)))
    responses = [
        {
            "objective": task.goal,
            "completion_criteria": ["Tests pass"],
            "steps": [
                {
                    "id": "write",
                    "description": "Write test",
                    "dependencies": [],
                    "expected_output": "Test file",
                },
                {
                    "id": "test",
                    "description": "Run test",
                    "dependencies": ["write"],
                    "expected_output": "Tests pass",
                },
            ],
        },
        {
            "action": "tool",
            "reason": "write",
            "tool_name": "filesystem.write",
            "arguments": {"path": "test_add.py", "content": "def test_add(): assert 2+2 == 4"},
        },
        {
            "action": "tool",
            "reason": "test",
            "tool_name": "terminal.run",
            "arguments": {"argv": ["python", "-m", "pytest", "-q"]},
        },
    ]
    adapter = AsyncMock()

    async def generate(model, messages, **kwargs):
        if responses:
            value = responses.pop(0)
        else:
            context = json.loads(messages[-1].content)
            value = {
                "checks": {
                    key: {
                        "passed": True,
                        "reason": "Fixture evidence reviewed",
                        "evidence_ids": [context["tests"][0]["call_id"]],
                    }
                    for key in context["criteria"]
                }
            }
        return Generation(model="test", content=json.dumps(value))

    adapter.generate.side_effect = generate
    sandbox = AsyncMock()
    sandbox.run.return_value = (0, "1 passed", False)
    if request.config.getoption("--docker"):
        sandbox = None
    runtime = Orchestrator(repo, adapter, ToolRegistry(root, Audit(tmp_path / "audit.db"), sandbox))
    try:
        result = asyncio.run(runtime.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        request_id = result.metadata["execution"]["pending"]["id"]
        result = asyncio.run(runtime.run(task.id, request_id))
        assert result.status == TaskStatus.COMPLETED
        assert result.metadata["verification"]["evidence"]
    finally:
        db.close()
