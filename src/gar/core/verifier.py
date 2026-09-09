"""Evidence-based verification for bounded software-development tasks."""

from pydantic import BaseModel

from gar.core.state import TaskStatus


class Verification(BaseModel):
    passed: bool
    evidence: list[str]
    issues: list[str]


class Verifier:
    async def verify(self, repo, task_id, tools):
        task = repo.get(task_id)
        if task.status != TaskStatus.VERIFYING:
            raise ValueError("Task is not awaiting verification")
        plan = repo.get_plan(task_id)
        observations = task.metadata.get("execution", {}).get("observations", [])
        evidence, issues = [], []
        latest = {o["step_id"]: o for o in observations}
        for step in plan.steps:
            item = latest.get(step.id)
            if not item or item.get("status") != "ok" or not item.get("call_id"):
                issues.append(f"No successful tool evidence for {step.id}")
        writes = {
            o["arguments"]["path"]: o
            for o in observations
            if o.get("tool") == "filesystem.write" and o.get("status") == "ok"
        }
        for path, item in writes.items():
            read = await tools.execute("filesystem.read", {"path": path})
            if read.status != "ok" or read.output != item["arguments"]["content"]:
                issues.append(f"Written artifact no longer matches: {path}")
            else:
                evidence.append(read.call_id)
        mutation = max(
            (
                i
                for i, o in enumerate(observations)
                if o.get("tool") in ("filesystem.write", "python.run")
            ),
            default=-1,
        )
        tests = [
            o
            for i, o in enumerate(observations)
            if i > mutation
            and o.get("tool") == "terminal.run"
            and o.get("exit_code") == 0
            and o.get("status") == "ok"
            and not o.get("truncated")
        ]
        if not tests:
            issues.append("A successful final test command is required after all changes")
        else:
            evidence.extend(o["call_id"] for o in tests)
        result = Verification(passed=not issues, evidence=evidence, issues=issues)
        repo.finish_verification(task_id, result.model_dump(), task.version)
        return result
