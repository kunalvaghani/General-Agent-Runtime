import time

from gar.memory.manager import MemoryItem, MemoryManager


def test_memory_attribution_dedup_expiry_and_delete(tmp_path):
    manager = MemoryManager(tmp_path / "memory.db")
    item = MemoryItem(type="semantic", content="Uses Python", source_task_id="a", importance=0.8)
    key = manager.save(item)
    assert manager.save(item.model_copy(update={"content": " uses   python "})) == key
    manager.save(item.model_copy(update={"id": "other", "source_task_id": "b"}))
    assert len(manager.search(source="a")) == 1
    assert len(manager.search("python")) == 2
    assert manager.save(item.model_copy(update={"importance": 0.1})) is None
    manager.save(
        MemoryItem(
            type="working",
            content="old",
            source_task_id="a",
            importance=0.9,
            expires_at=time.time() - 1,
        )
    )
    assert not manager.search("old")
    assert MemoryManager(manager.path).delete(key)
    assert not manager.search(source="a")
