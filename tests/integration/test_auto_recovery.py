import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from test_executor import prepared

from gar.core.orchestrator import Orchestrator
from gar.core.state import Step, StepStatus, TaskStatus
from gar.models.base import Generation


def decision(tool, arguments, action="tool"):
    return Generation(
        model="test",
        content=json.dumps(
            {
                "action": action,
                "reason": "Test decision",
                "tool_name": tool,
                "arguments": arguments,
            }
        ),
    )


def test_repair_context_retains_failure_when_history_exceeds_prompt_limit(tmp_path):
    db, repo, task, _, _ = prepared(tmp_path)
    try:
        task = task.model_copy(
            update={
                "metadata": {
                    "execution": {
                        "last_failure": {
                            "error": "command_failed",
                            "output": "Assertion failed\n" * 10000,
                        },
                        "observations": [
                            {
                                "tool": "filesystem.write",
                                "status": "ok",
                                "arguments": {"path": "app.py", "content": "x" * 50000},
                                "output": "File written.",
                            }
                        ],
                    }
                }
            }
        )
        encoded = Orchestrator.repair_context(task, repo.get_plan(task.id))
        context = json.loads(encoded)
        assert len(encoded) <= 20000
        assert context["failure"]["error"] == "command_failed"
        assert "Assertion failed" in context["failure"]["output"]
        assert context["written_files"] == ["app.py"]
        assert context["previous_steps"]
        assert "x" * 50000 not in encoded
    finally:
        db.close()


def test_repair_context_does_not_revive_an_old_rejected_write(tmp_path):
    db, repo, task, _, _ = prepared(tmp_path)
    try:
        task = task.model_copy(
            update={
                "metadata": {
                    "execution": {
                        "observations": [
                            {
                                "tool": "filesystem.write",
                                "status": "error",
                                "error": "invalid_arguments",
                                "output": "Old syntax error",
                            },
                            {
                                "tool": "filesystem.write",
                                "status": "ok",
                                "arguments": {"path": "app.py"},
                                "output": "File written.",
                            },
                        ]
                    }
                }
            }
        )
        context = json.loads(Orchestrator.repair_context(task, repo.get_plan(task.id)))
        assert context["failure"] == {"error": "", "output": ""}
        assert context["written_files"] == ["app.py"]
    finally:
        db.close()


def test_replan_resolves_dependencies_on_completed_previous_steps(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    try:
        task = repo.get(task.id)
        task = repo.transition(task.id, TaskStatus.RUNNING, task.version)
        task = repo.transition_step(task.id, "one", StepStatus.RUNNING, task.version)
        task = repo.transition_step(task.id, "one", StepStatus.COMPLETED, task.version)
        task = repo.transition(task.id, TaskStatus.VERIFYING, task.version)
        repo.finish_verification(
            task.id, {"passed": False, "evidence": [], "issues": ["Tests needed"]}, task.version
        )
        adapter.generate.return_value = Generation(
            model="test",
            content=json.dumps(
                {
                    "objective": "Verify existing work",
                    "completion_criteria": ["Tests pass"],
                    "steps": [
                        {
                            "id": "verify",
                            "description": "Test existing implementation",
                            "dependencies": ["one"],
                            "expected_output": "Tests pass",
                            "tool_hint": "terminal.run",
                        }
                    ],
                }
            ),
        )
        result = asyncio.run(Orchestrator(repo, adapter, tools).replan(task.id))
        plan = repo.get_plan(task.id)
        assert result.status == TaskStatus.PLANNING
        assert plan.revision == 2
        assert plan.steps[0].dependencies == ()
        assert plan.steps[0].status == StepStatus.PENDING
    finally:
        db.close()


def test_repair_context_keeps_a_test_failure_after_read_only_inspection(tmp_path):
    db, repo, task, _, _ = prepared(tmp_path)
    try:
        task = task.model_copy(
            update={
                "metadata": {
                    "execution": {
                        "observations": [
                            {
                                "tool": "terminal.run",
                                "status": "error",
                                "error": "command_failed",
                                "output": "A real test failed",
                            },
                            {"tool": "filesystem.read", "status": "ok", "output": "Current source"},
                        ]
                    }
                }
            }
        )
        context = json.loads(Orchestrator.repair_context(task, repo.get_plan(task.id)))
        assert context["failure"]["output"] == "A real test failed"
    finally:
        db.close()


def test_later_steps_get_retries_without_resetting_task_counters(tmp_path):
    steps = (
        Step(id="first", description="Write first", expected_output="First file"),
        Step(
            id="second",
            description="Write second",
            expected_output="Second file",
            dependencies=("first",),
        ),
        Step(
            id="verify",
            description="Test files",
            expected_output="Tests pass",
            dependencies=("second",),
        ),
    )
    db, repo, task, adapter, tools = prepared(tmp_path, steps)
    bad = decision("terminal.run", {"argv": ["unsupported"]})
    responses = [
        bad,
        decision("filesystem.write", {"path": "a.txt", "content": "a"}),
        bad,
        decision("filesystem.write", {"path": "b.txt", "content": "b"}),
        bad,
        decision("terminal.run", {"argv": ["python", "-m", "pytest", "-q"]}),
    ]

    async def generate(model, messages, **kwargs):
        if responses:
            return responses.pop(0)
        context = json.loads(messages[-1].content)
        return Generation(
            model="test",
            content=json.dumps(
                {
                    "checks": {
                        key: {
                            "passed": True,
                            "reason": "Fixture evidence reviewed",
                            "evidence_ids": [context["tests"][0]["call_id"]],
                        }
                        for key in context["criteria"]
                    }
                }
            ),
        )

    adapter.generate.side_effect = generate
    tools.sandbox = AsyncMock()
    tools.sandbox.run.return_value = (0, "2 passed", False)
    runtime = Orchestrator(repo, adapter, tools)
    try:
        result = asyncio.run(runtime.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        result = asyncio.run(runtime.run(task.id, result.metadata["execution"]["pending"]["id"]))
        assert result.status == TaskStatus.COMPLETED
        assert result.metadata["execution"]["retries"] == 3
        assert result.metadata["execution"]["decisions"] == 6
        assert all(step.attempts == 2 for step in repo.get_plan(task.id).steps)
        assert result.metadata.get("replans", 0) == 0
    finally:
        db.close()


def test_model_timeout_retries_without_replaying_a_tool(tmp_path):
    from gar.models.base import ModelTimeout

    steps = (
        Step(id="write", description="Write", expected_output="File"),
        Step(id="test", description="Test", expected_output="Pass", dependencies=("write",)),
    )
    db, repo, task, adapter, tools = prepared(tmp_path, steps)
    adapter.generate.side_effect = [
        ModelTimeout("request timed out"),
        decision("filesystem.write", {"path": "a.txt", "content": "once"}),
        decision("terminal.run", {"argv": ["python", "-m", "pytest", "-q"]}),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        state = result.metadata["execution"]
        assert state["retries"] == 1 and state["decisions"] == 3
        assert len(state["observations"]) == 1
        assert (tools.workspace.root / "a.txt").read_text() == "once"
        retry_prompt = json.loads(adapter.generate.call_args_list[1].args[1][-1].content)
        assert retry_prompt["previous_failure"]["error"] == "timeout"
        assert retry_prompt["replanning_available"] is True
        assert "No tool ran" in retry_prompt["previous_failure"]["output"]
    finally:
        db.close()


@pytest.mark.parametrize("action", ["tool", "request_approval"])
def test_denied_command_gets_alternative_without_false_approval(tmp_path, action):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.side_effect = [
        decision("terminal.run", {"argv": ["python", "calculator.py"]}, action),
        decision("filesystem.write", {"path": "calculator.py", "content": "# artifact"}),
        Generation(model="test", content="invalid verification repair plan"),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert (tools.workspace.root / "calculator.py").exists()
        assert result.metadata["execution"]["retries"] == 1
        events = repo.get_events(task.id)
        assert not any(e.event.value == "approval.required" for e in events)
        assert any(e.event.value == "recovery.started" for e in events)
        prompt = json.loads(adapter.generate.call_args_list[1].args[1][-1].content)
        assert prompt["observations"][-1]["error"] == "command_denied"
        # Artifact creation does not imply the goal was verified.
        assert result.status == TaskStatus.BLOCKED
    finally:
        db.close()


def test_alternative_dangerous_action_still_requires_its_own_approval(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.side_effect = [
        decision("terminal.run", {"argv": ["unsupported"]}),
        decision("terminal.run", {"argv": ["python", "-m", "pytest"]}),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert result.metadata["execution"]["pending"]["decision"]["arguments"]["argv"] == [
            "python",
            "-m",
            "pytest",
        ]
    finally:
        db.close()


def test_invalid_model_decision_retries_without_inventing_tool_evidence(tmp_path):
    from gar.models.base import InvalidModelResponse

    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.side_effect = [
        InvalidModelResponse("Invalid structured output"),
        decision("terminal.run", {"argv": ["python", "-m", "pytest"]}),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert result.metadata["execution"]["decisions"] == 2
        assert result.metadata["execution"]["observations"] == []
        assert any("No tool ran" in e.data.get("message", "") for e in repo.get_events(task.id))
    finally:
        db.close()


def test_path_policy_denial_does_not_trigger_automatic_workaround(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    adapter.generate.return_value = decision("filesystem.read", {"path": "../secret"})
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert adapter.generate.await_count == 1
    finally:
        db.close()


def test_executor_replan_request_is_honored_without_tool_failure(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    proposal = Generation(
        model="test",
        content=json.dumps(
            {
                "objective": "Test in Docker",
                "completion_criteria": ["Tests pass"],
                "steps": [
                    {
                        "id": "test",
                        "description": "Run tests",
                        "dependencies": [],
                        "expected_output": "Tests pass",
                    }
                ],
            }
        ),
    )
    adapter.generate.side_effect = [
        Generation(
            model="test", content=json.dumps({"action": "replan", "reason": "Need headless tests"})
        ),
        proposal,
        decision("terminal.run", {"argv": ["python", "-m", "pytest"]}),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert result.metadata["replans"] == 1
        assert result.metadata["execution"]["decisions"] == 2
        assert "replan_requested" not in result.metadata["execution"]
        assert repo.get_plan(task.id).revision == 2
    finally:
        db.close()


def test_retry_then_replan_keeps_decision_budget_and_stops_on_invalid_plan(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    bad = decision("terminal.run", {"argv": ["unsupported"]})
    adapter.generate.side_effect = [bad, bad, bad, Generation(model="test", content="invalid")]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert result.status == TaskStatus.BLOCKED
        assert result.metadata["execution"]["retries"] == 2
        assert result.metadata["execution"]["decisions"] == 3
        assert result.metadata["replans"] == 1
        assert adapter.generate.await_count == 4
    finally:
        db.close()


def test_successful_replan_uses_failure_context_without_resetting_budget(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    bad = decision("terminal.run", {"argv": ["unsupported"]})
    proposal = Generation(
        model="test",
        content=json.dumps(
            {
                "objective": "Create an artifact instead",
                "completion_criteria": ["File exists"],
                "steps": [
                    {
                        "id": "alternative",
                        "description": "Write a file",
                        "dependencies": [],
                        "expected_output": "File exists",
                    }
                ],
            }
        ),
    )
    adapter.generate.side_effect = [
        bad,
        bad,
        bad,
        proposal,
        decision("filesystem.write", {"path": "artifact.py", "content": "# local artifact"}),
        Generation(model="test", content="invalid verification repair plan"),
    ]
    try:
        result = asyncio.run(Orchestrator(repo, adapter, tools).run(task.id))
        assert (tools.workspace.root / "artifact.py").exists()
        assert repo.get_plan(task.id).revision == 2
        assert result.metadata["execution"]["decisions"] == 4
        assert result.metadata["replans"] == 2
        prompt = json.loads(adapter.generate.call_args_list[3].args[1][-1].content)
        assert "command_denied" in prompt["reference_context"]
        context = json.loads(prompt["reference_context"])
        assert context["mode"] == "repair_existing_work"
        assert context["previous_steps"][0]["status"] == "FAILED"
        assert context["failure"]["error"] == "command_denied"
    finally:
        db.close()


def test_approved_command_failure_recovers_without_manual_resume(tmp_path):
    db, repo, task, adapter, tools = prepared(tmp_path)
    tools.sandbox = AsyncMock()
    tools.sandbox.run.return_value = (1, "A failing test", False)
    adapter.generate.side_effect = [
        decision("terminal.run", {"argv": ["python", "-m", "pytest"]}),
        decision("filesystem.write", {"path": "fixed.py", "content": "# corrected artifact"}),
        Generation(model="test", content="invalid verification repair plan"),
    ]
    runtime = Orchestrator(repo, adapter, tools)
    try:
        result = asyncio.run(runtime.run(task.id))
        assert result.status == TaskStatus.WAITING_APPROVAL
        request = result.metadata["execution"]["pending"]["id"]
        result = asyncio.run(runtime.run(task.id, request))
        assert (tools.workspace.root / "fixed.py").exists()
        assert result.metadata["execution"]["retries"] == 1
        tools.sandbox.run.assert_awaited_once()
    finally:
        db.close()
