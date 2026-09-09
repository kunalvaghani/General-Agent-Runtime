"""Small attributed memory store with expiry, deduplication and explicit deletion."""

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from gar.safety.audit import redact


class MemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: Literal["working", "episodic", "semantic", "procedural"]
    content: str = Field(min_length=1, max_length=20000)
    source_task_id: str
    importance: float = Field(ge=0, le=1, allow_inf_nan=False)
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None


class MemoryManager:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memories "
                "(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, snapshot TEXT NOT NULL)"
            )

    def save(self, item: MemoryItem) -> str | None:
        if item.importance < 0.5 or not item.content.strip():
            return None
        data = item.model_dump()
        data["content"] = redact(item.content.strip())
        if item.type == "working" and item.expires_at is None:
            data["expires_at"] = time.time() + 86400
        item = MemoryItem.model_validate(data)
        fingerprint = hashlib.sha256(
            (
                item.type + "|" + item.source_task_id + "|" + " ".join(item.content.lower().split())
            ).encode()
        ).hexdigest()
        with sqlite3.connect(self.path) as conn:
            existing = conn.execute(
                "SELECT id FROM memories WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if existing:
                return existing[0]
            conn.execute(
                "INSERT INTO memories VALUES(?,?,?)", (item.id, fingerprint, item.model_dump_json())
            )
        return item.id

    def search(self, query: str = "", category: str | None = None, source: str | None = None):
        with sqlite3.connect(self.path) as conn:
            items = [
                MemoryItem.model_validate_json(r[0])
                for r in conn.execute("SELECT snapshot FROM memories")
            ]
        return sorted(
            [
                i
                for i in items
                if (i.expires_at is None or i.expires_at > time.time())
                and (category is None or i.type == category)
                and (source is None or i.source_task_id == source)
                and query.lower() in i.content.lower()
            ],
            key=lambda i: -i.importance,
        )[:100]

    def delete(self, item_id: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            return conn.execute("DELETE FROM memories WHERE id=?", (item_id,)).rowcount > 0

    def clear(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM memories")
