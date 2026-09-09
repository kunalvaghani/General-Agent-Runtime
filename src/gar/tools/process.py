"""Bounded subprocess output and a fail-closed Docker execution backend."""

import asyncio
import os
import shutil
from uuid import uuid4

from gar.safety.sandbox import Workspace
from gar.tools.base import ToolFailure

IMAGE = "gar-tools:stage4"
OUTPUT_LIMIT = 65536


async def capture(argv: list[str], timeout: float) -> tuple[int, str, bool]:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    output = bytearray()
    truncated = False

    async def drain():
        nonlocal truncated
        while chunk := await process.stdout.read(8192):
            remaining = OUTPUT_LIMIT - len(output)
            output.extend(chunk[:remaining])
            truncated |= len(chunk) > remaining

    reader = asyncio.create_task(drain())
    try:
        async with asyncio.timeout(timeout):
            await process.wait()
            await reader
        return process.returncode, output.decode("utf-8", errors="replace"), truncated
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if not reader.done():
            reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)


class DockerSandbox:
    async def run(
        self, workspace: Workspace, argv: list[str], timeout: float, writable: bool
    ) -> tuple[int, str, bool]:
        workspace.validate_mount()
        docker = shutil.which("docker")
        if not docker:
            raise ToolFailure("sandbox_unavailable", "Docker is required for process tools.")
        name = "gar-tool-" + uuid4().hex
        mount = f"type=bind,source={workspace.root},target=/workspace"
        if "," in str(workspace.root):
            raise ToolFailure("path_denied", "Container mount paths cannot contain commas.")
        if not writable:
            mount += ",readonly"
        command = [
            docker,
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            *(
                ["--label", f"gar.launch={os.environ['GAR_LAUNCH_ID']}"]
                if os.environ.get("GAR_LAUNCH_ID")
                else []
            ),
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=256m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=32m",
            "--mount",
            mount,
            "--workdir=/workspace",
            "--env=HOME=/tmp",
            IMAGE,
            *argv,
        ]
        launch_failed = False
        try:
            result = await capture(command, timeout)
            if result[0] == 125:
                launch_failed = True
                raise ToolFailure(
                    "sandbox_unavailable", "Docker/image unavailable; run sandbox-setup."
                )
            return result
        finally:
            # Killing the client alone does not stop its container or descendants.
            try:
                cleanup = await asyncio.shield(capture([docker, "rm", "-f", name], 10))
                if cleanup[0] and not launch_failed and "No such container" not in cleanup[1]:
                    raise ToolFailure("cleanup_failed", "Could not confirm container cleanup.")
            except (OSError, TimeoutError):
                raise ToolFailure(
                    "cleanup_failed", "Could not confirm container cleanup."
                ) from None
