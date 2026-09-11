"""Track and stop only processes and containers owned by this repository's launches."""

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]


def run_directory():
    return Path(os.environ.get("GAR_RUN_DIR", ROOT / ".gar-run"))


def identity(pid):
    process = psutil.Process(pid)
    return {"pid": pid, "created": process.create_time()}


def owned_process(record):
    try:
        process = psutil.Process(record["pid"])
        return process if process.create_time() == record["created"] else None
    except (psutil.NoSuchProcess, KeyError):
        return None


def save_launch(instance, processes):
    directory = run_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{instance}.json"
    tracked = {}
    if target.exists():
        for item in json.loads(target.read_text("utf-8"))["children"]:
            tracked[(item["pid"], item["created"])] = item
    for child in processes:
        if child.poll() is not None:
            continue
        try:
            parent = psutil.Process(child.pid)
            # Check the handle again after resolving the PID, before discovering descendants.
            if child.poll() is not None:
                continue
            for process in [parent, *parent.children(recursive=True)]:
                item = {"pid": process.pid, "created": process.create_time()}
                tracked[(item["pid"], item["created"])] = item
        except psutil.NoSuchProcess:
            pass
    record = {
        "repository": str(ROOT),
        "instance": instance,
        "launcher": identity(os.getpid()),
        "children": list(tracked.values()),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(record), encoding="utf-8")
    temporary.replace(target)
    return target


def stop_tree(record):
    parent = owned_process(record)
    if parent is None:
        return
    try:
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    processes = [*reversed(children), parent]
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(processes, timeout=3)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=3)
    if alive:
        raise RuntimeError("Some GAR-owned processes could not be stopped.")


def clean_containers(instance):
    if not re.fullmatch(r"[a-f0-9]{32}", instance):
        raise ValueError("Invalid launch identifier")
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker is unavailable; container cleanup cannot be verified.")
    result = subprocess.run(
        [docker, "ps", "-aq", "--filter", f"label=gar.launch={instance}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Docker cleanup could not be verified. Start Docker and run stop-gar again."
        )
    containers = result.stdout.split()
    if containers:
        subprocess.run(
            [docker, "rm", "-f", *containers], capture_output=True, timeout=15, check=True
        )


def cleanup_launch(instance, children):
    """Attempt every cleanup even when an individual process cannot be stopped."""
    failures = []
    for child in children:
        try:
            stop_tree(child)
        except (OSError, RuntimeError, psutil.Error) as exc:
            failures.append(str(exc))
    try:
        clean_containers(instance)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        failures.append(str(exc))
    if failures:
        raise RuntimeError("; ".join(failures))


def stop_all():
    directory = run_directory()
    records = []
    failures = []
    # Desktop sessions can also be started from the standalone CLI.
    try:
        import asyncio

        from gar.config import Settings
        from gar.desktop import DesktopManager

        settings = Settings()
        if (settings.data_dir / "desktops").exists():
            asyncio.run(DesktopManager(None, settings).close())
    except (OSError, ValueError, TimeoutError) as exc:
        failures.append(f"Desktop cleanup incomplete: {exc}")
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text("utf-8"))
            if record["repository"] != str(ROOT) or record["instance"] != path.stem:
                raise ValueError("Invalid launch record")
            if not re.fullmatch(r"[a-f0-9]{32}", path.stem):
                raise ValueError("Invalid launch identifier")
            path.with_suffix(".stop").touch()
            records.append((path, record))
        except (OSError, ValueError, KeyError) as exc:
            failures.append(str(exc))
    deadline = time.monotonic() + 25

    def launcher_active(path, record):
        if not path.exists():
            return False
        try:
            return owned_process(record["launcher"]) is not None
        except psutil.AccessDenied:
            # Attempt the remaining cleanup; retain this record if termination is denied.
            return False

    while time.monotonic() < deadline and any(
        launcher_active(path, record) for path, record in records
    ):
        time.sleep(0.2)
    for path, record in records:
        try:
            if not path.exists():
                # The launcher has already verified cleanup and removed its record.
                path.with_suffix(".stop").unlink(missing_ok=True)
                continue
            latest = json.loads(path.read_text("utf-8"))
            if latest["instance"] != record["instance"] or latest["launcher"] != record["launcher"]:
                raise ValueError("Launch record changed identity")
            cleanup_launch(record["instance"], [*latest["children"], record["launcher"]])
            path.unlink(missing_ok=True)
            path.with_suffix(".stop").unlink(missing_ok=True)
        except (
            OSError,
            ValueError,
            KeyError,
            RuntimeError,
            subprocess.SubprocessError,
            psutil.Error,
        ) as exc:
            failures.append(str(exc))
    for failure in failures:
        print(failure)
    if failures:
        return 1
    print(
        "GAR services and tracked task containers stopped."
        if records
        else "No tracked GAR services are running."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(stop_all())
