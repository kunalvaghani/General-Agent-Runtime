"""Verify the combined batch launcher and its configured same-origin API proxy."""

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
@pytest.mark.parametrize("occupied", [False, True])
def test_combined_launcher_custom_ports_and_preserved_data(tmp_path, occupied):
    root = Path(__file__).resolve().parents[2]
    if not (root / "web/node_modules/next").exists():
        pytest.skip("Run web-setup to install frontend dependencies")
    api_port, web_port = free_port(), free_port()
    while api_port == web_port:
        web_port = free_port()
    owners = []
    if occupied:
        for port in (api_port, web_port):
            owner = socket.socket()
            owner.bind(("127.0.0.1", port))
            owner.listen()
            owners.append(owner)
    data = tmp_path / "launcher data"
    data.mkdir()
    marker = data / "user-data.txt"
    marker.write_text("keep")
    environment = {
        **os.environ,
        "GAR_PORT": str(api_port),
        "GAR_WEB_ORIGIN": f"http://127.0.0.1:{web_port}",
        "GAR_DATA_DIR": str(data),
        "GAR_CONFIG_DIR": str(tmp_path / "config"),
        "GAR_OPEN_BROWSER": "0",
        "GAR_RUN_DIR": str(tmp_path / "tracked launches"),
        "GAR_TEST_DIST_DIR": ".next-test-" + uuid4().hex,
    }
    log_path = tmp_path / "launcher.log"
    with log_path.open("w+") as log:
        process = subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(root / "run-gar.bat"), "--no-setup"],
            cwd=tmp_path,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 60
            with httpx.Client(trust_env=False) as client:
                while time.monotonic() < deadline:
                    assert process.poll() is None, log_path.read_text()
                    output = log_path.read_text()
                    ui = re.search(r"Starting GAR UI at http://127.0.0.1:(\d+)", output)
                    backend = re.search(r"GAR backend: http://127.0.0.1:(\d+)", output)
                    if not ui or not backend:
                        time.sleep(0.25)
                        continue
                    actual_web_port, actual_api_port = int(ui[1]), int(backend[1])
                    try:
                        response = client.get(
                            f"http://127.0.0.1:{actual_web_port}/api/v1/health", timeout=2
                        )
                        if response.status_code == 200:
                            assert response.json()["service"] == "gar"
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)
                else:
                    pytest.fail("Combined launcher did not become ready: " + log_path.read_text())
                assert client.get(f"http://127.0.0.1:{actual_api_port}/api/v1/tasks").json() == []
                assert marker.read_text() == "keep"
                page = client.get(f"http://127.0.0.1:{actual_web_port}/", timeout=30)
                assert page.status_code == 200 and "Your agent workspace" in page.text
                assert 'data-gar-app="runtime"' in page.text
                if occupied:
                    assert actual_api_port != api_port and actual_web_port != web_port
                    assert all(owner.fileno() != -1 for owner in owners)
                stopped = subprocess.run(
                    ["cmd.exe", "/d", "/c", str(root / "stop-gar.bat"), "--no-pause"],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                assert stopped.returncode == 0, stopped.stdout + stopped.stderr
                process.wait(timeout=10)
                assert not list((tmp_path / "tracked launches").glob("*.json"))
                with pytest.raises(httpx.TransportError):
                    client.get(f"http://127.0.0.1:{actual_web_port}/", timeout=1)
                with pytest.raises(httpx.TransportError):
                    client.get(f"http://127.0.0.1:{actual_api_port}/api/v1/health", timeout=1)
        finally:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                    check=True,
                )
            process.wait(timeout=15)
            for owner in owners:
                owner.close()
            # Next adds its temporary type directories to the shared config.
            # Remove only this test's entries, preserving any concurrent settings.
            config_path = root / "web/tsconfig.json"
            config = json.loads(config_path.read_text("utf-8"))
            original = config.get("include", [])
            config["include"] = [
                item
                for item in original
                if not item.startswith(environment["GAR_TEST_DIST_DIR"] + "/")
            ]
            if config["include"] != original:
                config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
