"""Generate and persist a plan for an existing task without executing it."""

from rich.console import Console

from gar.cli.models import make_registry, run_command
from gar.cli.tasks import repository
from gar.core.planner import Planner, PlanningService


def plan(task_id: str) -> None:
    """Generate a validated plan for a pending or blocked task using its saved model."""

    async def generate() -> None:
        with repository() as (repo, settings):
            task = repo.get(task_id)
            registry = make_registry(settings)
            await registry.refresh()
            adapter = registry.resolve(task.model_id)
            service = PlanningService(repo, Planner(adapter))
            result = await service.plan_task(task_id)
            Console().print_json(result.model_dump_json())

    run_command(generate())
