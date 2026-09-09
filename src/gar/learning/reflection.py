"""Grounded trace reflection; candidates are never executable instructions."""

from pydantic import BaseModel

from gar.memory.manager import MemoryItem


class Experience(BaseModel):
    source_task_id: str
    problem_pattern: str
    successful_strategy: list[str]
    failed_strategies: list[str]
    evidence: list[str]
    confidence: float
    requires_review: bool = True


def reflect(task, memory=None) -> Experience:
    observations = task.metadata.get("execution", {}).get("observations", [])
    good = [o for o in observations if o.get("status") == "ok" and o.get("call_id")]
    bad = [o for o in observations if o.get("status") == "error"]
    verified = bool(task.metadata.get("verification", {}).get("passed"))
    result = Experience(
        source_task_id=task.id,
        problem_pattern=task.goal,
        successful_strategy=[o["tool"] for o in good if o.get("tool")],
        failed_strategies=[o.get("error") or "unknown_failure" for o in bad],
        evidence=[o["call_id"] for o in good],
        confidence=0.8 if verified and good else 0.2,
    )
    if memory is not None:
        memory.save(
            MemoryItem(
                type="episodic",
                content=result.model_dump_json(),
                source_task_id=task.id,
                importance=0.7,
            )
        )
        if verified and good:
            memory.save(
                MemoryItem(
                    type="procedural",
                    source_task_id=task.id,
                    importance=0.7,
                    content="UNREVIEWED CANDIDATE: " + result.model_dump_json(),
                )
            )
    return result
