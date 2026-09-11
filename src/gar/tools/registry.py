"""Single validated entry point for every tool invocation."""

import asyncio
import stat
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from gar.safety.audit import Audit, redact
from gar.safety.permissions import authorize
from gar.safety.sandbox import Workspace
from gar.tools.base import (
    CommandInput,
    DirectoryInput,
    EmptyInput,
    FileInput,
    PathInput,
    PythonInput,
    Risk,
    ToolFailure,
    ToolResult,
    ToolSpec,
    WriteInput,
)
from gar.tools.process import DockerSandbox

DEFINITIONS = {
    "filesystem.mkdir": (
        DirectoryInput,
        Risk.CAUTION,
        "Create workspace directories, including parents. Use this for folders; "
        "filesystem.write creates files.",
    ),
    "filesystem.list": (PathInput, Risk.SAFE, "List a workspace directory."),
    "filesystem.read": (FileInput, Risk.SAFE, "Read a UTF-8 workspace file (up to 1 MB)."),
    "filesystem.write": (
        WriteInput,
        Risk.CAUTION,
        "Write the COMPLETE file, replacing all previous contents. Not an insertion or "
        "append. Read existing files before updating; preserve their code. Overwrites "
        "require approval.",
    ),
    "terminal.run": (CommandInput, Risk.DANGEROUS, "Run allowlisted Python tests in Docker."),
    "python.run": (PythonInput, Risk.DANGEROUS, "Execute Python inside the task container."),
    "git.status": (EmptyInput, Risk.SAFE, "Inspect Git status in a read-only container."),
    "git.diff": (EmptyInput, Risk.SAFE, "Inspect Git diff with external helpers disabled."),
}
TEST_COMMANDS = (
    ["python", "-m", "pytest"],
    ["python", "-m", "pytest", "-q"],
    ["python", "-m", "unittest", "discover"],
)


class ToolRegistry:
    def __init__(
        self,
        workspace: Path,
        audit: Audit,
        sandbox: DockerSandbox | None = None,
        task_id: str | None = None,
    ):
        self.workspace = Workspace(workspace)
        if audit.path.is_relative_to(self.workspace.root):
            raise ValueError("Audit database must be outside the workspace")
        self.audit = audit
        self.task_id = task_id
        self.sandbox = sandbox or DockerSandbox()
        self.lock = asyncio.Lock()

    @staticmethod
    def specs() -> list[ToolSpec]:
        specs = []
        for name, (schema, risk, description) in DEFINITIONS.items():
            input_schema = schema.model_json_schema()
            if name == "terminal.run":
                input_schema["properties"]["argv"]["enum"] = list(TEST_COMMANDS)
            specs.append(
                ToolSpec(
                    name=name,
                    description=description,
                    risk=risk,
                    input_schema=input_schema,
                )
            )
        return specs

    async def execute(
        self,
        name: str,
        arguments: dict,
        *,
        approved: bool = False,
        timeout: float = 30,
        require_approval: bool = False,
    ) -> ToolResult:
        call_id = uuid4().hex
        # If audit cannot be written, no tool action starts.
        self.audit.append(
            call_id,
            "requested",
            {
                "task_id": self.task_id,
                "actor": "user",
                "tool": name,
                "arguments": arguments,
                "approved_by_user": approved,
            },
        )
        try:
            if not 0 < timeout <= 300:
                raise ToolFailure("invalid_arguments", "Timeout must be between 0 and 300 seconds.")
            if name not in DEFINITIONS:
                raise ToolFailure("unknown_tool", "Unknown tool.")
            schema, risk, _ = DEFINITIONS[name]
            args = schema.model_validate(arguments)
            if name == "terminal.run" and args.argv not in TEST_COMMANDS:
                raise ToolFailure(
                    "command_denied",
                    "This terminal command is unsupported, even with approval. Allowed argv: "
                    + str(TEST_COMMANDS)
                    + ". Create artifacts with filesystem tools; verify with supported tests. "
                    "Tests have a temporary virtual display, but no interactive desktop or "
                    "network. Use the separately approved Isolated desktop for GUI interaction.",
                )
            async with self.lock:
                target = None
                if isinstance(args, PathInput):
                    target = self.workspace.resolve(args.path)
                    if isinstance(args, FileInput) and target.exists() and not target.is_file():
                        raise ToolFailure(
                            "invalid_arguments",
                            "A file path is required, not a directory. No file was changed.",
                        )
                    if isinstance(args, WriteInput) and target.suffix.lower() == ".py":
                        try:
                            compile(args.content, target.name, "exec")
                        except (SyntaxError, ValueError) as exc:
                            # Keep diagnostics local and bounded. The rejected source is
                            # not on disk, so a later filesystem.read cannot recover it.
                            excerpt = ""
                            if isinstance(exc, SyntaxError) and exc.text:
                                line = exc.text.rstrip("\r\n")
                                column = max(0, (exc.offset or 1) - 1)
                                start = max(0, column - 120)
                                excerpt = (
                                    "\nRejected source (not saved):\n"
                                    + line[start : start + 240]
                                    + "\n"
                                    + " " * min(column - start, 240)
                                    + "^"
                                )
                            raise ToolFailure(
                                "invalid_arguments",
                                f"Python syntax invalid at line {getattr(exc, 'lineno', '?')}: "
                                f"{getattr(exc, 'msg', 'invalid source')}. No file was changed. "
                                "Send the COMPLETE valid Python file, not an indented fragment "
                                "or markdown fence." + excerpt,
                            ) from None
                    if name == "filesystem.write" and target.exists():
                        risk = Risk.DANGEROUS
                authorize(Risk.DANGEROUS if require_approval else risk, approved)
                self.audit.append(call_id, "started", {"risk": risk.value})
                output, code, truncated = await self._run(name, args, target, timeout, approved)
            result = ToolResult(
                call_id=call_id,
                tool=name,
                status="ok" if code == 0 else "error",
                output=redact(output),
                exit_code=code,
                truncated=truncated,
                error=None if code == 0 else "command_failed",
            )
        except ToolFailure as exc:
            result = ToolResult(
                call_id=call_id, tool=name, status="error", error=exc.code, output=str(exc)
            )
        except ValidationError:
            result = ToolResult(
                call_id=call_id, tool=name, status="error", error="invalid_arguments"
            )
        except TimeoutError:
            result = ToolResult(
                call_id=call_id,
                tool=name,
                status="error",
                error="timeout",
                output=f"Tool execution exceeded {timeout:g} seconds. Use finite checks that exit; "
                "do not run a persistent server or GUI mainloop as a test. Interactive GUI "
                "sessions use the separately approved isolated desktop after verification.",
            )
        except (NotADirectoryError, FileExistsError):
            result = ToolResult(
                call_id=call_id,
                tool=name,
                status="error",
                error="invalid_arguments",
                output="A path component has the wrong type or already exists. "
                "Inspect with filesystem.list; use filesystem.mkdir for directories and "
                "choose a file path with directory parents. Existing data was preserved.",
            )
        except (OSError, UnicodeError):
            result = ToolResult(call_id=call_id, tool=name, status="error", error="io_error")
        except asyncio.CancelledError:
            self.audit.append(call_id, "cancelled", {})
            raise
        self.audit.append(call_id, "finished", result.model_dump())
        return result

    async def _run(self, name, args, target, timeout, approved):
        if target is not None:
            target = self.workspace.resolve(args.path)
            if (
                target.exists()
                and name not in ("filesystem.list", "filesystem.mkdir")
                and not stat.S_ISREG(target.stat().st_mode)
            ):
                raise ToolFailure("path_denied", "Only regular files are supported.")
        if name == "filesystem.mkdir":
            target.mkdir(parents=True, exist_ok=True)
            self.workspace.resolve(args.path)
            return "Directory ready.", 0, False
        if name == "filesystem.list":
            entries = []
            for item in target.iterdir():
                if len(entries) >= 1000:
                    return "\n".join(entries), 0, True
                try:
                    self.workspace.resolve(item.relative_to(self.workspace.root).as_posix())
                    entries.append(item.name)
                except ToolFailure:
                    continue
            return "\n".join(sorted(entries)), 0, False
        if name == "filesystem.read":
            with target.open("rb") as stream:
                data = stream.read(1_000_001)
            if len(data) > 1_000_000:
                raise ToolFailure("output_limit", "File exceeds 1 MB read limit.")
            return data.decode("utf-8"), 0, False
        if name == "filesystem.write":
            # Parents stay inside the already validated workspace; never follow links.
            target.parent.mkdir(parents=True, exist_ok=True)
            target = self.workspace.resolve(args.path)
            # Exclusive creation prevents an unapproved overwrite race.
            if target.exists():
                authorize(Risk.DANGEROUS, approved)
            mode = "w" if approved else "x"
            with target.open(mode, encoding="utf-8", newline="") as stream:
                stream.write(args.content)
            return "File written.", 0, False
        if name == "python.run":
            argv = ["python", "-B", "-c", args.code]
        elif name == "terminal.run":
            if args.argv not in TEST_COMMANDS:
                raise ToolFailure(
                    "command_denied", "Only supported Python test commands are allowed."
                )
            argv = args.argv
        else:
            argv = [
                "git",
                "-c",
                "safe.directory=/workspace",
                "-c",
                "core.fsmonitor=false",
                "--no-optional-locks",
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
            ]
            if name == "git.diff":
                argv = argv[:5] + ["--no-optional-locks", "diff", "--no-ext-diff", "--no-textconv"]
        code, output, truncated = await self.sandbox.run(
            self.workspace, argv, timeout, name in ("python.run", "terminal.run")
        )
        return output, code, truncated
