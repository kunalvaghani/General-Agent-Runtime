import asyncio

import pytest

from gar.safety.audit import Audit
from gar.tools.registry import ToolRegistry


@pytest.fixture
def runtime(request, tmp_path):
    if not request.config.getoption("--docker"):
        pytest.skip("Run with --docker after sandbox-setup")
    root = tmp_path / "workspace"
    root.mkdir()
    root.chmod(0o777)
    return ToolRegistry(root, Audit(tmp_path / "audit.db"))


def execute(runtime, name, args, **kwargs):
    return asyncio.run(runtime.execute(name, args, **kwargs))


def test_real_python_and_terminal(runtime):
    code = (
        "from pathlib import Path; "
        "Path('test_add.py').write_text('def test_add(): assert 2+2 == 4')"
    )
    result = execute(runtime, "python.run", {"code": code}, approved=True)
    assert result.status == "ok", result
    result = execute(
        runtime, "terminal.run", {"argv": ["python", "-m", "pytest", "-q"]}, approved=True
    )
    assert result.status == "ok" and "1 passed" in result.output, result


def test_real_network_and_host_isolation(runtime):
    code = """import socket
from pathlib import Path
try:
    assert not Path('/root/.ssh').exists()
except PermissionError:
    pass
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
except OSError:
    print('NETWORK_BLOCKED')
else:
    raise AssertionError('network enabled')
try:
    Path('/outside_workspace').write_text('escape')
except OSError:
    print('ROOT_READ_ONLY')
else:
    raise AssertionError('root writable')
"""
    result = execute(runtime, "python.run", {"code": code}, approved=True)
    assert result.status == "ok", result
    assert "NETWORK_BLOCKED" in result.output and "ROOT_READ_ONLY" in result.output


def test_real_timeout(runtime):
    result = execute(
        runtime, "python.run", {"code": "import time; time.sleep(60)"}, approved=True, timeout=2
    )
    assert result.error == "timeout", result


def test_real_git(runtime):
    code = """import subprocess
from pathlib import Path
subprocess.run(['git', 'init'], check=True)
Path('a.txt').write_text('first')
subprocess.run(['git', '-c', 'safe.directory=/workspace', 'add', 'a.txt'], check=True)
Path('a.txt').write_text('second')
"""
    result = execute(runtime, "python.run", {"code": code}, approved=True)
    assert result.status == "ok", result
    result = execute(runtime, "git.status", {})
    assert result.status == "ok" and "a.txt" in result.output, result
    result = execute(runtime, "git.diff", {})
    assert result.status == "ok" and "+second" in result.output, result
