import asyncio
import os
import sqlite3
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from gar.safety.audit import Audit, redact
from gar.safety.permissions import authorize
from gar.tools.base import Risk, ToolFailure
from gar.tools.process import capture
from gar.tools.registry import ToolRegistry


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    sandbox = AsyncMock()
    sandbox.run.return_value = (0, "passed", False)
    return ToolRegistry(root, Audit(tmp_path / "audit.db"), sandbox)


def call(runtime, name, args, **kwargs):
    return asyncio.run(runtime.execute(name, args, **kwargs))


def test_write_read_list_and_approval(runtime):
    args = {"path": "a.txt", "content": "hello"}
    assert call(runtime, "filesystem.write", args).status == "ok"
    assert call(runtime, "filesystem.read", {"path": "a.txt"}).output == "hello"
    assert call(runtime, "filesystem.list", {}).output == "a.txt"
    assert call(runtime, "filesystem.write", args).error == "approval_required"
    assert call(runtime, "filesystem.write", args, approved=True).status == "ok"


def test_docker_workspace_alias_stays_in_task_folder(runtime):
    args = {"path": "/workspace/calculator.py", "content": "print(2 + 2)"}
    assert call(runtime, "filesystem.write", args).status == "ok"
    assert (runtime.workspace.root / "calculator.py").read_text() == args["content"]
    assert call(runtime, "filesystem.read", {"path": args["path"]}).output == args["content"]
    assert call(runtime, "filesystem.list", {"path": "/workspace"}).output == "calculator.py"
    assert call(runtime, "filesystem.write", args).error == "approval_required"


def test_nested_source_creation_preserves_workspace_boundary(runtime):
    args = {"path": "tests/unit/test_app.py", "content": "def test_add(): assert 2+2 == 4"}
    assert call(runtime, "filesystem.write", args).status == "ok"
    assert (runtime.workspace.root / args["path"]).read_text() == args["content"]
    assert (
        call(runtime, "filesystem.write", {**args, "path": "../outside/new.py"}).error
        == "path_denied"
    )


def test_invalid_python_fragment_does_not_replace_existing_file(runtime):
    target = runtime.workspace.root / "app.py"
    target.write_text("def add(a,b): return a+b\n")
    result = call(
        runtime,
        "filesystem.write",
        {"path": "app.py", "content": "    def method(self):\n        pass\n"},
        approved=True,
    )
    assert result.error == "invalid_arguments"
    assert "COMPLETE" in result.output
    assert target.read_text() == "def add(a,b): return a+b\n"


def test_rejected_source_diagnostic_points_to_missing_quote(runtime):
    source = "buttons = [\n    '1', '2', '-,\n]\n"
    result = call(runtime, "filesystem.write", {"path": "app.py", "content": source})
    assert result.error == "invalid_arguments"
    assert "line 2" in result.output
    assert "'1', '2', '-," in result.output
    excerpt, pointer = result.output.split("Rejected source (not saved):\n")[1].splitlines()
    assert excerpt[pointer.index("^")] == "'"
    assert not (runtime.workspace.root / "app.py").exists()


def test_rejected_source_diagnostic_is_bounded(runtime):
    source = "value = " + " " * 10000 + "'unterminated"
    result = call(runtime, "filesystem.write", {"path": "app.py", "content": source})
    assert result.error == "invalid_arguments"
    assert "'unterminated" in result.output
    assert len(result.output) < 800
    assert not (runtime.workspace.root / "app.py").exists()


def test_file_target_validation_precedes_approval(runtime):
    assert call(runtime, "filesystem.write", {"content": "x"}).error == "invalid_arguments"
    assert (
        call(runtime, "filesystem.write", {"path": ".", "content": "x"}).error
        == "invalid_arguments"
    )
    assert call(runtime, "filesystem.read", {}).error == "invalid_arguments"


def test_directory_creation_and_file_conflict_preserve_data(runtime):
    assert call(runtime, "filesystem.mkdir", {"path": "project/tests"}).status == "ok"
    assert (runtime.workspace.root / "project/tests").is_dir()
    assert call(runtime, "filesystem.mkdir", {"path": "../escape"}).error == "path_denied"
    (runtime.workspace.root / "file").write_text("keep")
    result = call(runtime, "filesystem.write", {"path": "file/test.py", "content": "pass"})
    assert result.error == "invalid_arguments"
    assert (runtime.workspace.root / "file").read_text() == "keep"


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/etc/passwd",
        "/workspace/../secret",
        "/workspace//etc/passwd",
        "/workspace/C:/Windows/a",
        "/workspace/.env",
        "/workspace/.git/config",
        "/workspace2/secret",
        "/workspace/..\\secret",
        "C:/Windows/a",
        "C:relative",
        "a:secret",
        "NUL",
        "COM1.txt",
        "file.",
        "file ",
        ".env",
        ".env.local",
        ".ssh/key",
        ".git/config",
        "a/../../x",
        "..\\secret",
        "\\\\server\\share",
        "a\x00b",
    ],
)
def test_denied_paths(runtime, path):
    assert call(runtime, "filesystem.read", {"path": path}).error == "path_denied"


def test_hardlink_rejected(runtime, tmp_path):
    external = tmp_path / "outside.txt"
    external.write_text("private")
    os.link(external, runtime.workspace.root / "link.txt")
    assert call(runtime, "filesystem.read", {"path": "link.txt"}).error == "path_denied"


def test_directory_link_rejected(runtime, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("secret")
    link = runtime.workspace.root / "linked"
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(outside)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    assert call(runtime, "filesystem.read", {"path": "linked/secret"}).error == "path_denied"
    assert (
        call(runtime, "filesystem.read", {"path": "/workspace/linked/secret"}).error
        == "path_denied"
    )


def test_secret_mount_rejected(runtime):
    (runtime.workspace.root / ".env").write_text("secret")
    with pytest.raises(ToolFailure):
        runtime.workspace.validate_mount()


def test_schema_and_missing_file(runtime):
    assert call(runtime, "delete", {}).error == "unknown_tool"
    assert (
        call(runtime, "filesystem.write", {"path": "x", "content": 7}).error == "invalid_arguments"
    )
    assert (
        call(runtime, "python.run", {"code": "pass", "approved": True}).error == "invalid_arguments"
    )
    assert call(runtime, "filesystem.read", {"path": "missing"}).error == "io_error"


def test_code_approval_and_command_allowlist(runtime):
    assert call(runtime, "python.run", {"code": "print(1)"}).error == "approval_required"
    runtime.sandbox.run.assert_not_called()
    result = call(runtime, "terminal.run", {"argv": ["cmd", "/c", "echo unsafe"]}, approved=True)
    assert result.error == "command_denied"
    assert (
        call(runtime, "terminal.run", {"argv": ["python", "-m", "pytest"]}, approved=True).status
        == "ok"
    )


def test_process_errors(runtime):
    runtime.sandbox.run.return_value = (1, "test failed", False)
    assert call(runtime, "python.run", {"code": "pass"}, approved=True).error == "command_failed"
    runtime.sandbox.run.side_effect = TimeoutError
    result = call(runtime, "python.run", {"code": "pass"}, approved=True)
    assert result.error == "timeout"
    assert "30 seconds" in result.output and "mainloop" in result.output
    runtime.sandbox.run.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        call(runtime, "python.run", {"code": "pass"}, approved=True)


def test_audit_and_fail_closed(runtime, monkeypatch):
    result = call(runtime, "filesystem.write", {"path": "a", "content": "token=private-value"})
    with sqlite3.connect(runtime.audit.path) as conn:
        rows = conn.execute("SELECT call_id, phase, data FROM tool_audit ORDER BY id").fetchall()
    assert [r[1] for r in rows] == ["requested", "started", "finished"]
    assert all(r[0] == result.call_id for r in rows)
    assert "private-value" not in str(rows)

    def fail(*args):
        raise OSError("audit unavailable")

    monkeypatch.setattr(runtime.audit, "append", fail)
    with pytest.raises(OSError):
        call(runtime, "filesystem.write", {"path": "new", "content": "data"})
    assert not (runtime.workspace.root / "new").exists()


def test_prohibited_never_approved():
    with pytest.raises(ToolFailure):
        authorize(Risk.PROHIBITED, True)


def test_quoted_secret_redaction():
    assert "private-value" not in redact('{"token": "private-value"}')


def test_real_subprocess_bounds():
    result = asyncio.run(capture([sys.executable, "-c", "print('x'*100000)"], 5))
    assert result[0] == 0 and len(result[1]) == 65536 and result[2]
    with pytest.raises(TimeoutError):
        asyncio.run(capture([sys.executable, "-c", "import time; time.sleep(10)"], 0.1))
