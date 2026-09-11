import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from gar.config import Settings
from gar.desktop import DesktopManager, inventory


def prepared(tmp_path):
    settings = Settings(data_dir=tmp_path / "data")
    task_id = "a" * 32
    source = settings.data_dir / "workspaces" / task_id
    source.mkdir(parents=True)
    (source / "app.py").write_text(
        "import tkinter as tk\n"
        "root=tk.Tk()\nroot.title('GAR isolated test')\nroot.geometry('300x200+10+10')\n"
        "def write():\n    open('session-only.txt','w').write('ok')\n"
        "tk.Button(root,text='Write session file',command=write).pack()\n"
        "root.mainloop()\n"
    )
    (source / "test_app.py").write_text("def test_math(): assert 2+2 == 4\n")
    task = SimpleNamespace(
        id=task_id,
        workspace=str(source),
        status="COMPLETED",
        metadata={"verification": {"passed": True}},
    )
    manager = DesktopManager(Mock(get=Mock(return_value=task)), settings)
    return manager, task, source


def fake_docker(manager):
    async def docker(*args, **kwargs):
        if args[:2] == ("image", "inspect"):
            return "sha256:" + "a" * 64
        if args[0] == "run":
            return "1 passed"
        return ""

    manager.docker = AsyncMock(side_effect=docker)


def test_task_id_is_not_a_desktop_session(tmp_path):
    manager, task, _ = prepared(tmp_path)
    with pytest.raises(ValueError, match="Desktop session not found") as error:
        manager.read(task.id)
    assert "request.json" not in str(error.value)
    assert str(tmp_path) not in str(error.value)


def test_desktop_requires_verification_and_rejects_changed_snapshot(tmp_path):
    manager, task, source = prepared(tmp_path)
    fake_docker(manager)
    task.status = "BLOCKED"
    with pytest.raises(ValueError, match="verification"):
        asyncio.run(manager.prepare(task.id, "app.py"))
    manager.docker.assert_not_called()
    task.status = "COMPLETED"
    record = asyncio.run(manager.prepare(task.id, "app.py"))
    (source / "app.py").write_text("changed")
    with pytest.raises(ValueError, match="Files changed"):
        asyncio.run(manager.approve(record["id"]))
    assert not (manager.directory(record["id"]) / "claimed").exists()


def test_desktop_approval_is_single_use_and_limits_are_fixed(tmp_path):
    manager, task, _ = prepared(tmp_path)
    fake_docker(manager)
    record = asyncio.run(manager.prepare(task.id, "app.py"))
    assert record["state"] == "awaiting_approval"
    command = manager.command(record, "run")
    assert "--network=none" in command and "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--user=65534:65534" in command
    assert command[command.index("--mount") + 1].endswith("target=/source,readonly")
    assert command[-3].startswith("sha256:")
    asyncio.run(manager.approve(record["id"]))
    with pytest.raises(ValueError, match="already used"):
        asyncio.run(manager.approve(record["id"]))


def test_failed_tests_never_create_launch_approval(tmp_path):
    manager, task, _ = prepared(tmp_path)
    fake_docker(manager)
    previous = manager.docker.side_effect

    async def fail(*args, **kwargs):
        if args[0] == "run":
            raise ValueError("1 failed")
        return await previous(*args, **kwargs)

    manager.docker.side_effect = fail
    with pytest.raises(ValueError, match="1 failed"):
        asyncio.run(manager.prepare(task.id, "app.py"))
    manifest = next(manager.root.glob("*/request.json"))
    assert json.loads(manifest.read_text())["state"] == "tests_failed"


def test_expired_or_modified_frozen_copy_needs_new_approval(tmp_path):
    manager, task, _ = prepared(tmp_path)
    fake_docker(manager)
    record = asyncio.run(manager.prepare(task.id, "app.py"))
    record["expires"] = 0
    manager.save(record)
    with pytest.raises(ValueError, match="expired"):
        asyncio.run(manager.approve(record["id"]))
    record = asyncio.run(manager.prepare(task.id, "app.py"))
    (manager.directory(record["id"]) / "source" / "app.py").write_text("changed")
    with pytest.raises(ValueError, match="Files changed"):
        asyncio.run(manager.approve(record["id"]))


def test_real_desktop_test_approve_frame_input_stop(tmp_path, request):
    if not request.config.getoption("--docker"):
        pytest.skip("Requires gar-desktop:1 and --docker")
    manager, task, source = prepared(tmp_path)
    before = inventory(source)

    async def scenario():
        record = await manager.prepare(task.id, "app.py")
        assert "passed" in record["test_output"]
        assert (
            await manager.docker("ps", "-q", "--filter", f"label=gar.desktop={manager.owner}") == ""
        )
        await manager.approve(record["id"])
        try:
            for _ in range(30):
                try:
                    await manager.docker(
                        "exec",
                        "gar-desktop-" + record["id"],
                        "xdotool",
                        "search",
                        "--onlyvisible",
                        "--name",
                        "GAR isolated test",
                    )
                    frame = await manager.frame(record["id"])
                    break
                except ValueError:
                    await asyncio.sleep(0.2)
            else:
                pytest.fail(await manager.docker("logs", "gar-desktop-" + record["id"]))
            assert frame.startswith(b"\x89PNG")
            await manager.input(record["id"], "click", x=160, y=25)
            assert (
                await manager.docker(
                    "exec", "gar-desktop-" + record["id"], "cat", "/tmp/workspace/session-only.txt"
                )
                == "ok"
            )
            # Inspect the actual isolation configuration, not only our command construction.
            config = json.loads(await manager.docker("inspect", "gar-desktop-" + record["id"]))[0]
            assert config["HostConfig"]["NetworkMode"] == "none"
            assert config["HostConfig"]["ReadonlyRootfs"]
            assert len(config["Mounts"]) == 1 and not config["Mounts"][0]["RW"]
            assert config["Mounts"][0]["Destination"] == "/source"
            assert inventory(source) == before
        finally:
            await manager.stop(record["id"])
        assert (await manager.status(record["id"]))["state"] == "stopped"
        assert (
            await manager.docker("ps", "-aq", "--filter", f"label=gar.desktop={manager.owner}")
            == ""
        )

    asyncio.run(scenario())
