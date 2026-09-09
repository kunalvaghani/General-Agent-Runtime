"""Local API and model CLI commands."""

import typer
import uvicorn
from pydantic import ValidationError
from rich.console import Console

from gar import __version__
from gar.api.app import create_app
from gar.cli.execution import execute
from gar.cli.models import ask, models_app, use
from gar.cli.planning import plan
from gar.cli.runtime import approve, config_app, doctor, memory_app, replan, resume, run
from gar.cli.tasks import cancel, db_init, task, task_create, tasks
from gar.cli.tools import tool, tools
from gar.config import Settings

app = typer.Typer(help="GAR — General Agent Runtime.", no_args_is_help=True)
app.add_typer(models_app, name="models")
app.command()(use)
app.command()(ask)
app.command()(plan)
app.command()(execute)
for command in (run, resume, approve, replan, doctor):
    app.command()(command)
app.add_typer(memory_app, name="memory")
app.add_typer(config_app, name="config")
for command in (db_init, task_create, tasks, task, cancel, tool, tools):
    app.command()(command)


@app.command()
def version() -> None:
    """Show the installed GAR version."""
    Console().print(f"GAR {__version__}")


@app.command()
def serve() -> None:
    """Start the local API using GAR_HOST, GAR_PORT and GAR_LOG_LEVEL."""
    try:
        settings = Settings()
    except ValidationError as exc:
        # Do not echo configuration values, which could contain secrets.
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        Console(stderr=True).print(f"Invalid GAR configuration: {fields}")
        raise typer.Exit(code=2) from None
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        timeout_graceful_shutdown=5,
    )
