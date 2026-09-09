"""Test-only ASGI host: temporary data and scripted model, real API/tools/SQLite/SSE."""

import tempfile
from pathlib import Path

import uvicorn
from scripted_provider import registry

import gar.api.routes.runtime
import gar.api.service
from gar.api.app import create_app
from gar.config import Settings

if __name__ == "__main__":
    gar.api.service.make_registry = registry
    gar.api.routes.runtime.make_registry = registry
    with tempfile.TemporaryDirectory(prefix="gar-browser-acceptance-") as directory:
        root = Path(directory)
        app = create_app(
            Settings(
                _env_file=None, data_dir=root, config_dir=root, web_origin="http://127.0.0.1:3100"
            )
        )
        uvicorn.run(app, host="127.0.0.1", port=8100, log_level="warning")
