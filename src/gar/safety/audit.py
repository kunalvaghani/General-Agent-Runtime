"""Append-only tool audit outside the task workspace; sensitive text is redacted."""

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def redact(text: str) -> str:
    text = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        text,
        flags=re.S,
    )
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    return re.sub(
        r"(?i)((?:api[_-]?key|password|secret|token)[\"']?\s*[=:]\s*[\"']?)[^\s,;\"'}]+",
        r"\1[REDACTED]",
        text,
    )


class Audit:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tool_audit "
                "(id INTEGER PRIMARY KEY, call_id TEXT, phase TEXT, timestamp TEXT, data TEXT)"
            )

    def append(self, call_id: str, phase: str, data: dict) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO tool_audit(call_id, phase, timestamp, data) VALUES(?,?,?,?)",
                (call_id, phase, datetime.now(UTC).isoformat(), redact(json.dumps(data))),
            )
