"""Tests for playlist repository module."""

import pytest
import os
import tempfile
from data import db
from data.playlist_repository import (
    watch_all_playlists,
    watch_playlist_tracks,
    set_playlist_track_order,
    find_by_name,
    create_playlist,
    delete_playlist,
    add_to_playlist,
    remove_from_playlist,
    watch_all_albums,
    watch_artists_with_albums,
    watch_artist_tracks,
    watch_album_tracks,
)
from data.models import Playlist, Track, AlbumData, ArtistAlbums


_counter = 0


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


def _create_track(title="Test Track"):
    """Helper to create a track in the database with a unique path."""
    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO tracks (title, path) VALUES (?, ?)",
            (title, tmp_path),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"], tmp_path


def test_create_and_watch_playlist():
    pid = create_playlist("Test Playlist")
    assert pid > 0
    playlists = watch_all_playlists()
    assert len(playlists) == 1
    assert playlists[0].name == "Test Playlist"


def test_find_by_name():
    create_playlist("Find Me")
    found_id = find_by_name("Find Me")
    assert found_id is not None
    not_found = find_by_name("Not Found")
    assert not_found is None


def test_delete_playlist():
    pid = create_playlist("Delete Me")
    delete_playlist(pid)
    playlists = watch_all_playlists()
    assert len(playlists) == 0


def test_add_and_remove_from_playlist():
    pid = create_playlist("With Tracks")
    tid, _ = _create_track()
    add_to_playlist(pid, tid)
    tracks = watch_playlist_tracks(pid)
    assert len(tracks) == 1
    remove_from_playlist(pid, tid)
    tracks = watch_playlist_tracks(pid)
    assert len(tracks) == 0


def test_set_playlist_track_order():
    pid = create_playlist("Ordered")
    t1, _ = _create_track(title="A")
    t2, _ = _create_track(title="B")
    t3, _ = _create_track(title="C")
    add_to_playlist(pid, t1)
    add_to_playlist(pid, t2)
    add_to_playlist(pid, t3)
    set_playlist_track_order(pid, [t3, t1, t2])
    tracks = watch_playlist_tracks(pid)
    assert [t.id for t in tracks] == [t3, t1, t2]


def test_watch_all_albums_empty():
    albums = watch_all_albums()
    assert len(albums) == 0


def test_watch_all_albums_with_data():
    tid, _ = _create_track(title="T1")
    with db.get_connection() as conn:
        conn.execute("UPDATE tracks SET album='Album1', artist='Artist1' WHERE id=?", (tid,))
        conn.commit()
    albums = watch_all_albums()
    assert len(albums) == 1
    assert albums[0].album == "Album1"


def test_watch_artists_with_albums():
    tid, _ = _create_track(title="T1")
    with db.get_connection() as conn:
        conn.execute("UPDATE tracks SET album='Album1', artist='Artist1' WHERE id=?", (tid,))
        conn.commit()
    artists = watch_artists_with_albums()
    assert len(artists) == 1
    assert artists[0].artist == "Artist1"
    assert len(artists[0].albums) == 1


def test_watch_artist_tracks():
    tid, _ = _create_track(title="T1")
    with db.get_connection() as conn:
        conn.execute("UPDATE tracks SET artist='Artist1' WHERE id=?", (tid,))
        conn.commit()
    tracks = watch_artist_tracks("Artist1")
    assert len(tracks) == 1
    assert tracks[0].id == tid


def test_watch_album_tracks():
    tid, _ = _create_track(title="T1")
    with db.get_connection() as conn:
        conn.execute("UPDATE tracks SET album='Album1' WHERE id=?", (tid,))
        conn.commit()
    tracks = watch_album_tracks("Album1")
    assert len(tracks) == 1
    assert tracks[0].id == tid
