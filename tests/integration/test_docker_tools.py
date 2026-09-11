import asyncio
from unittest.mock import AsyncMock

import pytest

from gar.safety.sandbox import Workspace
from gar.tools.process import DockerSandbox


def test_container_flags_and_cleanup(monkeypatch, tmp_path):
    capture = AsyncMock(side_effect=[(0, "ok", False), (0, "removed", False)])
    monkeypatch.setattr("gar.tools.process.capture", capture)
    monkeypatch.setattr("gar.tools.process.shutil.which", lambda name: "docker")
    asyncio.run(DockerSandbox().run(Workspace(tmp_path), ["python", "-c", "pass"], 3, True))
    argv = capture.call_args_list[0].args[0]
    for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--pull=never"):
        assert flag in argv
    assert capture.call_args_list[1].args[0][1:3] == ["rm", "-f"]


def test_timeout_cleanup(monkeypatch, tmp_path):
    capture = AsyncMock(side_effect=[TimeoutError(), (0, "removed", False)])
    monkeypatch.setattr("gar.tools.process.capture", capture)
    monkeypatch.setattr("gar.tools.process.shutil.which", lambda name: "docker")
    with pytest.raises(TimeoutError):
        asyncio.run(DockerSandbox().run(Workspace(tmp_path), ["python", "-c", "pass"], 1, True))
    assert capture.await_count == 2


def test_headless_image_can_test_tk_widgets_in_virtual_display(tmp_path, request):
    if not request.config.getoption("--docker"):
        pytest.skip("Requires Docker")
    code, output, _ = asyncio.run(
        DockerSandbox().run(
            Workspace(tmp_path),
            [
                "python",
                "-c",
                "import tkinter; root=tkinter.Tk(); root.withdraw(); "
                "root.update(); root.destroy(); print(tkinter.TkVersion)",
            ],
            20,
            False,
        )
    )
    assert code == 0, output
    assert "8.6" in output
