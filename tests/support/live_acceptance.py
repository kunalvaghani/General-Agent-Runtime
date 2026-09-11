"""Opt-in real Ollama/Docker acceptance using a fresh, isolated workspace.

Run: python tests/support/live_acceptance.py
Only scoped workspace tools and Docker execution in this fixture may be approved.
Host execution is never approved. Production task approval policy is unchanged.
"""

import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

from gar.config import Settings
from gar.core.orchestrator import Orchestrator
from gar.core.runtime import task_tools
from gar.core.state import Task, TaskStatus
from gar.models.ollama import OllamaAdapter
from gar.persistence.database import Database
from gar.persistence.repositories import TaskRepository


async def main():
    root = Path(".gar-run") / ("live-acceptance-" + uuid4().hex)
    root.mkdir(parents=True)
    configured = Settings()
    saved = configured.data_dir / "settings.json"
    if saved.exists():
        values = json.loads(saved.read_text("utf-8"))
        configured = Settings.model_validate(
            {
                **configured.model_dump(),
                **{k: v for k, v in values.items() if k in ("default_model", "model_timeout")},
            }
        )
    settings = configured.model_copy(update={"data_dir": root.absolute()})
    db = Database(root / "gar.db")
    db.initialize()
    repo = TaskRepository(db)
    task_id = uuid4().hex
    task = repo.create(
        Task(
            id=task_id,
            goal="Create a minimal Python/Tkinter calculator with digits, decimal input, "
            "addition (+), subtraction (-), multiplication (*), division (/), clear, "
            "equals, and graceful division-by-zero handling. No additional features. "
            "Include behavioral tests of the final files, including at least one "
            "button-driven calculation. Run the tests using the supported Docker tools "
            "and allowed test commands. Keep the GUI entry file importable for finite "
            "tests; the user will launch it through GAR's isolated desktop after verification.",
            model_id="qwen2.5-coder:7b",
            workspace=str(settings.data_dir / "workspaces" / task_id),
            max_steps=50,
        )
    )
    print(f"Acceptance workspace: {root.absolute()}", flush=True)
    adapter = OllamaAdapter(str(settings.ollama_url), timeout=settings.model_timeout)
    (root / "configuration.json").write_text(
        json.dumps({"model": task.model_id, "model_timeout": settings.model_timeout}),
        encoding="utf-8",
    )
    original = adapter.generate
    original_request = adapter._request

    async def request(method, path, **kwargs):
        result = await original_request(method, path, **kwargs)
        if path == "api/chat":
            with (root / "wire-responses.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result) + "\n")
        return result

    adapter._request = request

    async def generate(*args, **kwargs):
        print("Model request", flush=True)
        started = time.monotonic()
        result = await original(*args, **kwargs)
        with (root / "responses.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result.model_dump()) + "\n")
        print(f"Model response received in {time.monotonic() - started:.1f}s", flush=True)
        return result

    adapter.generate = generate
    runtime = Orchestrator(repo, adapter, task_tools(task, settings))
    try:
        result = await runtime.run(task.id)
        while result.status == TaskStatus.WAITING_APPROVAL:
            pending = result.metadata["execution"]["pending"]
            name = pending["decision"]["tool_name"]
            if name not in (
                "filesystem.read",
                "filesystem.list",
                "filesystem.mkdir",
                "filesystem.write",
                "terminal.run",
                "python.run",
                "git.status",
                "git.diff",
            ):
                break
            print(f"Fixture approval: {name}", flush=True)
            result = await runtime.run(task.id, pending["id"])
        (root / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(
            f"Result: {result.status}; "
            f"decisions={result.metadata.get('execution', {}).get('decisions')}",
            flush=True,
        )
        print(json.dumps(result.metadata.get("verification", {})), flush=True)
        return (
            0
            if result.status == TaskStatus.COMPLETED
            else (2 if result.status == TaskStatus.WAITING_APPROVAL else 1)
        )
    finally:
        # Keep a result snapshot even if planning or transport raises before run returns.
        (root / "result.json").write_text(
            repo.get(task.id).model_dump_json(indent=2), encoding="utf-8"
        )
        db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
