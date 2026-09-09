import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from gar.cli.models import make_registry
from gar.core.state import Task, TaskStatus
from gar.models.base import ModelError
from gar.persistence.repositories import TaskNotFound
from gar.tools.registry import ToolRegistry

router = APIRouter()


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    goal: str = Field(min_length=1, max_length=20000)
    model: str = Field(min_length=1, max_length=200)
    max_steps: int = Field(default=50, ge=1, le=1000)
    start: bool = True


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    approve: bool


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_model: str | None = None
    model_timeout: float = Field(default=120, gt=0, le=3600, allow_inf_nan=False)


def service(request):
    return request.app.state.runtime


def find(request, task_id):
    try:
        return service(request).repo.get(task_id)
    except TaskNotFound:
        raise HTTPException(404, "Task not found") from None


@router.get("/models")
@router.post("/models/refresh")
async def models(request: Request):
    try:
        return await make_registry(service(request).settings).refresh()
    except ModelError as exc:
        raise HTTPException(503, str(exc)) from None


@router.get("/tools")
def tools():
    return ToolRegistry.specs()


@router.get("/tasks", response_model=list[Task])
def tasks(request: Request):
    return service(request).repo.list()


@router.post("/tasks", response_model=Task, status_code=201)
async def create(data: TaskInput, request: Request):
    runtime = service(request)
    task_id = uuid4().hex
    task = runtime.repo.create(
        Task(
            id=task_id,
            goal=data.goal,
            model_id=data.model,
            max_steps=data.max_steps,
            workspace=str((runtime.settings.data_dir / "workspaces" / task_id).absolute()),
        )
    )
    if data.start:
        runtime.submit(task.id)
    return task


@router.get("/tasks/{task_id}", response_model=Task)
def detail(task_id: str, request: Request):
    return find(request, task_id)


@router.get("/tasks/{task_id}/plan")
def plan(task_id: str, request: Request):
    find(request, task_id)
    return service(request).repo.get_plan(task_id)


@router.get("/tasks/{task_id}/snapshot")
def snapshot(task_id: str, request: Request):
    try:
        return service(request).repo.snapshot(task_id)
    except TaskNotFound:
        raise HTTPException(404, "Task not found") from None


@router.get("/tasks/{task_id}/tool-calls")
def calls(task_id: str, request: Request):
    return find(request, task_id).metadata.get("execution", {}).get("observations", [])


@router.post("/tasks/{task_id}/cancel", response_model=Task)
async def cancel(task_id: str, request: Request):
    find(request, task_id)
    return await service(request).cancel(task_id)


@router.post("/tasks/{task_id}/resume", response_model=Task)
async def resume(task_id: str, request: Request):
    task = find(request, task_id)
    if task.status not in (TaskStatus.BLOCKED, TaskStatus.PENDING, TaskStatus.PLANNING):
        raise HTTPException(409, "Task cannot resume")
    try:
        service(request).submit(
            task_id,
            retry=task.status == TaskStatus.BLOCKED
            and service(request).repo.get_plan(task_id) is not None,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return task


@router.post("/tasks/{task_id}/approve", response_model=Task)
async def approve(task_id: str, data: ApprovalInput, request: Request):
    task = find(request, task_id)
    pending = task.metadata.get("execution", {}).get("pending", {})
    if task.status != TaskStatus.WAITING_APPROVAL or pending.get("id") != data.request_id:
        raise HTTPException(409, "Approval request is stale or invalid")
    if not data.approve:
        return await service(request).cancel(task_id)
    try:
        service(request).submit(task_id, approval_id=data.request_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return task


@router.get("/tasks/{task_id}/events")
async def events(task_id: str, request: Request, after: int = 0):
    find(request, task_id)
    try:
        cursor = max(0, after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(400, "Invalid event cursor") from None

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            for event in service(request).repo.get_events(task_id, cursor):
                cursor = event.id
                yield f"id: {cursor}\ndata: {event.model_dump_json()}\n\n"
            task = service(request).repo.get(task_id)
            if task.is_terminal:
                yield "event: end\ndata: {}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/memory")
def memory(request: Request, query: str = "", category: str | None = None):
    return service(request).memory.search(query, category)


@router.delete("/memory/{item_id}")
def delete_memory(item_id: str, request: Request):
    if not service(request).memory.delete(item_id):
        raise HTTPException(404, "Memory not found")
    return {"deleted": True}


@router.get("/settings")
def settings(request: Request):
    config = service(request).settings
    return {"default_model": config.default_model, "model_timeout": config.model_timeout}


@router.patch("/settings")
def patch_settings(data: SettingsPatch, request: Request):
    runtime = service(request)
    values = {**settings(request), **data.model_dump(exclude_unset=True)}
    path = Path(runtime.settings.data_dir) / "settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values), encoding="utf-8")
    temporary.replace(path)
    runtime.settings = runtime.settings.model_copy(update=values)
    return values
