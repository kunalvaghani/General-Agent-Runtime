"""Stage 2 task inspection; creation records a goal without executing it."""

from contextlib import contextmanager
from uuid import uuid4

import typer
from pydantic import ValidationError
from rich.console import Console
from sqlalchemy.exc import SQLAlchemyError

from gar.config import Settings
from gar.core.state import Task, TaskStatus
from gar.persistence.database import Database
from gar.persistence.repositories import TaskRepository


@contextmanager
def repository():
    database = None
    try:
        settings = Settings()
        saved = settings.data_dir / "settings.json"
        if saved.exists():
            import json

            settings = Settings.model_validate(
                {**settings.model_dump(), **json.loads(saved.read_text("utf-8"))}
            )
        database = Database(settings.data_dir / "gar.db")
        database.initialize()
        yield TaskRepository(database), settings
    except (ValidationError, SQLAlchemyError, OSError):
        Console(stderr=True).print("Invalid configuration or inaccessible GAR database.")
        raise typer.Exit(1) from None
    except ValueError as exc:
        Console(stderr=True).print(str(exc), markup=False)
        raise typer.Exit(1) from None
    finally:
        if database is not None:
            database.close()


def db_init() -> None:
    """Initialize database tables without changing existing tasks."""
    with repository():
        Console().print("GAR database ready (schema 1).")


def task_create(goal: str, model: str, max_steps: int = 50) -> None:
    """Record a pending goal. Does not call models or run tools."""
    with repository() as (repo, settings):
        task_id = uuid4().hex
        workspace = (settings.data_dir / "workspaces" / task_id).resolve()
        task = repo.create(
            Task(
                id=task_id, goal=goal, model_id=model, workspace=str(workspace), max_steps=max_steps
            )
        )
        Console().print_json(task.model_dump_json())


def tasks() -> None:
    """List persisted task snapshots."""
    with repository() as (repo, _):
        Console().print_json(data=[task.model_dump(mode="json") for task in repo.list()])


def task(task_id: str) -> None:
    """Inspect a task, its current plan and persisted events."""
    with repository() as (repo, _):
        snapshot = repo.get(task_id)
        plan = repo.get_plan(task_id)
        Console().print_json(
            data={
                "task": snapshot.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json") if plan else None,
                "events": [event.model_dump(mode="json") for event in repo.get_events(task_id)],
            }
        )


def cancel(task_id: str) -> None:
    """Mark a nonterminal task cancelled; Stage 2 has no active executor."""
    with repository() as (repo, _):
        snapshot = repo.get(task_id)
        result = repo.transition(task_id, TaskStatus.CANCELLED, snapshot.version)
        Console().print_json(result.model_dump_json())
