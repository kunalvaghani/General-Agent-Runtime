"""Discover, select and query models without executing any proposed tools."""

import asyncio
from collections.abc import Coroutine
from typing import Any

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from gar.config import Settings
from gar.models.base import Message, ModelError
from gar.models.ollama import OllamaAdapter
from gar.models.registry import ModelRegistry
from gar.models.selection import load_selection, save_selection

models_app = typer.Typer(help="Discover installed Ollama models.", invoke_without_command=True)


def make_registry(settings: Settings) -> ModelRegistry:
    registry = ModelRegistry()
    registry.register(OllamaAdapter(str(settings.ollama_url), settings.model_timeout))
    return registry


def run_command(operation: Coroutine[Any, Any, None]) -> None:
    try:
        asyncio.run(operation)
    except ValidationError:
        Console(stderr=True).print("Invalid GAR configuration or model input.")
        raise typer.Exit(2) from None
    except ModelError as exc:
        Console(stderr=True).print(str(exc), markup=False)
        raise typer.Exit(1) from None


async def list_models() -> None:
    registry = make_registry(Settings())
    profiles = await registry.refresh()
    if not profiles:
        Console().print("Ollama is reachable, but no models are installed.")
        return
    table = Table("Provider", "Model")
    for profile in profiles:
        table.add_row(profile.provider, profile.id)
    Console().print(table)


@models_app.callback()
def models(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        run_command(list_models())


@models_app.command()
def refresh() -> None:
    """Fetch a fresh model list from the provider."""
    run_command(list_models())


def use(model: str) -> None:
    """Select an installed model for subsequent gar ask commands."""

    async def select() -> None:
        settings = Settings()
        registry = make_registry(settings)
        await registry.refresh()
        registry.resolve(model)
        save_selection(settings.config_dir, model)
        Console().print(f"Selected {model}", markup=False)

    run_command(select())


def ask(prompt: str, model: str | None = None) -> None:
    """Send a single prompt to a model; does not execute tools."""

    async def generate() -> None:
        if not prompt.strip():
            raise ModelError("Prompt must not be empty.")
        settings = Settings()
        selected = model or settings.default_model or load_selection(settings.config_dir)
        if not selected:
            raise ModelError("Choose a model with gar use, GAR_DEFAULT_MODEL, or --model.")
        registry = make_registry(settings)
        await registry.refresh()
        adapter = registry.resolve(selected)
        answer = await adapter.generate(selected, [Message(role="user", content=prompt)])
        Console().print(answer.content, markup=False, highlight=False)
        if answer.tool_calls:
            Console().print("Model proposed tool calls; execution is unavailable in Stage 1.")

    run_command(generate())
