"""Provider registration and atomic discovery snapshots; no capability guessing."""

from gar.models.base import ModelAdapter, ModelNotFound, ModelProfile


class ModelRegistry:
    def __init__(self) -> None:
        self.adapters: dict[str, ModelAdapter] = {}
        self.profiles: dict[tuple[str, str], ModelProfile] = {}

    def register(self, adapter: ModelAdapter) -> None:
        if adapter.provider in self.adapters:
            raise ValueError("Provider is already registered")
        self.adapters[adapter.provider] = adapter

    async def refresh(self) -> list[ModelProfile]:
        snapshot: dict[tuple[str, str], ModelProfile] = {}
        for provider, adapter in self.adapters.items():
            for profile in await adapter.discover():
                if profile.provider != provider:
                    raise ValueError("Discovered model has the wrong provider")
                snapshot[(provider, profile.id)] = profile
        self.profiles = snapshot
        return list(snapshot.values())

    def resolve(self, model: str, provider: str = "ollama") -> ModelAdapter:
        if (provider, model) not in self.profiles:
            raise ModelNotFound("Model is not installed; run gar models to list available names.")
        return self.adapters[provider]
