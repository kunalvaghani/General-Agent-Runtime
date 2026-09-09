"""Approval is trusted caller input, never part of a model tool argument."""

from gar.tools.base import Risk, ToolFailure


def authorize(risk: Risk, approved: bool) -> None:
    if risk == Risk.PROHIBITED:
        raise ToolFailure("permission_denied", "This operation is prohibited.")
    if risk == Risk.DANGEROUS and not approved:
        raise ToolFailure("approval_required", "Explicit approval is required for this exact call.")
