"""Run the API and frontend together, stopping only owned child processes."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from uuid import uuid4

import httpx

from gar.config import Settings
from gar.lifecycle import cleanup_launch, identity, save_launch


def preferred_ui_port(configured):
    # A free socket does not mean a clean browser origin: Open WebUI can leave
    # cached assets/service workers behind on 3000 even after its server stops.
    return 4317 if configured == 3000 else configured


def available_port(preferred, host="127.0.0.1", excluded=()):
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    for port in range(preferred, min(preferred + 100, 65536)):
        if port in excluded:
            continue
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port near {preferred}; close an older GAR window and retry.")


def frontend_ready(client, url, instance):
    health = client.get(url + "/api/v1/health")
    if (
        health.status_code != 200
        or health.headers.get("X-GAR-Launch-ID") != instance
        or health.json().get("service") != "gar"
    ):
        return False
    page = client.get(url)
    return page.status_code == 200 and 'data-gar-app="runtime"' in page.text


def open_frontend(url):
    if os.environ.get("GAR_OPEN_BROWSER") == "0":
        return
    try:
        if not webbrowser.open_new_tab(url):
            print(f"Open this address in your browser: {url}", flush=True)
    except (webbrowser.Error, OSError):
        print(f"Open this address in your browser: {url}", flush=True)


def main(mode="dev"):
    root = Path(__file__).resolve().parents[2]
    settings = Settings()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm and mode != "serve":
        print("Node.js and npm are required. Run web-setup after installing Node.js.")
        return 1
    environment = os.environ.copy()
    host = f"[{settings.host}]" if ":" in settings.host else settings.host
    api_port = available_port(settings.port, settings.host) if mode != "web" else settings.port
    preferred_web_port = preferred_ui_port(settings.web_origin.port or 80)
    chosen_web_port = (
        available_port(preferred_web_port, excluded=(api_port,))
        if mode != "serve"
        else settings.web_origin.port or 80
    )
    web_port = str(chosen_web_port)
    ui_url = f"http://127.0.0.1:{web_port}"
    instance = uuid4().hex
    environment.update(
        GAR_PORT=str(api_port),
        GAR_WEB_ORIGIN=ui_url,
        GAR_LAUNCH_ID=instance,
    )
    if mode != "web":
        environment["GAR_BACKEND_URL"] = f"http://{host}:{api_port}"
    if api_port != settings.port:
        print(f"Backend port {settings.port} is occupied; using {api_port}.", flush=True)
    if mode != "serve" and settings.web_origin.port == 3000:
        print(
            "Using GAR's dedicated UI address to avoid Open WebUI's cached port 3000.", flush=True
        )
    if mode != "serve" and chosen_web_port != preferred_web_port:
        print(
            f"Frontend port {preferred_web_port} is occupied; using {web_port}.",
            flush=True,
        )
    print(f"GAR backend: http://{host}:{api_port}", flush=True)
    processes = []
    manifest = None
    children = []
    try:
        manifest = save_launch(instance, processes)
        if mode != "web":
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "gar", "serve"],
                    cwd=root,
                    env=environment,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
            )
            children.append(identity(processes[-1].pid))
            save_launch(instance, processes)
        command = [npm, "run", "dev", "--", "--port", web_port]
        if os.name == "nt":
            command = [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/c",
                npm,
                "run",
                "dev",
                "--",
                "--port",
                web_port,
            ]
        if mode != "serve":
            processes.append(subprocess.Popen(command, cwd=root / "web", env=environment))
            children.append(identity(processes[-1].pid))
            save_launch(instance, processes)
        print(
            (f"Starting GAR UI at {ui_url}." if mode != "serve" else "Starting GAR API.")
            + " Keep this window open; Ctrl+C or stop-gar.bat stops GAR.",
            flush=True,
        )
        ready = False
        last_tracking = 0.0
        deadline = time.monotonic() + 90
        with httpx.Client(trust_env=False, timeout=2) as client:
            while all(process.poll() is None for process in processes):
                if time.monotonic() - last_tracking > 1:
                    save_launch(instance, processes)
                    last_tracking = time.monotonic()
                if manifest.with_suffix(".stop").exists():
                    print("Stopping GAR services and active task containers…", flush=True)
                    return 0
                if not ready:
                    try:
                        if mode == "serve":
                            response = client.get(f"http://{host}:{api_port}/api/v1/health")
                            ready = (
                                response.status_code == 200
                                and response.headers.get("X-GAR-Launch-ID") == instance
                            )
                        elif mode == "web":
                            response = client.get(ui_url)
                            ready = (
                                response.status_code == 200
                                and 'data-gar-app="runtime"' in response.text
                            )
                        else:
                            ready = frontend_ready(client, ui_url, instance)
                        if ready:
                            ready_url = (
                                ui_url if mode != "serve" else environment["GAR_BACKEND_URL"]
                            )
                            print(f"GAR is ready: {ready_url}", flush=True)
                            if mode != "serve":
                                open_frontend(ui_url)
                    except (httpx.HTTPError, ValueError):
                        pass
                    if not ready and time.monotonic() >= deadline:
                        print("Startup timed out. Check the service errors above.", flush=True)
                        return 1
                time.sleep(0.25)
        print(
            "A GAR service stopped. Check the error above; "
            "another GAR window may already be using its port.",
            flush=True,
        )
        return next(
            (process.returncode or 1 for process in processes if process.poll() is not None), 1
        )
    except KeyboardInterrupt:
        return 0
    finally:
        if manifest and manifest.exists():
            children.extend(json.loads(manifest.read_text("utf-8"))["children"])
        if mode != "web" and processes and processes[0].poll() is None:
            try:
                processes[0].send_signal(
                    signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM
                )
                processes[0].wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            cleanup_launch(instance, children)
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            print(f"Cleanup incomplete: {exc}", flush=True)
            return 1
        else:
            if manifest:
                manifest.unlink(missing_ok=True)
                manifest.with_suffix(".stop").unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("dev", "serve", "web"), default="dev")
    raise SystemExit(main(parser.parse_args().mode))
