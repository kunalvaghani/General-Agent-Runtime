"""SQLite tables store validated snapshots and an ordered event journal."""

from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, Text

metadata = MetaData()
tasks = Table(
    "tasks",
    metadata,
    Column("id", String, primary_key=True),
    Column("version", Integer, nullable=False),
    Column("snapshot", Text, nullable=False),
)
plans = Table(
    "plans",
    metadata,
    Column("task_id", String, ForeignKey("tasks.id"), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("snapshot", Text, nullable=False),
)
events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String, ForeignKey("tasks.id"), nullable=False, index=True),
    Column("event", String, nullable=False),
    Column("timestamp", String, nullable=False),
    Column("data", Text, nullable=False),
)
