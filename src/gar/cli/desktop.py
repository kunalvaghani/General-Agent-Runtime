import asyncio

import typer
from rich.console import Console

from gar.cli.tasks import repository
from gar.desktop import DesktopManager

desktop_app = typer.Typer(help="Test and approve an isolated Python GUI desktop")


@desktop_app.command("prepare")
def prepare(task_id: str, entry: str):
    """Retest a frozen verified task snapshot; does not launch its GUI."""
    with repository() as (repo, settings):
        result = asyncio.run(DesktopManager(repo, settings).prepare(task_id, entry))
        Console().print_json(data=result)
        Console().print("Review this snapshot. To launch without network or host writes, use:")
        Console().print(f"run-gar.bat --no-setup desktop approve {result['id']}")


@desktop_app.command("approve")
def approve(session: str):
    """Explicitly approve the exact prepared snapshot; approval is single-use."""
    with repository() as (repo, settings):
        result = asyncio.run(DesktopManager(repo, settings).approve(session))
        Console().print_json(data=result)
        Console().print("Open the task page in GAR and enter this desktop session ID to view it.")


@desktop_app.command("stop")
def stop(session: str):
    with repository() as (repo, settings):
        Console().print_json(data=asyncio.run(DesktopManager(repo, settings).stop(session)))
