"""Explicit SQLite lifecycle. Creating configuration never opens a database."""

from pathlib import Path

from sqlalchemy import URL, create_engine, event

from gar.persistence.models import metadata


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.engine = create_engine(
            URL.create("sqlite", database=str(self.path)), connect_args={"timeout": 10}
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.engine.begin() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            if version not in (0, 1):
                raise ValueError("Unsupported GAR database schema version")
            metadata.create_all(connection)
            connection.exec_driver_sql("PRAGMA user_version=1")

    def close(self) -> None:
        self.engine.dispose()
