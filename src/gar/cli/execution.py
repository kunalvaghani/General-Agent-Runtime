from rich.console import Console

from gar.cli.models import make_registry, run_command
from gar.cli.tasks import repository
from gar.core.executor import Executor
from gar.core.runtime import task_tools


def execute(task_id: str, approval_id: str | None = None):
    """Execute a saved plan; approvals apply only to the pending request ID."""

    async def work():
        with repository() as (repo, settings):
            task = repo.get(task_id)
            registry = make_registry(settings)
            await registry.refresh()
            result = await Executor(
                repo, registry.resolve(task.model_id), task_tools(task, settings)
            ).run(task_id, approval_id)
            Console().print_json(result.model_dump_json())

    run_command(work())
