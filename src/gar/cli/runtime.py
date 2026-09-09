"""Production local CLI workflows with live events and explicit approvals."""

import asyncio
from uuid import uuid4

import typer
from rich.console import Console

from gar.cli.models import make_registry, run_command
from gar.cli.tasks import repository
from gar.core.orchestrator import Orchestrator
from gar.core.runtime import task_tools
from gar.core.state import Task
from gar.memory.manager import MemoryManager
from gar.models.selection import load_selection

memory_app = typer.Typer(help="Inspect and delete attributed memories")
config_app = typer.Typer(help="Inspect runtime configuration")


async def work(repo, settings, task, approval_id=None, retry=False, replan=False):
    registry = make_registry(settings)
    await registry.refresh()
    runtime = Orchestrator(
        repo,
        registry.resolve(task.model_id),
        task_tools(task, settings),
        MemoryManager(settings.data_dir / "memory.db"),
    )
    operation = asyncio.create_task(
        runtime.replan(task.id) if replan else runtime.run(task.id, approval_id, retry)
    )
    cursor = 0
    console = Console()
    try:
        while not operation.done():
            for event in repo.get_events(task.id, cursor):
                cursor = event.id
                console.print(f"{event.id}  {event.event.value}", markup=False)
            await asyncio.sleep(0.1)
        result = await operation
        for event in repo.get_events(task.id, cursor):
            console.print(f"{event.id}  {event.event.value}", markup=False)
        console.print_json(result.model_dump_json())
        return result
    finally:
        if not operation.done():
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)


def run(goal: str, model: str | None = None, max_steps: int = 50):
    """Plan, execute and verify a goal; pause for exact-call approval when needed."""

    async def start():
        with repository() as (repo, settings):
            selected = model or settings.default_model or load_selection(settings.config_dir)
            if not selected:
                raise ValueError("Select a model using gar use or --model")
            task_id = uuid4().hex
            task = repo.create(
                Task(
                    id=task_id,
                    goal=goal,
                    model_id=selected,
                    max_steps=max_steps,
                    workspace=str((settings.data_dir / "workspaces" / task_id).absolute()),
                )
            )
            Console().print(f"Task {task.id}")
            await work(repo, settings, task)

    run_command(start())


def resume(task_id: str):
    """Retry a blocked task within its existing action budget."""

    async def start():
        with repository() as (repo, settings):
            await work(repo, settings, repo.get(task_id), retry=repo.get_plan(task_id) is not None)

    run_command(start())


def approve(task_id: str, request_id: str):
    """Approve the exact stored tool request shown in task details."""

    async def start():
        with repository() as (repo, settings):
            await work(repo, settings, repo.get(task_id), approval_id=request_id)

    run_command(start())


def replan(task_id: str):
    """Generate a bounded replacement plan for a blocked task."""

    async def start():
        with repository() as (repo, settings):
            await work(repo, settings, repo.get(task_id), replan=True)

    run_command(start())


def doctor():
    """Check configuration, SQLite, model discovery and container availability."""

    async def check():
        with repository() as (_, settings):
            import shutil

            Console().print(f"Database ready; Docker CLI: {bool(shutil.which('docker'))}")
            models = await make_registry(settings).refresh()
            Console().print(f"Ollama reachable; {len(models)} installed models")

    run_command(check())


@memory_app.command("list")
def memory_list(query: str = ""):
    with repository() as (_, settings):
        Console().print_json(
            data=[
                i.model_dump() for i in MemoryManager(settings.data_dir / "memory.db").search(query)
            ]
        )


@memory_app.command("clear")
def memory_clear():
    with repository() as (_, settings):
        MemoryManager(settings.data_dir / "memory.db").clear()
        Console().print("Memory cleared")


@config_app.command("show")
def config_show():
    with repository() as (_, settings):
        Console().print_json(settings.model_dump_json())


@config_app.command("set")
def config_set(key: str, value: str):
    import json

    from gar.api.routes.runtime import SettingsPatch

    with repository() as (_, settings):
        if key not in ("default_model", "model_timeout"):
            raise ValueError("Supported keys: default_model, model_timeout")
        path = settings.data_dir / "settings.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data[key] = float(value) if key == "model_timeout" else value
        data = SettingsPatch.model_validate(data).model_dump()
        path.write_text(json.dumps(data), encoding="utf-8")
        Console().print("Settings saved")
