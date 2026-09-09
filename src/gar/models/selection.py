"""Persist only user model selection; task persistence belongs to Stage 2."""

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from gar.models.base import Contract, ModelError


class Selection(Contract):
    model: str


def load_selection(directory: Path) -> str | None:
    try:
        return Selection.model_validate_json((directory / "model.json").read_text("utf-8")).model
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError):
        raise ModelError("Cannot read saved model selection; run gar use to replace it.") from None


def save_selection(directory: Path, model: str) -> None:
    temporary: str | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False
        ) as f:
            temporary = f.name
            f.write(Selection(model=model).model_dump_json())
        os.replace(temporary, directory / "model.json")
    except OSError:
        raise ModelError("Cannot save model selection; check GAR_CONFIG_DIR permissions.") from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
