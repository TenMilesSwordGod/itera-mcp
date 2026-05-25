import os
import sqlite3
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session

from . import models

_db_path: str | None = None
_conn: sqlite3.Connection | None = None

SCHEMA_VERSION = 2

MIGRATIONS: dict[int, str] = {
    2: """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            iteration_id TEXT REFERENCES iterations(id),
            title TEXT NOT NULL,
            summary TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed')),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            name TEXT NOT NULL,
            description TEXT,
            is_preset INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, name)
        );

        CREATE TABLE IF NOT EXISTS conclusions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id),
            content TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('high', 'medium', 'low')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_tags (
            memory_id INTEGER NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id),
            PRIMARY KEY (memory_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS merge_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            entity_type TEXT NOT NULL CHECK(entity_type IN ('memory', 'conclusion')),
            kept_id INTEGER NOT NULL,
            removed_id INTEGER NOT NULL,
            kept_content TEXT NOT NULL,
            removed_content TEXT NOT NULL,
            similarity REAL NOT NULL,
            merged_at TEXT NOT NULL
        );

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'architecture', 'Architecture & design: system structure, module division, design patterns', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'implementation', 'Implementation details: code approaches, algorithm choices, coding techniques', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'risk', 'Risks & issues: identified risks, encountered problems, technical debt', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'decision', 'Key decisions: important technical/business decisions and rationale', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'pattern', 'Patterns & experience: reusable solutions, best practices, lessons learned', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'integration', 'Dependencies & integration: external dependencies, API integrations, third-party services', 1, datetime('now')
        FROM projects;

        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'quality', 'Quality & optimization: code quality, performance optimization, security hardening', 1, datetime('now')
        FROM projects;

        CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_iteration_id ON sessions(iteration_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_tags_project_id ON tags(project_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_project_id ON conclusions(project_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_session_id ON conclusions(session_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_tag_id ON conclusions(tag_id);
        CREATE INDEX IF NOT EXISTS idx_merge_log_project_id ON merge_log(project_id);
        CREATE INDEX IF NOT EXISTS idx_merge_log_entity_type ON merge_log(entity_type);
    """,
    1: """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            tech_stack TEXT,
            constraints TEXT,
            active_iteration_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS iterations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            name TEXT NOT NULL,
            goal TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT NOT NULL DEFAULT 'planning'
                CHECK(status IN ('planning', 'active', 'completed')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            type TEXT NOT NULL CHECK(type IN ('requirement', 'bug')),
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'medium'
                CHECK(priority IN ('high', 'medium', 'low')),
            status TEXT NOT NULL DEFAULT 'backlog',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            iteration_id TEXT REFERENCES iterations(id),
            acceptance_criteria TEXT,
            severity TEXT CHECK(severity IN ('critical', 'major', 'minor')),
            steps_to_reproduce TEXT,
            environment TEXT,
            verified INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS memory_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            type TEXT NOT NULL
                CHECK(type IN ('fact', 'decision', 'pitfall', 'preference')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            timestamp TEXT NOT NULL,
            session_id TEXT,
            action TEXT NOT NULL,
            summary TEXT,
            item_id TEXT,
            iteration_id TEXT,
            details TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_items_project_id ON items(project_id);
        CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
        CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
        CREATE INDEX IF NOT EXISTS idx_items_iteration_id ON items(iteration_id);
        CREATE INDEX IF NOT EXISTS idx_items_deleted ON items(deleted);
        CREATE INDEX IF NOT EXISTS idx_iterations_project_id ON iterations(project_id);
        CREATE INDEX IF NOT EXISTS idx_memory_project_id ON memory_entries(project_id);
        CREATE INDEX IF NOT EXISTS idx_activity_project_id ON activity_log(project_id);
    """
}


def _get_data_dir() -> Path:
    data_dir = os.environ.get("ITERA_DATA_DIR", os.path.expanduser("~/.itera"))
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    global _conn, _db_path

    if _conn is not None:
        return _conn

    if db_path is None:
        db_path = str(_get_data_dir() / "itera.db")

    _db_path = db_path
    _conn = sqlite3.connect(db_path)
    _conn.execute("PRAGMA journal_mode=WAL;")
    _conn.execute("PRAGMA foreign_keys=ON;")
    _conn.row_factory = sqlite3.Row

    _run_migrations(_conn)

    models.init_engine(db_path)

    logger.info(f"Database initialized at {db_path}")
    return _conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    logger.info(f"Current schema version: {current_version}")

    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            logger.info(f"Running migration v{version}")
            conn.executescript(MIGRATIONS[version])
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()


def get_db() -> sqlite3.Connection:
    if _conn is None:
        return init_db()
    return _conn


def get_session() -> Session:
    if _db_path is None:
        init_db()
    return models.get_session(_db_path)


def close_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    models.close_engine()