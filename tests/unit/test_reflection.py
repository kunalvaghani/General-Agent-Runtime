from gar.core.state import Task
from gar.learning.reflection import reflect
from gar.memory.manager import MemoryManager


def test_reflection_cannot_invent_or_approve_procedures(tmp_path):
    memory = MemoryManager(tmp_path / "memory.db")
    task = Task(
        goal="test",
        model_id="m",
        workspace="w",
        metadata={
            "verification": {"passed": True},
            "execution": {
                "observations": [{"tool": "terminal.run", "call_id": "actual", "status": "ok"}]
            },
        },
    )
    result = reflect(task, memory)
    assert result.evidence == ["actual"] and result.requires_review
    assert memory.search(category="procedural")[0].content.startswith("UNREVIEWED")
    reflect(task, memory)
    assert len(memory.search()) == 2
    empty = reflect(Task(goal="test", model_id="m", workspace="w"))
    assert not empty.evidence and empty.confidence < 0.5
