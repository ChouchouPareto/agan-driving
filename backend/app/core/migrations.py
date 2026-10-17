"""Upgrade versioned databases before ORM reads; preserve a local SQLite backup."""
from pathlib import Path
import sqlite3
import uuid

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.database import Base


def _backup_sqlite(engine) -> None:
    path = engine.url.database
    if engine.dialect.name == "sqlite" and path and path != ":memory:":
        backup = Path(path).resolve().parent / "backups"
        backup.mkdir(exist_ok=True)
        target = backup / f"before-migration-{uuid.uuid4().hex}.db"
        with sqlite3.connect(path) as source, sqlite3.connect(target) as destination:
            source.backup(destination)


def initialize_database(engine) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    tables = inspect(engine).get_table_names()
    if "alembic_version" in tables:
        with engine.connect() as connection:
            current = connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        head = ScriptDirectory.from_config(config).get_current_head()
        if current != head:
            _backup_sqlite(engine)
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
    Base.metadata.create_all(engine)
    # Older development DBs may have been created without Alembic tracking.
    if "knowledge_chunks" in inspect(engine).get_table_names():
        columns = {column["name"] for column in inspect(engine).get_columns("knowledge_chunks")}
        if "embedding" not in columns:
            _backup_sqlite(engine)
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN embedding JSON"))
