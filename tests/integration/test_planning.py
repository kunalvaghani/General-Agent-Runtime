import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from typer.testing import CliRunner

from gar.cli.app import app
from gar.core.planner import Planner, PlanningError, PlanningService
from gar.core.state import Task, TaskStatus
from gar.models.base import Generation, ModelAdapter, ModelTimeout
from gar.models.ollama import OllamaAdapter
from gar.models.registry import ModelRegistry
from gar.persistence.database import Database
from gar.persistence.repositories import Conflict, TaskRepository

PAYLOAD = {
    "objective": "Write a module",
    "completion_criteria": ["Module exists"],
    "steps": [
        {
            "id": "write",
            "description": "Create a module",
            "dependencies": [],
            "expected_output": "Module exists on disk",
        }
    ],
}


@pytest.fixture
def state(tmp_path):
    database = Database(tmp_path / "gar.db")
    database.initialize()
    repo = TaskRepository(database)
    task = repo.create(Task(goal="Write a module", model_id="test", workspace="workspace"))
    adapter = AsyncMock(spec=ModelAdapter)
    adapter.generate.return_value = Generation(model="test", content=json.dumps(PAYLOAD))
    yield repo, task, adapter
    database.close()


def test_plan_persisted_with_events_and_no_execution(state):
    repo, task, adapter = state
    service = PlanningService(repo, Planner(adapter))
    plan = asyncio.run(service.plan_task(task.id))
    assert repo.get_plan(task.id) == plan
    assert repo.get(task.id).status == TaskStatus.PLANNING
    assert repo.get(task.id).current_step is None
    assert [e.event.value for e in repo.get_events(task.id)] == [
        "task.created",
        "task.status_changed",
        "model.requested",
        "model.responded",
        "plan.created",
    ]
    with pytest.raises(PlanningError):
        asyncio.run(service.plan_task(task.id))
    assert adapter.generate.await_count == 1
    reopened = Database(repo.database.path)
    try:
        assert TaskRepository(reopened).get_plan(task.id).completion_criteria == ("Module exists",)
    finally:
        reopened.close()


@pytest.mark.parametrize("failure", [PlanningError("invalid"), ModelTimeout("timeout")])
def test_failure_blocks_without_plan_and_allows_explicit_retry(state, failure):
    repo, task, adapter = state
    adapter.generate.side_effect = failure
    service = PlanningService(repo, Planner(adapter))
    with pytest.raises(type(failure)):
        asyncio.run(service.plan_task(task.id))
    assert repo.get(task.id).status == TaskStatus.BLOCKED
    assert repo.get_plan(task.id) is None
    adapter.generate.side_effect = None
    asyncio.run(service.plan_task(task.id))
    assert repo.get_plan(task.id) is not None


@pytest.mark.parametrize("fail", [True, False])
def test_cancellation_during_model_request_is_not_overwritten(state, fail):
    repo, task, adapter = state

    async def respond(*args, **kwargs):
        current = repo.get(task.id)
        repo.transition(task.id, TaskStatus.CANCELLED, current.version)
        if fail:
            raise ModelTimeout("timeout")
        return Generation(model="test", content=json.dumps(PAYLOAD))

    adapter.generate.side_effect = respond
    with pytest.raises((ModelTimeout, Conflict)):
        asyncio.run(PlanningService(repo, Planner(adapter)).plan_task(task.id))
    assert repo.get(task.id).status == TaskStatus.CANCELLED
    assert repo.get_plan(task.id) is None


def test_async_cancellation_blocks_task(state):
    repo, task, adapter = state
    adapter.generate.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(PlanningService(repo, Planner(adapter)).plan_task(task.id))
    assert repo.get(task.id).status == TaskStatus.BLOCKED


def test_cli_ollama_adapter_to_sqlite(monkeypatch, tmp_path):
    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test"}]})
        body = json.loads(request.content)
        assert "completion_criteria" in body["format"]["required"]
        return httpx.Response(
            200,
            json={
                "model": "test",
                "done": True,
                "message": {"role": "assistant", "content": json.dumps(PAYLOAD)},
            },
        )

    def registry(settings):
        result = ModelRegistry()
        result.register(OllamaAdapter(transport=httpx.MockTransport(respond)))
        return result

    monkeypatch.setattr("gar.cli.planning.make_registry", registry)
    monkeypatch.setenv("GAR_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    created = runner.invoke(app, ["task-create", "Write module", "test"])
    task_id = json.loads(created.output)["id"]
    result = runner.invoke(app, ["plan", task_id])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["task_id"] == task_id
    detail = json.loads(runner.invoke(app, ["task", task_id]).output)
    assert detail["plan"]["completion_criteria"] == ["Module exists"]
