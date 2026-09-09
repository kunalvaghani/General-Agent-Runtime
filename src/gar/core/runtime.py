"""Shared construction of task-scoped tools for CLI and API."""

import re
from pathlib import Path

from gar.safety.audit import Audit
from gar.safety.sandbox import reject_link
from gar.tools.registry import ToolRegistry


def task_tools(task, settings):
    if not re.fullmatch(r"[0-9a-f]{32}", task.id):
        raise ValueError("Invalid task ID")
    root = (settings.data_dir / "workspaces" / task.id).absolute()
    if Path(task.workspace) != root:
        raise ValueError("Workspace mismatch")
    for path in (*reversed(root.parents), root):
        reject_link(path)
    root.mkdir(parents=True, exist_ok=True)
    return ToolRegistry(root, Audit(settings.data_dir / "tool-audit.db"), task_id=task.id)
