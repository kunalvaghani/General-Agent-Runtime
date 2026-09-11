"""Trusted container entry point; never runs on the host."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

Path("/tmp/home").mkdir(exist_ok=True)
Path("/tmp/.X11-unix").mkdir(exist_ok=True)
shutil.copytree("/source", "/tmp/workspace")
os.chdir("/tmp/workspace")
x = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24", "-nolisten", "tcp", "-noreset"])
for _ in range(100):
    if (
        subprocess.run(
            ["xdpyinfo"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        break
    time.sleep(0.05)
else:
    raise SystemExit("Desktop display did not start")
if sys.argv[1] == "test":
    raise SystemExit(subprocess.call(["python3", "-m", "pytest", "-q"]))
raise SystemExit(subprocess.call(["python3", "-B", sys.argv[2]]))
