"""Tests for track repository module."""

import os
import tempfile
import time

import pytest

from data import db
from data.models import Track
from data.track_repository import (
    AUDIO_EXTENSIONS,
    LYRICS_EXTENSIONS,
    _get_music_dir,
    _row_to_track,
    clear_all_tracks,
    count_tracks,
    delete_track,
    delete_tracks,
    get_missing_tracks,
    get_track,
    get_track_by_path,
    import_files,
    update_metadata,
    watch_all_tracks,
)


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
    try:
        db_path = db.get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass
    db.init_database()
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


def test_audio_extensions_non_empty():
    assert len(AUDIO_EXTENSIONS) > 0
    assert "mp3" in AUDIO_EXTENSIONS
    assert "flac" in AUDIO_EXTENSIONS


def test_lyrics_extensions_non_empty():
    assert len(LYRICS_EXTENSIONS) > 0
    assert "lrc" in LYRICS_EXTENSIONS
    assert "srt" in LYRICS_EXTENSIONS


def test_get_music_dir():
    music_dir = _get_music_dir()
    assert os.path.isdir(music_dir)
    assert "music" in music_dir


def test_count_tracks_empty():
    assert count_tracks() == 0


def test_import_and_count_tracks():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        assert count_tracks() == 1
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_get_track_by_path():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        track = get_track_by_path(tmp_path)
        assert track is not None
        assert isinstance(track, Track)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_get_track():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        track = get_track_by_path(tmp_path)
        assert track is not None
        fetched = get_track(track.id)
        assert fetched is not None
        assert fetched.id == track.id
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_watch_all_tracks():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        tracks = watch_all_tracks()
        assert len(tracks) == 1
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_update_metadata():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        track = get_track_by_path(tmp_path)
        assert track is not None
        update_metadata(track.id, "New Title", "New Artist", "New Album")
        updated = get_track(track.id)
        assert updated.title == "New Title"
        assert updated.artist == "New Artist"
        assert updated.album == "New Album"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_delete_track():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        track = get_track_by_path(tmp_path)
        assert track is not None
        delete_track(track.id)
        assert get_track(track.id) is None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_delete_tracks_batch():
    paths = []
    for i in range(3):
        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        paths.append(tmp_path)
    try:
        import_files(paths, copy=False)
        time.sleep(0.5)
        tracks = watch_all_tracks()
        ids = [t.id for t in tracks]
        delete_tracks(ids)
        assert count_tracks() == 0
    finally:
        for p in paths:
            if os.path.exists(p):
                os.unlink(p)


def test_clear_all_tracks():
    paths = []
    for i in range(2):
        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        paths.append(tmp_path)
    try:
        import_files(paths, copy=False)
        time.sleep(0.5)
        assert count_tracks() == 2
        clear_all_tracks()
        assert count_tracks() == 0
    finally:
        for p in paths:
            if os.path.exists(p):
                os.unlink(p)


def test_get_missing_tracks():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        # File exists, so no missing tracks
        missing = get_missing_tracks()
        assert len(missing) == 0
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_get_missing_tracks_after_delete():
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        import_files([tmp_path], copy=False)
        time.sleep(0.5)
        os.unlink(tmp_path)
        missing = get_missing_tracks()
        assert len(missing) == 1
    except FileNotFoundError:
        pass


def test_row_to_track():
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM tracks WHERE id=1").fetchone()
    if row:
        track = _row_to_track(row)
        assert isinstance(track, Track)
        assert track.id == row["id"]
