import json
import socket
from unittest.mock import MagicMock, Mock

import httpx
import pytest

from gar.launcher import available_port, frontend_ready, main, open_frontend, preferred_ui_port


@pytest.mark.parametrize("configured,expected", [(3000, 4317), (4317, 4317), (5321, 5321)])
def test_legacy_browser_origin_is_avoided_and_custom_port_preserved(configured, expected):
    assert preferred_ui_port(configured) == expected


def test_occupied_port_is_skipped_without_closing_owner():
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        owner.listen()
        port = owner.getsockname()[1]
        selected = available_port(port)
        assert selected != port
        assert owner.fileno() != -1


def test_wrong_app_or_backend_instance_cannot_open_browser():
    client = Mock()
    client.get.return_value = httpx.Response(200, json={"service": "gar"})
    assert not frontend_ready(client, "http://127.0.0.1:3000", "ours")
    health = httpx.Response(200, json={"service": "gar"}, headers={"X-GAR-Launch-ID": "ours"})
    client.get.side_effect = [health, httpx.Response(200, text="<title>Open WebUI</title>")]
    assert not frontend_ready(client, "http://127.0.0.1:3000", "ours")
    client.get.side_effect = [health, httpx.Response(200, text='<html data-gar-app="runtime">')]
    assert frontend_ready(client, "http://127.0.0.1:3000", "ours")


def test_browser_opens_by_default_and_can_be_disabled(monkeypatch):
    browser = Mock(return_value=True)
    monkeypatch.setattr("gar.launcher.webbrowser.open_new_tab", browser)
    open_frontend("http://127.0.0.1:3000")
    browser.assert_called_once_with("http://127.0.0.1:3000")
    monkeypatch.setenv("GAR_OPEN_BROWSER", "0")
    open_frontend("http://127.0.0.1:3000")
    browser.assert_called_once()


def test_browser_failure_prints_manual_address(monkeypatch, capsys):
    monkeypatch.setattr("gar.launcher.webbrowser.open_new_tab", Mock(side_effect=OSError))
    open_frontend("http://127.0.0.1:3000")
    assert "Open this address in your browser: http://127.0.0.1:3000" in capsys.readouterr().out


@pytest.mark.parametrize("mode,count", [("dev", 2), ("serve", 1), ("web", 1)])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_tracked_launch_modes_honor_stop_and_cleanup_result(
    tmp_path, monkeypatch, mode, count, cleanup_fails
):
    manifest = tmp_path / "launch.json"
    manifest.write_text(json.dumps({"children": []}))
    manifest.with_suffix(".stop").touch()
    monkeypatch.setattr("gar.launcher.save_launch", Mock(return_value=manifest))
    monkeypatch.setattr("gar.launcher.identity", Mock(return_value={"pid": 123, "created": 1}))
    monkeypatch.setattr("gar.launcher.available_port", lambda preferred, *args, **kwargs: preferred)
    monkeypatch.setattr("gar.launcher.shutil.which", Mock(return_value="npm.cmd"))
    process = Mock(pid=123)
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr("gar.launcher.subprocess.Popen", spawn)
    monkeypatch.setattr("gar.launcher.httpx.Client", MagicMock())
    cleanup = Mock(side_effect=RuntimeError("cleanup failed") if cleanup_fails else None)
    monkeypatch.setattr("gar.launcher.cleanup_launch", cleanup)
    assert main(mode) == (1 if cleanup_fails else 0)
    assert spawn.call_count == count
    cleanup.assert_called_once()
    assert manifest.exists() == cleanup_fails
    for call in spawn.call_args_list:
        assert len(call.kwargs["env"]["GAR_LAUNCH_ID"]) == 32
        if mode != "serve":
            assert call.kwargs["env"]["GAR_WEB_ORIGIN"] == "http://127.0.0.1:4317"
    if mode == "web":
        process.send_signal.assert_not_called()
    else:
        process.send_signal.assert_called_once()
