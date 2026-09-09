"""One local worker at a time, with persisted task state and explicit cancellation."""

import asyncio
import json

from gar.cli.models import make_registry
from gar.core.orchestrator import Orchestrator
from gar.core.runtime import task_tools
from gar.core.state import StepStatus, TaskStatus
from gar.memory.manager import MemoryManager
from gar.persistence.repositories import TaskRepository


class RuntimeService:
    def __init__(self, database, settings):
        self.repo = TaskRepository(database)
        self.settings = settings
        saved = settings.data_dir / "settings.json"
        if saved.exists():
            values = json.loads(saved.read_text("utf-8"))
            self.settings = type(settings).model_validate(
                {
                    **settings.model_dump(),
                    **{k: v for k, v in values.items() if k in ("default_model", "model_timeout")},
                }
            )
        self.memory = MemoryManager(settings.data_dir / "memory.db")
        self.workers = {}
        self.lock = asyncio.Lock()

    def submit(self, task_id, approval_id=None, retry=False):
        if task_id in self.workers and not self.workers[task_id].done():
            raise ValueError("Task already scheduled")
        worker = asyncio.create_task(self._run(task_id, approval_id, retry))
        self.workers[task_id] = worker

    async def _run(self, task_id, approval_id, retry):
        async with self.lock:
            try:
                task = self.repo.get(task_id)
                if task.is_terminal:
                    return
                registry = make_registry(self.settings)
                await registry.refresh()
                runtime = Orchestrator(
                    self.repo,
                    registry.resolve(task.model_id),
                    task_tools(task, self.settings),
                    self.memory,
                )
                await runtime.run(task_id, approval_id, retry)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not expose provider errors or secret-bearing tracebacks over HTTP.
                task = self.repo.get(task_id)
                if not task.is_terminal:
                    if task.status == TaskStatus.PENDING:
                        task = self.repo.transition(task_id, TaskStatus.PLANNING, task.version)
                    if task.current_step and task.status == TaskStatus.RUNNING:
                        task = self.repo.transition_step(
                            task_id, task.current_step, StepStatus.FAILED, task.version
                        )
                    if task.status != TaskStatus.BLOCKED:
                        self.repo.transition(task_id, TaskStatus.BLOCKED, task.version)

    async def cancel(self, task_id):
        task = self.repo.get(task_id)
        if not task.is_terminal:
            task = self.repo.transition(task_id, TaskStatus.CANCELLED, task.version)
        worker = self.workers.get(task_id)
        if worker and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        return task

    async def close(self):
        for worker in self.workers.values():
            if not worker.done():
                worker.cancel()
        await asyncio.gather(*self.workers.values(), return_exceptions=True)
        for task_id in self.workers:
            task = self.repo.get(task_id)
            if task.status in (TaskStatus.PLANNING, TaskStatus.RUNNING):
                if task.current_step and task.status == TaskStatus.RUNNING:
                    task = self.repo.transition_step(
                        task_id, task.current_step, StepStatus.FAILED, task.version
                    )
                self.repo.transition(task_id, TaskStatus.BLOCKED, task.version)
