from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class DesktopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry: str = Field(min_length=1, max_length=200)


class DesktopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    value: str = Field(default="", max_length=200)
    x: int = Field(default=0, ge=0, lt=1024)
    y: int = Field(default=0, ge=0, lt=768)


def manager(request, task_id, session=None):
    desktop = request.app.state.desktop
    if session and desktop.read(session)["task_id"] != task_id:
        raise ValueError("Desktop belongs to another task")
    return desktop


@router.post("/tasks/{task_id}/desktop")
async def prepare(task_id: str, data: DesktopRequest, request: Request):
    try:
        return await manager(request, task_id).prepare(task_id, data.entry)
    except (ValueError, OSError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/tasks/{task_id}/desktop/{session}")
async def status(task_id: str, session: str, request: Request):
    try:
        return await manager(request, task_id, session).status(session)
    except (ValueError, OSError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/tasks/{task_id}/desktop/{session}/{action}")
async def action(task_id: str, session: str, action: str, request: Request):
    try:
        desktop = manager(request, task_id, session)
        if action == "approve":
            return await desktop.approve(session)
        if action == "stop":
            return await desktop.stop(session)
        raise ValueError("Unknown desktop action")
    except (ValueError, OSError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/tasks/{task_id}/desktop/{session}/frame")
async def frame(task_id: str, session: str, request: Request):
    try:
        data = await manager(request, task_id, session).frame(session)
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})
    except (ValueError, OSError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/tasks/{task_id}/desktop/{session}/input/send")
async def send(task_id: str, session: str, data: DesktopInput, request: Request):
    try:
        await manager(request, task_id, session).input(session, **data.model_dump())
        return {"sent": True}
    except (ValueError, OSError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from None
