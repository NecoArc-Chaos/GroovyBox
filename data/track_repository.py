"""Track Repository for GroovyBox.

This module provides CRUD operations for music tracks in the database.
Handles file import, metadata extraction, album art storage, directory
scanning, and track management operations. Supports both synchronous
(threaded) and asynchronous import workflows.
"""

import asyncio
import os
import shutil
from typing import List, Optional, Tuple
import threading
from data.db import get_connection, get_app_dir, is_mobile
from logic.logger import logger
from data.models import Track
from logic.metadata_service import get_metadata, SUPPORTED_EXTENSIONS

# Supported audio file extensions for import
AUDIO_EXTENSIONS = {"mp3", "m4a", "wav", "flac", "aac", "ogg", "wma", "m4p", "aiff", "au", "dss"}

# Supported lyrics file extensions for batch import
LYRICS_EXTENSIONS = {"lrc", "srt", "txt"}


def _get_music_dir() -> str:
    music_dir = os.path.join(get_app_dir(), "music")
    os.makedirs(music_dir, exist_ok=True)
    return music_dir


def watch_all_tracks() -> List[Track]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tracks ORDER BY title COLLATE NOCASE"
        ).fetchall()
    return [_row_to_track(r) for r in rows]


def get_track(track_id: int) -> Optional[Track]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return _row_to_track(row) if row else None


def get_track_by_path(path: str) -> Optional[Track]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tracks WHERE path = ?", (path,)).fetchone()
    return _row_to_track(row) if row else None


def _collect_music_files(directory_path: str, recursive: bool) -> List[str]:
    files = []
    if recursive:
        for root, _, filenames in os.walk(directory_path):
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, f))
    else:
        for f in os.listdir(directory_path):
            full = os.path.join(directory_path, f)
            if os.path.isfile(full):
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(full)
    return files


def _copy_to_music_dir(src: str) -> str:
    music_dir = _get_music_dir()
    filename = os.path.basename(src)
    dest = os.path.join(music_dir, filename)
    if not os.path.exists(dest):
        try:
            shutil.copy2(src, dest)
            return dest
        except Exception:
            return src
    name, ext = os.path.splitext(filename)
    for counter in range(1, 999):
        alt = os.path.join(music_dir, f"{name}_{counter}{ext}")
        if not os.path.exists(alt):
            try:
                shutil.copy2(src, alt)
                return alt
            except Exception:
                return src
    return src


def _do_import(file_paths: List[str], conn, copy: bool = False) -> Tuple[int, List[str]]:
    existing = {
        r["path"] for r in conn.execute(
            "SELECT path FROM tracks WHERE path IN ({})".format(
                ",".join("?" * len(file_paths))
            ), file_paths
        ).fetchall()
    }
    new_paths = [p for p in file_paths if p not in existing]
    mobile = is_mobile()
    should_copy = mobile or copy

    art_dir = os.path.join(get_app_dir(), "art")
    os.makedirs(art_dir, exist_ok=True)

    imported = 0
    for path in new_paths:
        if not os.path.isfile(path):
            continue
        try:
            meta = get_metadata(path)
            filename = os.path.basename(path)
            title = meta.title or os.path.splitext(filename)[0]

            final_path = _copy_to_music_dir(path) if should_copy else path

            art_path = None
            if meta.art_bytes:
                art_name = f"{os.path.splitext(filename)[0]}_{imported}_art.jpg"
                art_file = os.path.join(art_dir, art_name)
                try:
                    with open(art_file, "wb") as f:
                        f.write(meta.art_bytes)
                    art_path = art_file
                except Exception:
                    pass

            conn.execute(
                """INSERT OR IGNORE INTO tracks
                   (title, artist, album, duration, path, art_uri, lyrics_offset)
                   VALUES (?, ?, ?, ?, ?, ?, 0)""",
                (title, meta.artist, meta.album,
                 meta.duration, final_path, art_path),
            )
            conn.commit()
            imported += 1
        except Exception:
            continue
    return imported, new_paths


def import_files(file_paths: List[str], callback=None, copy: bool = False):
    def _import():
        try:
            with get_connection() as conn:
                imported, new_paths = _do_import(file_paths, conn, copy=copy)
            logger.info("import_files: imported %d/%d files", imported, len(new_paths))
            if callback:
                callback()
        except Exception as e:
            logger.error("import_files thread failed: %s", e)
    threading.Thread(target=_import, daemon=True).start()


async def import_files_async(file_paths: List[str], copy: bool = False) -> int:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _import_sync, file_paths, copy)


def _import_sync(file_paths: List[str], copy: bool = False) -> int:
    with get_connection() as conn:
        imported, new_paths = _do_import(file_paths, conn, copy=copy)
    logger.info("import_files_async: imported %d/%d files", imported, len(new_paths))
    return imported


def scan_directory(directory_path: str, recursive: bool = True, callback=None):
    def _scan():
        music_files = _collect_music_files(directory_path, recursive)
        if music_files:
            import_files(music_files, callback=callback)
        elif callback:
            callback()
    threading.Thread(target=_scan, daemon=True).start()


async def scan_directory_async(directory_path: str, recursive: bool = True) -> int:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _scan_sync, directory_path, recursive)


def _scan_sync(directory_path: str, recursive: bool) -> int:
    music_files = _collect_music_files(directory_path, recursive)
    if music_files:
        return _import_sync(music_files)
    return 0


def update_art_uri(track_id: int, art_path: Optional[str]):
    with get_connection() as conn:
        conn.execute("UPDATE tracks SET art_uri=? WHERE id=?", (art_path, track_id))
        conn.commit()


def update_metadata(track_id: int, title: str, artist: str = None, album: str = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE tracks SET title=?, artist=?, album=? WHERE id=?",
            (title, artist, album, track_id),
        )
        conn.commit()


def update_lyrics(track_id: int, lyrics_json: Optional[str]):
    with get_connection() as conn:
        conn.execute("UPDATE tracks SET lyrics=? WHERE id=?", (lyrics_json, track_id))
        conn.commit()


def update_lyrics_offset(track_id: int, offset: int):
    with get_connection() as conn:
        conn.execute("UPDATE tracks SET lyrics_offset=? WHERE id=?", (offset, track_id))
        conn.commit()


def delete_track(track_id: int):
    with get_connection() as conn:
        track = conn.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        if track:
            art = track["art_uri"]
            if art and os.path.isfile(art):
                try:
                    os.remove(art)
                except Exception:
                    pass
        conn.execute("DELETE FROM tracks WHERE id=?", (track_id,))
        conn.commit()


def clear_all_tracks():
    art_dir = os.path.join(get_app_dir(), "art")
    if os.path.isdir(art_dir):
        for f in os.listdir(art_dir):
            try:
                os.remove(os.path.join(art_dir, f))
            except Exception:
                pass
    with get_connection() as conn:
        conn.execute("DELETE FROM tracks")
        conn.commit()


def get_missing_tracks() -> List[Track]:
    missing: List[Track] = []
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM tracks").fetchall()
    for r in rows:
        track = _row_to_track(r)
        if not os.path.isfile(track.path):
            missing.append(track)
    return missing


def delete_tracks(track_ids: List[int]):
    if not track_ids:
        return
    placeholders = ",".join("?" * len(track_ids))
    with get_connection() as conn:
        for tid in track_ids:
            row = conn.execute("SELECT art_uri FROM tracks WHERE id=?", (tid,)).fetchone()
            if row and row["art_uri"] and os.path.isfile(row["art_uri"]):
                try:
                    os.remove(row["art_uri"])
                except Exception:
                    pass
        conn.execute(f"DELETE FROM tracks WHERE id IN ({placeholders})", track_ids)
        conn.commit()


def count_tracks() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]


def _row_to_track(row) -> Track:
    """Convert a database row to a Track dataclass instance.
    
    Args:
        row: A sqlite3.Row object from a tracks table query.
    
    Returns:
        A Track instance with values from the row.
    """
    return Track(
        id=row["id"],
        title=row["title"],
        artist=row["artist"],
        album=row["album"],
        duration=row["duration"],
        path=row["path"],
        art_uri=row["art_uri"],
        lyrics=row["lyrics"],
        lyrics_offset=row["lyrics_offset"],
        added_at=row["added_at"],
    )
