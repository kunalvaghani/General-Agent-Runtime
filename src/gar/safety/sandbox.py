"""Workspace path checks for a single-user local runtime, not an OS sandbox."""

import os
import stat
from pathlib import Path, PureWindowsPath

from gar.tools.base import ToolFailure

DENIED = {
    ".ssh",
    ".aws",
    ".azure",
    ".config",
    ".git",
    ".env",
    ".gar",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "cookies",
    "login data",
}


def reject_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ToolFailure("path_denied", "Links and Windows reparse points are not allowed.")
    if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
        raise ToolFailure("path_denied", "Hard-linked files are not allowed.")


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))
        for path in (*reversed(self.root.parents), self.root):
            reject_link(path)
            if path.name.lower() in DENIED:
                raise ToolFailure("path_denied", "Workspace is inside a denied directory.")
        if not self.root.is_dir():
            raise ToolFailure("path_denied", "Workspace must be an existing directory.")

    def resolve(self, value: str) -> Path:
        # Docker's mount is a virtual alias for this task only, never a host path.
        if value == "/workspace":
            value = "."
        elif value.startswith("/workspace/"):
            value = value[len("/workspace/") :]
        windows = PureWindowsPath(value)
        if windows.drive or windows.root or Path(value).is_absolute() or "\\" in value:
            raise ToolFailure("path_denied", "Use a workspace-relative path with forward slashes.")
        parts = value.split("/")
        for part in parts:
            lower = part.lower()
            if (
                part == ".."
                or ":" in part
                or "\x00" in part
                or (part not in ("", ".") and part.rstrip(" .") != part)
                or lower in DENIED
                or lower.startswith(".env.")
                or PureWindowsPath(part).is_reserved()
            ):
                raise ToolFailure("path_denied", "Path contains a denied component.")
        target = self.root.joinpath(*parts)
        for path in (*reversed(target.parents), target):
            reject_link(path)
        resolved = target.resolve()
        if not resolved.is_relative_to(self.root):
            raise ToolFailure("path_denied", "Path is outside the workspace.")
        return resolved

    def validate_mount(self) -> None:
        """Reject secrets and links anywhere before exposing a tree to a container."""
        count = 0

        def fail_walk(error):
            raise ToolFailure("path_denied", "Cannot inspect the complete workspace.")

        for base, dirs, files in os.walk(self.root, followlinks=False, onerror=fail_walk):
            for name in [*dirs, *files]:
                count += 1
                if count > 10000:
                    raise ToolFailure("path_denied", "Workspace exceeds mount inspection limit.")
                relative = (Path(base) / name).relative_to(self.root).as_posix()
                # Git metadata is needed by inspection, but must never be a link or gitfile.
                if relative == ".git" or relative.startswith(".git/"):
                    target = self.root / relative
                    reject_link(target)
                    if relative == ".git" and not target.is_dir():
                        raise ToolFailure(
                            "path_denied", "External Git directories are not allowed."
                        )
                else:
                    self.resolve(relative)
