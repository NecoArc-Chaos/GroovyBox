"""Playlist Repository for GroovyBox.

This module provides CRUD operations for playlists and their associated tracks.
Also includes queries for albums, artists, and artist-album relationships
used by the library browsing screens.
"""

from data.db import get_connection
from data.models import AlbumData, ArtistAlbums, Playlist, Track
from data.track_repository import _row_to_track


def watch_all_playlists() -> list[Playlist]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM playlists ORDER BY created_at").fetchall()
    return [_row_to_playlist(r) for r in rows]


def watch_playlist_tracks(playlist_id: int) -> list[Track]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.* FROM tracks t
               JOIN playlist_entries pe ON t.id = pe.track_id
               WHERE pe.playlist_id = ?
               ORDER BY pe.sort_order, pe.added_at""",
            (playlist_id,),
        ).fetchall()
    return [_row_to_track(r) for r in rows]


def set_playlist_track_order(playlist_id: int, track_ids: list[int]):
    with get_connection() as conn:
        for order, tid in enumerate(track_ids):
            conn.execute(
                "UPDATE playlist_entries SET sort_order = ? WHERE playlist_id = ? AND track_id = ?",
                (order, playlist_id, tid),
            )
        conn.commit()


def find_by_name(name: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM playlists WHERE name = ?", (name,)).fetchone()
    return row[0] if row else None


def create_playlist(name: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
        conn.commit()
        pid = cur.lastrowid
    return pid


def delete_playlist(playlist_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
        conn.commit()


def add_to_playlist(playlist_id: int, track_id: int):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO playlist_entries (playlist_id, track_id) VALUES (?, ?)",
            (playlist_id, track_id),
        )
        conn.commit()


def remove_from_playlist(playlist_id: int, track_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM playlist_entries WHERE playlist_id=? AND track_id=?",
            (playlist_id, track_id),
        )
        conn.commit()


def watch_artists_with_albums() -> list[ArtistAlbums]:
    with get_connection() as conn:
        rows = conn.execute("""SELECT COALESCE(NULLIF(artist,''), 'Unknown') as artist,
                      album, MIN(art_uri) as art_uri
               FROM tracks WHERE album IS NOT NULL
               GROUP BY artist, album ORDER BY artist, album""").fetchall()

        artists_dict = {}
        for r in rows:
            artist_name = r["artist"]
            if artist_name not in artists_dict:
                artists_dict[artist_name] = {"albums": [], "track_count": 0}
            artists_dict[artist_name]["albums"].append(
                AlbumData(album=r["album"], artist=artist_name, art_uri=r["art_uri"])
            )

        for artist_name, data in artists_dict.items():
            safe_name = artist_name if artist_name != "Unknown" else ""
            if safe_name:
                cnt = conn.execute(
                    "SELECT COUNT(*) as c FROM tracks WHERE artist=? AND album IS NOT NULL", (safe_name,)
                ).fetchone()["c"]
            else:
                cnt = conn.execute(
                    "SELECT COUNT(*) as c FROM tracks WHERE (artist IS NULL OR artist='') AND album IS NOT NULL"
                ).fetchone()["c"]
            data["track_count"] = cnt

    return [ArtistAlbums(artist=a, albums=d["albums"], track_count=d["track_count"]) for a, d in artists_dict.items()]


def watch_all_albums() -> list[AlbumData]:
    with get_connection() as conn:
        rows = conn.execute("""SELECT album, MIN(artist) as artist, MIN(art_uri) as art_uri
               FROM tracks WHERE album IS NOT NULL
               GROUP BY album ORDER BY album""").fetchall()
    return [
        AlbumData(
            album=r["album"],
            artist=r["artist"] or "Various Artists",
            art_uri=r["art_uri"],
        )
        for r in rows
    ]


def watch_artist_tracks(artist_name: str) -> list[Track]:
    with get_connection() as conn:
        if artist_name == "Unknown":
            rows = conn.execute("SELECT * FROM tracks WHERE (artist IS NULL OR artist='') ORDER BY title").fetchall()
        else:
            rows = conn.execute("SELECT * FROM tracks WHERE artist=? ORDER BY album, title", (artist_name,)).fetchall()
    return [_row_to_track(r) for r in rows]


def watch_album_tracks(album_name: str) -> list[Track]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM tracks WHERE album = ? ORDER BY title", (album_name,)).fetchall()
    return [_row_to_track(r) for r in rows]


def _row_to_playlist(row) -> Playlist:
    """Convert a database row to a Playlist dataclass instance.

    Args:
        row: A sqlite3.Row object from a playlists table query.

    Returns:
        A Playlist instance with values from the row.
    """
    return Playlist(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
    )
