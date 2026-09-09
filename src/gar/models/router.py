"""Deterministic hard constraints before stable cost/name ordering."""

from pydantic import BaseModel, Field

from gar.models.base import ModelNotFound, ModelProfile


class Requirements(BaseModel):
    local_only: bool = False
    coding: bool = False
    vision: bool = False
    context_size: int = Field(default=0, ge=0)
    max_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def choose(profiles: list[ModelProfile], needs: Requirements) -> ModelProfile:
    candidates = [
        p
        for p in profiles
        if (not needs.local_only or p.local)
        and (not needs.coding or p.coding is True)
        and (not needs.vision or p.vision is True)
        and p.context_window >= needs.context_size
        and (needs.max_cost is None or p.cost is not None and p.cost <= needs.max_cost)
    ]
    if not candidates:
        raise ModelNotFound("No model meets the requested constraints")
    return sorted(
        candidates, key=lambda p: (p.cost if p.cost is not None else float("inf"), p.provider, p.id)
    )[0]
