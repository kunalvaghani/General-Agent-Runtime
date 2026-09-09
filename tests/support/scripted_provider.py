"""Deterministic model only; integration tests use the real runtime and Docker tools."""

import json

from gar.models.base import Generation, ModelProfile
from gar.models.registry import ModelRegistry


class ScriptedProvider:
    provider = "ollama"

    async def discover(self):
        return [ModelProfile(id="acceptance-model", provider=self.provider, local=True)]

    async def generate(self, model, messages, **kwargs):
        request = json.loads(messages[-1].content)
        goal = request["goal"]
        scenario = goal.lower()
        if "malformed-plan" in scenario or ("malformed-decision" in scenario and "step" in request):
            return Generation(model=model, content="{not valid structured output")
        if "step" not in request:
            ids = ["module", "tests", "verify"]
            if "repair" in scenario:
                ids = ["inspect", "repair", "verify"]
            if "danger" in scenario or "cancel active" in scenario:
                ids = ["process"]
            result = {
                "objective": goal,
                "completion_criteria": ["Module and tests exist; pytest passes"],
                "steps": [
                    {
                        "id": step,
                        "description": f"Run {step}",
                        "dependencies": ids[index - 1 : index],
                        "expected_output": f"Evidence for {step}",
                    }
                    for index, step in enumerate(ids)
                ],
            }
        else:
            step = request["step"]["id"]
            if step == "process":
                code = "from pathlib import Path; Path('danger.txt').write_text('ran')"
                if "cancel active" in scenario:
                    code = (
                        "import os,time; from pathlib import Path; "
                        "Path('started.txt').write_text(os.environ['HOSTNAME']); "
                        "time.sleep(60); Path('finished.txt').write_text('unexpected')"
                    )
                tool, args = "python.run", {"code": code}
            elif step == "inspect":
                if request["step"]["attempts"] == 1:
                    tool, args = "terminal.run", {"argv": ["python", "-m", "pytest", "-q"]}
                else:
                    tool, args = "filesystem.read", {"path": "addition.py"}
            elif step in ("module", "repair"):
                tool, args = (
                    "filesystem.write",
                    {"path": "addition.py", "content": "def add(a, b):\n    return a + b\n"},
                )
            elif step == "tests":
                tool, args = (
                    "filesystem.write",
                    {
                        "path": "test_addition.py",
                        "content": (
                            "from addition import add\ndef test_add():\n    assert add(2, 3) == 5\n"
                        ),
                    },
                )
            else:
                tool, args = "terminal.run", {"argv": ["python", "-m", "pytest", "-q"]}
            result = {
                "action": "tool",
                "reason": f"Produce evidence for {step}",
                "tool_name": tool,
                "arguments": args,
            }
        return Generation(model=model, content=json.dumps(result))


def registry(_settings):
    result = ModelRegistry()
    result.register(ScriptedProvider())
    return result
