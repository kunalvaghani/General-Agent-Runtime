import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_launcher_from_other_directory_and_failure_exit(tmp_path):
    env = {**os.environ, "GAR_DATA_DIR": str(tmp_path / "launcher data")}
    command = ["cmd.exe", "/d", "/c", str(ROOT / "run-gar.bat"), "--no-setup"]
    result = subprocess.run(
        [*command, "version"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GAR 0.1.0" in result.stdout
    assert (tmp_path / "launcher data" / "gar.db").exists()
    help_result = subprocess.run(
        [*command, "plan-help"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "TASK_ID" in help_result.stdout
    tools_result = subprocess.run(
        [*command, "tools-help"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30
    )
    assert tools_result.returncode == 0, tools_result.stderr
    assert "INPUT_FILE" in tools_result.stdout
    result = subprocess.run(
        [*command, "unknown-command"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
