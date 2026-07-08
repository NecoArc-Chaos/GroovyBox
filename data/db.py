"""Database Module for GroovyBox.

This module handles all database operations including connection management,
schema initialization, and application settings persistence. Uses SQLite
with WAL journal mode for concurrent read/write performance.
"""

import contextlib
import sqlite3
import os
from typing import Optional


# Global cached database path to avoid repeated path resolution
DB_PATH = None

# Simple in-memory cache for get_setting (cleared on set_setting)
_SETTING_CACHE: dict = {}


def is_mobile() -> bool:
    if "ANDROID_ROOT" in os.environ:
        return True
    if os.environ.get("FLET_APP_DATA_DIR"):
        return True
    try:
        test_dir = os.path.join(os.path.expanduser("~"), ".groovybox_writable_test")
        os.makedirs(test_dir, exist_ok=True)
        os.rmdir(test_dir)
        return False
    except (OSError, PermissionError):
        return True


# Backward compat alias
_is_mobile = is_mobile


def get_app_data_dir() -> str:
    flet_dir = os.environ.get("FLET_APP_DATA_DIR")
    if flet_dir:
        return flet_dir
    if "ANDROID_ROOT" in os.environ:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.expanduser("~")


def get_app_dir() -> str:
    base = get_app_data_dir()
    return os.path.join(base, "groovybox")


def get_db_path():
    global DB_PATH
    if DB_PATH is None:
        app_dir = get_app_dir()
        os.makedirs(app_dir, exist_ok=True)
        DB_PATH = os.path.join(app_dir, "groovybox.db")
    return DB_PATH


@contextlib.contextmanager
def get_connection():
    """Create and configure a new SQLite database connection.
    
    """

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.text_factory = str
    try:
        yield conn
    finally:
        conn.close()


def with_conn(func):
    """Decorator that provides a managed database connection."""
    def wrapper(*args, **kwargs):
        with get_connection() as conn:
            return func(conn, *args, **kwargs)
    return wrapper


def init_database():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT,
                album TEXT,
                duration INTEGER,
                path TEXT UNIQUE NOT NULL,
                art_uri TEXT,
                lyrics TEXT,
                lyrics_offset INTEGER DEFAULT 0,
                added_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS playlist_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
                track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
                added_at TEXT DEFAULT (datetime('now')),
                sort_order INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS watch_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                recursive INTEGER DEFAULT 1,
                added_at TEXT DEFAULT (datetime('now')),
                last_scanned TEXT
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        try:
            conn.execute("ALTER TABLE playlist_entries ADD COLUMN sort_order INTEGER DEFAULT 0")
        except Exception:
            pass
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    cached = _SETTING_CACHE.get(key)
    if cached is not None:
        return cached
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    val = row["value"] if row else default
    _SETTING_CACHE[key] = val
    return val


def set_setting(key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    _SETTING_CACHE[key] = value
