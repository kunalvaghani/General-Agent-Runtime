"""Start the installed CLI and verify an actual loopback HTTP response."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


@pytest.mark.parametrize(
    "launcher",
    [
        False,
        pytest.param(
            True, marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher")
        ),
    ],
)
def test_cli_starts_live_api(launcher, tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        **os.environ,
        "GAR_HOST": "127.0.0.1",
        "GAR_PORT": str(port),
        "GAR_DATA_DIR": str(tmp_path / "server-data"),
        "GAR_RUN_DIR": str(tmp_path / "tracked launches"),
    }
    command = [sys.executable, "-m", "gar", "serve"]
    if launcher:
        command = [
            "cmd.exe",
            "/d",
            "/c",
            str(Path(__file__).resolve().parents[2] / "run-gar.bat"),
            "--no-setup",
            "serve",
        ]
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError(f"Server exited: {process.communicate()[1]}")
                try:
                    response = client.get("/api/v1/health", timeout=0.5)
                except httpx.TransportError:
                    time.sleep(0.1)
                    continue
                assert response.status_code == 200
                assert response.json()["status"] == "ok"
                break
            else:
                raise AssertionError("Server did not become ready within 15 seconds")
    finally:
        if process.poll() is None:
            if launcher:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=10,
                    check=True,
                )
            else:
                process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
