"""Explicit user tool invocation; model-driven execution belongs to Stage 5."""

import asyncio
import json
import re
from pathlib import Path

import typer
from rich.console import Console

from gar.cli.tasks import repository
from gar.safety.audit import Audit
from gar.safety.sandbox import reject_link
from gar.tools.registry import ToolRegistry


def tools() -> None:
    """List available tool schemas and risk levels."""
    Console().print_json(data=[spec.model_dump(mode="json") for spec in ToolRegistry.specs()])


def tool(task_id: str, name: str, input_file: Path, approve: bool = False) -> None:
    """Invoke a tool with a JSON argument file; --approve authorizes this exact call."""
    with repository() as (repo, settings):
        task = repo.get(task_id)
        if task.is_terminal:
            raise ValueError("Tools cannot run for a terminal task")
        if not re.fullmatch(r"[0-9a-f]{32}", task_id):
            raise ValueError("Invalid task workspace identifier")
        root = (settings.data_dir / "workspaces" / task_id).absolute()
        if Path(task.workspace) != root:
            raise ValueError("Task workspace does not match the runtime workspace")
        for path in (*reversed(root.parents), root):
            reject_link(path)
        root.mkdir(parents=True, exist_ok=True)
        with input_file.open("rb") as stream:
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Tool argument file exceeds 1 MB")
        arguments = json.loads(raw)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        registry = ToolRegistry(root, Audit(settings.data_dir / "tool-audit.db"), task_id=task_id)
        result = asyncio.run(registry.execute(name, arguments, approved=approve))
        Console().print_json(result.model_dump_json())
        if result.status != "ok":
            raise typer.Exit(1)
