import sqlite3
import tempfile
import threading
from pathlib import Path

from app.core.config import get_settings
from app.storage import get_object_storage


_backup_lock = threading.Lock()


def sqlite_database_path() -> Path | None:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.removeprefix("sqlite:///")).resolve()


def restore_database_if_needed() -> bool:
    settings = get_settings()
    database_path = sqlite_database_path()
    if not settings.tos_enabled or database_path is None or database_path.exists():
        return False
    storage = get_object_storage()
    if not storage.exists(settings.tos_database_backup_key):
        return False
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.write_bytes(storage.read(settings.tos_database_backup_key))
    return True


def backup_database() -> bool:
    settings = get_settings()
    database_path = sqlite_database_path()
    if not settings.tos_enabled or database_path is None or not database_path.exists():
        return False
    with _backup_lock, tempfile.NamedTemporaryFile(suffix=".db") as temporary:
        with sqlite3.connect(database_path) as source, sqlite3.connect(temporary.name) as target:
            source.backup(target)
        get_object_storage().save(settings.tos_database_backup_key, Path(temporary.name).read_bytes())
    return True
