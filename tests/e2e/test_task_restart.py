import json
import os
import subprocess
import sys


def test_task_is_readable_in_new_process(tmp_path):
    env = {**os.environ, "GAR_DATA_DIR": str(tmp_path / "persistent state")}

    def invoke(*arguments):
        result = subprocess.run(
            [sys.executable, "-m", "gar", *arguments],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    created = invoke("task-create", "Keep this goal across restart", "test-model")
    inspected = invoke("task", created["id"])
    assert inspected["task"] == created
    assert inspected["events"][0]["event"] == "task.created"
