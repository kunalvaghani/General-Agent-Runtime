import json
import os
from unittest.mock import Mock

import pytest

from gar.lifecycle import (
    ROOT,
    clean_containers,
    cleanup_launch,
    identity,
    owned_process,
    save_launch,
    stop_all,
)


def test_reused_pid_is_never_treated_as_owned():
    record = identity(os.getpid())
    assert owned_process(record) is not None
    record["created"] -= 1
    assert owned_process(record) is None


def test_container_cleanup_filters_exact_launch(monkeypatch):
    monkeypatch.setattr("gar.lifecycle.shutil.which", lambda _: "docker")
    run = Mock(side_effect=[Mock(returncode=0, stdout="owned-id\n"), Mock(returncode=0)])
    monkeypatch.setattr("gar.lifecycle.subprocess.run", run)
    instance = "a" * 32
    clean_containers(instance)
    assert run.call_args_list[0].args[0][-1] == f"label=gar.launch={instance}"
    assert run.call_args_list[1].args[0] == ["docker", "rm", "-f", "owned-id"]


def test_stop_with_no_launches_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("GAR_RUN_DIR", str(tmp_path))
    assert stop_all() == 0
    assert stop_all() == 0


def test_tracking_does_not_resolve_exited_child_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("GAR_RUN_DIR", str(tmp_path))
    child = Mock(pid=987654321)
    child.poll.return_value = 0
    path = save_launch("a" * 32, [child])
    assert json.loads(path.read_text())["children"] == []


def test_cleanup_attempts_other_children_and_containers_after_failure(monkeypatch):
    stop = Mock(side_effect=[RuntimeError("access denied"), None])
    containers = Mock()
    monkeypatch.setattr("gar.lifecycle.stop_tree", stop)
    monkeypatch.setattr("gar.lifecycle.clean_containers", containers)
    with pytest.raises(RuntimeError, match="access denied"):
        cleanup_launch("a" * 32, [{"pid": 1}, {"pid": 2}])
    assert stop.call_count == 2
    containers.assert_called_once_with("a" * 32)


@pytest.mark.parametrize("docker", [None, "docker"])
def test_unavailable_docker_reports_incomplete_cleanup(monkeypatch, docker):
    monkeypatch.setattr("gar.lifecycle.shutil.which", lambda _: docker)
    monkeypatch.setattr("gar.lifecycle.subprocess.run", Mock(return_value=Mock(returncode=1)))
    with pytest.raises(RuntimeError, match="cleanup"):
        clean_containers("a" * 32)


def test_foreign_repository_manifest_is_never_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("GAR_RUN_DIR", str(tmp_path))
    path = tmp_path / ("a" * 32 + ".json")
    path.write_text(json.dumps({"repository": "another repository", "instance": "a" * 32}))
    cleanup = Mock()
    monkeypatch.setattr("gar.lifecycle.cleanup_launch", cleanup)
    assert stop_all() == 1
    cleanup.assert_not_called()
    assert path.exists()
    assert not path.with_suffix(".stop").exists()


def test_failed_cleanup_keeps_manifest_for_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("GAR_RUN_DIR", str(tmp_path))
    path = tmp_path / ("a" * 32 + ".json")
    record = {"repository": str(ROOT), "instance": "a" * 32, "launcher": {}, "children": []}
    path.write_text(json.dumps(record))
    monkeypatch.setattr("gar.lifecycle.owned_process", lambda _: None)
    cleanup = Mock(side_effect=[RuntimeError("retry cleanup"), None])
    monkeypatch.setattr("gar.lifecycle.cleanup_launch", cleanup)
    assert stop_all() == 1
    assert path.exists()
    assert stop_all() == 0
    assert not path.exists()
