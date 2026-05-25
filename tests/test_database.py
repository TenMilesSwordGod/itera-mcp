import sqlite3
import pytest
from pathlib import Path
import tempfile
from itera_mcp.database import init_db, close_db, SCHEMA_VERSION


def test_init_db_creates_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        conn = init_db(str(path))

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "projects" in table_names
        assert "items" in table_names
        assert "iterations" in table_names
        assert "memory_entries" in table_names
        assert "activity_log" in table_names

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == SCHEMA_VERSION

        close_db()


def test_init_db_is_idempotent():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        init_db(str(path))
        close_db()
        conn2 = init_db(str(path))
        tables = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        assert len(tables) == 10
        close_db()


def test_wal_mode_enabled():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        conn = init_db(str(path))
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal == "wal"
        close_db()


def test_foreign_keys_enabled():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        conn = init_db(str(path))
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        close_db()


def test_foreign_key_enforcement():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        path = Path(f.name)
        conn = init_db(str(path))

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO items (id, project_id, type, title, summary, created_at, updated_at) "
                "VALUES ('item-1', 'no-such-project', 'bug', 'test', 'test', '2024-01-01', '2024-01-01')"
            )
            conn.commit()
        close_db()