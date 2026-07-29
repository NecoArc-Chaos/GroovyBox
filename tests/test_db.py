"""Tests for database module."""

import pytest
import sqlite3
import os
from data import db


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database state between tests."""
    db._SETTING_CACHE.clear()
    db.DB_PATH = None
    conn = getattr(db._thread_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        db._thread_local.connection = None
    # Remove the database file to ensure clean state
    try:
        db_path = db.get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass
    yield
    db._SETTING_CACHE.clear()
    db.DB_PATH = None
    conn = getattr(db._thread_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        db._thread_local.connection = None
    try:
        db_path = db.get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


def test_init_database_creates_tables():
    db.init_database()
    with db.get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "tracks" in table_names
        assert "playlists" in table_names
        assert "playlist_entries" in table_names
        assert "watch_folders" in table_names
        assert "app_settings" in table_names


def test_get_setting_default():
    db.init_database()
    val = db.get_setting("nonexistent_key", "default_val")
    assert val == "default_val"


def test_set_and_get_setting():
    db.init_database()
    db.set_setting("test_key", "test_value")
    val = db.get_setting("test_key")
    assert val == "test_value"


def test_setting_cache():
    db.init_database()
    db.set_setting("cache_test", "cached_val")
    # First call populates cache
    val1 = db.get_setting("cache_test")
    assert val1 == "cached_val"
    # Update bypasses cache read
    db.set_setting("cache_test", "new_val")
    val2 = db.get_setting("cache_test")
    assert val2 == "new_val"


def test_get_app_dir():
    app_dir = db.get_app_dir()
    assert "groovybox" in app_dir


def test_get_db_path():
    path = db.get_db_path()
    assert path.endswith("groovybox.db")


def test_close_thread_connection():
    db.init_database()
    with db.get_connection() as conn:
        pass
    conn = getattr(db._thread_local, "connection", None)
    assert conn is not None
    db.close_thread_connection()
    assert getattr(db._thread_local, "connection", None) is None
