from pathlib import Path

from app import database_backup
from app.storage import LocalStorage


def test_local_storage_rejects_parent_path():
    storage = LocalStorage()
    try:
        storage.save("../outside.txt", b"unsafe")
        assert False, "parent traversal must be rejected"
    except ValueError:
        pass


def test_sqlite_backup_round_trip(monkeypatch, tmp_path: Path):
    database_path = tmp_path / "app.db"

    class MemoryStorage:
        content = b""

        def save(self, key: str, content: bytes) -> None:
            self.content = content

        def read(self, key: str) -> bytes:
            return self.content

        def exists(self, key: str) -> bool:
            return bool(self.content)

    storage = MemoryStorage()
    monkeypatch.setattr(database_backup, "sqlite_database_path", lambda: database_path)
    monkeypatch.setattr(database_backup, "get_object_storage", lambda: storage)
    monkeypatch.setattr(database_backup.get_settings(), "storage_backend", "tos")
    monkeypatch.setattr(database_backup.get_settings(), "tos_bucket", "test-bucket")

    import sqlite3
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('ok')")
        connection.commit()
    assert database_backup.backup_database()
    database_path.unlink()
    assert database_backup.restore_database_if_needed()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "ok"
