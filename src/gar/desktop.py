"""User-approved, tested Python desktops with no host-code execution."""

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from uuid import uuid4

from gar.safety.audit import Audit
from gar.safety.sandbox import Workspace
from gar.tools.process import capture

IMAGE = "gar-desktop:1"


def inventory(root):
    workspace = Workspace(root)
    workspace.validate_mount()
    result = {}
    total = 0
    for base, dirs, files in os.walk(workspace.root):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            relative = (Path(base) / name).relative_to(workspace.root).as_posix()
            path = workspace.resolve(relative)
            total += path.stat().st_size
            if total > 100_000_000 or len(result) >= 3000:
                raise ValueError("Desktop workspace limit: 100 MB and 3000 files")
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class DesktopManager:
    def __init__(self, repo, settings):
        self.repo, self.settings = repo, settings
        self.root = (settings.data_dir / "desktops").absolute()
        self.owner = hashlib.sha256(str(self.root).encode()).hexdigest()
        self.audit = Audit(settings.data_dir / "desktop-audit.db")
        self.lock = asyncio.Lock()

    def directory(self, session):
        if not re.fullmatch("[a-f0-9]{32}", session):
            raise ValueError("Invalid desktop request")
        return self.root / session

    def save(self, record):
        path = self.directory(record["id"]) / "request.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(record), encoding="utf-8")
        temp.replace(path)

    def read(self, session):
        try:
            return json.loads((self.directory(session) / "request.json").read_text("utf-8"))
        except FileNotFoundError:
            raise ValueError(
                "Desktop session not found. Use the session ID returned by desktop prepare, "
                "not the task ID. For a new desktop, complete task verification and then "
                "select Test frozen copy."
            ) from None

    async def docker(self, *args, timeout=15):
        executable = shutil.which("docker")
        if not executable:
            raise ValueError("Docker is unavailable")
        code, output, truncated = await capture([executable, *args], timeout)
        if code or truncated:
            raise ValueError(output[:2000] or "Docker operation failed")
        return output.strip()

    def command(self, record, mode):
        source = self.directory(record["id"]) / "source"
        if "," in str(source):
            raise ValueError("Desktop data path cannot contain commas")
        labels = ["--label", f"gar.desktop={self.owner}"]
        if os.environ.get("GAR_LAUNCH_ID"):
            labels += ["--label", f"gar.launch={os.environ['GAR_LAUNCH_ID']}"]
        return [
            "run",
            *(["--rm"] if mode == "test" else []),
            "--name",
            "gar-desktop-" + record["id"],
            *labels,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=128",
            "--memory=512m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs=/tmp:rw,nosuid,size=256m",
            "--mount",
            f"type=bind,source={source},target=/source,readonly",
            record["image"],
            mode,
            record["entry"],
        ]

    async def prepare(self, task_id, entry):
        async with self.lock:
            task = self.repo.get(task_id)
            if task.status != "COMPLETED" or not task.metadata.get("verification", {}).get(
                "passed"
            ):
                raise ValueError("Complete task verification before requesting a desktop")
            expected = (self.settings.data_dir / "workspaces" / task.id).absolute()
            if Path(task.workspace) != expected:
                raise ValueError("Task workspace mismatch")
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.py", entry):
                raise ValueError("Select a workspace-relative Python file")
            original = inventory(expected)
            if entry not in original:
                raise ValueError("Entry file is not in the workspace")
            image = await self.docker("image", "inspect", IMAGE, "--format", "{{.Id}}")
            session = uuid4().hex
            source = self.directory(session) / "source"
            source.mkdir(parents=True)
            for relative in original:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(Workspace(expected).resolve(relative).read_bytes())
            if inventory(source) != original or inventory(expected) != original:
                raise ValueError("Workspace changed while preparing; test again")
            record = {
                "id": session,
                "task_id": task_id,
                "entry": entry,
                "image": image,
                "files": original,
                "workspace": str(expected),
                "state": "testing",
                "expires": time.time() + 900,
            }
            self.save(record)
            self.audit.append(session, "testing", {"task_id": task_id, "files": original})
            try:
                record["test_output"] = await self.docker(
                    *self.command(record, "test"), timeout=120
                )
                record["state"] = "awaiting_approval"
            except (ValueError, TimeoutError):
                record["state"] = "tests_failed"
                raise
            finally:
                try:
                    await asyncio.shield(self.remove(record))
                except BaseException:
                    record["state"] = "cleanup_failed"
                    raise
                finally:
                    self.save(record)
            return record

    async def remove(self, record):
        # Resolve by our repository label AND exact unique container name.
        ids = await self.docker(
            "ps",
            "-aq",
            "--filter",
            f"label=gar.desktop={self.owner}",
            "--filter",
            f"name=^/gar-desktop-{record['id']}$",
        )
        if ids:
            await self.docker("rm", "-f", *ids.split())

    async def approve(self, session):
        async with self.lock:
            record = self.read(session)
            # Exclusive claim also prevents another CLI/API process reusing this approval.
            claim = self.directory(session) / "claimed"
            if record["state"] != "awaiting_approval" or time.time() > record["expires"]:
                raise ValueError("Desktop approval expired or was already used; prepare again")
            if (
                inventory(Path(record["workspace"])) != record["files"]
                or inventory(self.directory(session) / "source") != record["files"]
            ):
                raise ValueError("Files changed since testing; new tests and approval are required")
            with claim.open("x"):
                pass
            self.audit.append(
                session, "approved", {"entry": record["entry"], "image": record["image"]}
            )
            command = self.command(record, "run")
            command.insert(1, "-d")
            try:
                await self.docker(*command)
            except BaseException:
                record["state"] = "launch_failed"
                self.save(record)
                await asyncio.shield(self.remove(record))
                raise
            record["state"] = "running"
            self.save(record)
            return record

    async def status(self, session):
        record = self.read(session)
        if record["state"] == "running":
            ids = await self.docker(
                "ps",
                "-q",
                "--filter",
                f"label=gar.desktop={self.owner}",
                "--filter",
                f"name=^/gar-desktop-{session}$",
            )
            if not ids:
                existing = await self.docker(
                    "ps",
                    "-aq",
                    "--filter",
                    f"label=gar.desktop={self.owner}",
                    "--filter",
                    f"name=^/gar-desktop-{session}$",
                )
                if existing:
                    record["output"] = await self.docker("logs", "--tail", "30", existing)
                    await self.remove(record)
                record["state"] = "stopped"
                self.save(record)
        return record

    async def stop(self, session):
        async with self.lock:
            record = self.read(session)
            await self.remove(record)
            record["state"] = "stopped"
            self.save(record)
            self.audit.append(session, "stopped", {})
            return record

    async def frame(self, session):
        if (await self.status(session))["state"] != "running":
            raise ValueError("Desktop is not running")
        name = "gar-desktop-" + session
        await self.docker("exec", name, "scrot", "-o", "/tmp/gar-frame.png")
        process = await asyncio.create_subprocess_exec(
            shutil.which("docker"),
            "exec",
            name,
            "cat",
            "/tmp/gar-frame.png",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(5):
                data = await process.stdout.read(4_000_001)
                # read() may return a partial pipe buffer; collect up to the limit.
                while len(data) <= 4_000_000:
                    chunk = await process.stdout.read(min(65536, 4_000_001 - len(data)))
                    if not chunk:
                        break
                    data += chunk
                if len(data) > 4_000_000 or not data.startswith(b"\x89PNG"):
                    raise ValueError("Invalid desktop frame")
                await process.wait()
                return data
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def input(self, session, kind, value="", x=0, y=0):
        if (await self.status(session))["state"] != "running":
            raise ValueError("Desktop is not running")
        if kind == "click" and 0 <= x < 1024 and 0 <= y < 768:
            args = ["mousemove", str(x), str(y), "click", "1"]
        elif kind == "text" and len(value) <= 200:
            args = ["type", "--clearmodifiers", "--", value]
        elif kind == "key" and value in {
            "Return",
            "BackSpace",
            "Tab",
            "Escape",
            "Left",
            "Right",
            "Up",
            "Down",
        }:
            args = ["key", value]
        else:
            raise ValueError("Unsupported desktop input")
        await self.docker("exec", "gar-desktop-" + session, "xdotool", *args)

    async def close(self):
        if not self.root.exists():
            return
        ids = await self.docker("ps", "-aq", "--filter", f"label=gar.desktop={self.owner}")
        if ids:
            await self.docker("rm", "-f", *ids.split())
