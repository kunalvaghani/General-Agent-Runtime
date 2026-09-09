import pytest
from sqlalchemy import insert

from gar.core.events import EventType
from gar.core.state import Plan, Step, StepStatus, Task, TaskStatus
from gar.persistence.database import Database
from gar.persistence.models import events
from gar.persistence.repositories import Conflict, TaskNotFound, TaskRepository


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "state" / "gar.db")
    database.initialize()
    yield database
    database.close()


def pending(database):
    repo = TaskRepository(database)
    task = repo.create(Task(goal="test", model_id="test", workspace="workspace"))
    return repo, task


def running(database):
    repo, task = pending(database)
    task = repo.transition(task.id, TaskStatus.PLANNING, task.version)
    task = repo.save_plan(
        Plan(
            task_id=task.id,
            objective="test",
            steps=(
                Step(id="a", description="a", expected_output="a"),
                Step(id="b", description="b", expected_output="b", dependencies=("a",)),
            ),
        ),
        task.version,
    )
    return repo, repo.transition(task.id, TaskStatus.RUNNING, task.version)


def test_restart_preserves_task_plan_steps_and_events(database):
    repo, task = running(database)
    task = repo.transition_step(task.id, "a", StepStatus.RUNNING, task.version)
    task = repo.transition_step(task.id, "a", StepStatus.COMPLETED, task.version)
    expected_events = repo.get_events(task.id)
    database.close()
    reopened = Database(database.path)
    try:
        reopened.initialize()
        loaded = TaskRepository(reopened)
        assert loaded.get(task.id) == task
        assert loaded.get_plan(task.id).steps[0].status == StepStatus.COMPLETED
        assert loaded.get_events(task.id) == expected_events
        assert [e.id for e in expected_events] == sorted(e.id for e in expected_events)
        assert loaded.get_events(task.id, expected_events[-2].id) == expected_events[-1:]
    finally:
        reopened.close()


def test_event_failure_rolls_back_state(database, monkeypatch):
    repo, task = pending(database)

    def fail(*args):
        raise RuntimeError("injected journal failure")

    monkeypatch.setattr(repo, "_event", fail)
    with pytest.raises(RuntimeError):
        repo.transition(task.id, TaskStatus.PLANNING, task.version)
    assert repo.get(task.id) == task
    assert len(repo.get_events(task.id)) == 1


def test_stale_writer_and_invalid_transition_add_no_events(database):
    repo, task = pending(database)
    updated = repo.transition(task.id, TaskStatus.PLANNING, task.version)
    with pytest.raises(Conflict):
        repo.transition(task.id, TaskStatus.CANCELLED, task.version)
    assert repo.get(task.id) == updated
    assert len(repo.get_events(task.id)) == 2
    with pytest.raises(ValueError):
        repo.transition(task.id, TaskStatus.COMPLETED, updated.version)
    assert len(repo.get_events(task.id)) == 2


def test_dependencies_and_single_active_step(database):
    repo, task = running(database)
    with pytest.raises(ValueError):
        repo.transition_step(task.id, "b", StepStatus.RUNNING, task.version)
    task = repo.transition_step(task.id, "a", StepStatus.RUNNING, task.version)
    with pytest.raises(ValueError):
        repo.transition_step(task.id, "b", StepStatus.RUNNING, task.version)
    task = repo.transition_step(task.id, "a", StepStatus.FAILED, task.version)
    task = repo.transition_step(task.id, "a", StepStatus.RUNNING, task.version)
    assert repo.get_plan(task.id).steps[0].attempts == 2
    task = repo.transition_step(task.id, "a", StepStatus.COMPLETED, task.version)
    repo.transition_step(task.id, "b", StepStatus.RUNNING, task.version)


def test_cancellation_and_unverified_completion(database):
    repo, task = running(database)
    with pytest.raises(ValueError, match="steps"):
        repo.transition(task.id, TaskStatus.VERIFYING, task.version)
    for step_id in ("a", "b"):
        task = repo.transition_step(task.id, step_id, StepStatus.RUNNING, task.version)
        task = repo.transition_step(task.id, step_id, StepStatus.COMPLETED, task.version)
    task = repo.transition(task.id, TaskStatus.VERIFYING, task.version)
    with pytest.raises(ValueError, match="verifier"):
        repo.transition(task.id, TaskStatus.COMPLETED, task.version)
    task = repo.transition(task.id, TaskStatus.CANCELLED, task.version)
    assert repo.get_events(task.id)[-1].event == EventType.TASK_CANCELLED
    with pytest.raises(ValueError):
        repo.transition(task.id, TaskStatus.PLANNING, task.version)


def test_missing_task_and_foreign_key(database):
    repo = TaskRepository(database)
    with pytest.raises(TaskNotFound):
        repo.get("missing")
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            insert(events).values(
                task_id="missing", event="task.created", timestamp="now", data="{}"
            )
        )


def test_schema_version_rejected(database):
    with database.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="schema"):
        database.initialize()


def test_plan_revision_and_limits(database):
    repo, task = running(database)
    first = repo.get_plan(task.id)
    task = repo.transition(task.id, TaskStatus.PLANNING, task.version)
    with pytest.raises(Conflict):
        repo.save_plan(first, task.version)
    revised = Plan(task_id=task.id, objective="revised", revision=2, steps=first.steps)
    repo.save_plan(revised, task.version)
    assert repo.get_plan(task.id).revision == 2


def test_plan_cannot_exceed_task_budget(database):
    repo = TaskRepository(database)
    task = repo.create(Task(goal="test", model_id="test", workspace="workspace", max_steps=1))
    task = repo.transition(task.id, TaskStatus.PLANNING, task.version)
    plan = Plan(
        task_id=task.id,
        objective="test",
        steps=(
            Step(id="a", description="a", expected_output="a"),
            Step(id="b", description="b", expected_output="b"),
        ),
    )
    with pytest.raises(ValueError, match="limit"):
        repo.save_plan(plan, task.version)
    assert repo.get_plan(task.id) is None
    assert repo.get(task.id).version == task.version
