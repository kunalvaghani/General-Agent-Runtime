"""Trusted test-container entry point; never execute on the host."""

import os
import subprocess
import sys
import time
from pathlib import Path

Path("/tmp/.X11-unix").mkdir(exist_ok=True)
os.environ["DISPLAY"] = ":99"
display = subprocess.Popen(
    ["Xvfb", ":99", "-screen", "0", "1024x768x24", "-nolisten", "tcp", "-noreset"]
)
try:
    for _ in range(100):
        if display.poll() is not None:
            raise SystemExit("Virtual display exited during startup")
        if (
            subprocess.run(
                ["xdpyinfo"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode
            == 0
        ):
            break
        time.sleep(0.05)
    else:
        raise SystemExit("Virtual display did not become ready")
    raise SystemExit(subprocess.call(sys.argv[1:]))
finally:
    display.terminate()
    try:
        display.wait(timeout=2)
    except subprocess.TimeoutExpired:
        display.kill()
        display.wait()
