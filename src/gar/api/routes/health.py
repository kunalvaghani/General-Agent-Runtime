"""Process liveness only; provider readiness comes in later stages."""

import os
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from gar import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["gar"] = "gar"
    version: str = __version__


@router.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    if instance := os.environ.get("GAR_LAUNCH_ID"):
        response.headers["X-GAR-Launch-ID"] = instance
    return HealthResponse()
