"""Background Watch Folder Scanner for GroovyBox.

This module provides automatic filesystem monitoring of music library folders
using the watchdog library. When files are added, modified, or removed,
the scanner automatically updates the track database.
"""

import os
import threading
import asyncio
from typing import Dict, Optional, Set
from data import track_repository as trepo
from logic.logger import logger
from logic.metadata_service import get_metadata

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False


if _HAS_WATCHDOG:

    class _TrackChangeHandler(FileSystemEventHandler):
        """Watchdog event handler that syncs filesystem changes to the database."""

        def __init__(self, scanner: "WatchScanner"):
            self._scanner = scanner
            self._loop: Optional[asyncio.AbstractEventLoop] = None

        def set_loop(self, loop: asyncio.AbstractEventLoop):
            self._loop = loop

        def _schedule(self, coro):
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self._loop)

        def on_created(self, event: FileSystemEvent):
            if event.is_directory:
                return
            path = event.src_path
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext in trepo.AUDIO_EXTENSIONS:
                logger.debug(f"watch_scanner: new file detected: {path}")
                self._schedule(self._scanner._on_file_added(path))

        def on_modified(self, event: FileSystemEvent):
            if event.is_directory:
                return
            path = event.src_path
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext in trepo.AUDIO_EXTENSIONS:
                logger.debug(f"watch_scanner: file modified: {path}")
                self._schedule(self._scanner._on_file_modified(path))

        def on_deleted(self, event: FileSystemEvent):
            if event.is_directory:
                return
            path = event.src_path
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext in trepo.AUDIO_EXTENSIONS:
                logger.debug(f"watch_scanner: file deleted: {path}")
                self._schedule(self._scanner._on_file_deleted(path))

        def on_moved(self, event: FileSystemEvent):
            if event.is_directory:
                return
            src_path = event.src_path
            dest_path = getattr(event, "dest_path", None)
            if not dest_path:
                return
            src_ext = os.path.splitext(src_path)[1].lower().lstrip(".")
            dest_ext = os.path.splitext(dest_path)[1].lower().lstrip(".")
            if src_ext in trepo.AUDIO_EXTENSIONS:
                logger.debug(f"watch_scanner: file moved: {src_path} -> {dest_path}")
                self._schedule(self._scanner._on_file_deleted(src_path))
            if dest_ext in trepo.AUDIO_EXTENSIONS:
                self._schedule(self._scanner._on_file_added(dest_path))


class WatchScanner:
    """Manages background filesystem watching for music library folders.

    Uses watchdog to monitor watch folders for changes and automatically
    imports or removes tracks as needed.
    """

    def __init__(self):
        self._observer: Optional[Observer] = None
        self._handler: Optional[_TrackChangeHandler] = None
        self._watched_paths: Dict[str, Set[str]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop for scheduling async tasks."""
        self._loop = loop
        if self._handler:
            self._handler.set_loop(loop)

    async def _on_file_added(self, path: str):
        """Handle a new audio file detected by watchdog."""
        if not os.path.isfile(path):
            return
        try:
            n = await trepo.import_files_async([path], copy=False)
            if n > 0:
                logger.info(f"watch_scanner: imported {path}")
        except Exception as ex:
            logger.warning(f"watch_scanner: failed to import {path}: {ex}")

    async def _on_file_modified(self, path: str):
        """Handle a modified audio file - re-import metadata."""
        if not os.path.isfile(path):
            return
        try:
            existing = trepo.get_track_by_path(path)
            if existing:
                meta = get_metadata(path)
                trepo.update_metadata(
                    existing.id,
                    meta.title or os.path.splitext(os.path.basename(path))[0],
                    meta.artist,
                    meta.album,
                )
                if meta.art_bytes:
                    art_dir = os.path.join(trepo.get_app_dir(), "art")
                    os.makedirs(art_dir, exist_ok=True)
                    art_name = f"{os.path.splitext(os.path.basename(path))[0]}_{existing.id}_art.jpg"
                    art_file = os.path.join(art_dir, art_name)
                    try:
                        with open(art_file, "wb") as f:
                            f.write(meta.art_bytes)
                        trepo.update_art_uri(existing.id, art_file)
                    except Exception:
                        pass
                logger.debug(f"watch_scanner: updated metadata for {path}")
        except Exception as ex:
            logger.warning(f"watch_scanner: failed to update {path}: {ex}")

    async def _on_file_deleted(self, path: str):
        """Handle a deleted audio file - remove from database."""
        try:
            track = trepo.get_track_by_path(path)
            if track:
                trepo.delete_track(track.id)
                logger.info(f"watch_scanner: removed {path}")
        except Exception as ex:
            logger.warning(f"watch_scanner: failed to remove {path}: {ex}")

    def start(self):
        """Start the watchdog observer thread."""
        if not _HAS_WATCHDOG:
            logger.warning("watch_scanner: watchdog not installed, skipping")
            return
        if self._observer and self._observer.is_alive():
            return
        self._handler = _TrackChangeHandler(self)
        if self._loop:
            self._handler.set_loop(self._loop)
        self._observer = Observer()
        for folder, _ in self._watched_paths.items():
            try:
                self._observer.schedule(self._handler, folder, recursive=True)
                logger.debug(f"watch_scanner: watching {folder}")
            except Exception as ex:
                logger.warning(f"watch_scanner: failed to watch {folder}: {ex}")
        self._observer.start()

    def stop(self):
        """Stop the watchdog observer."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    def add_watch(self, folder: str, folder_id: int):
        """Add a folder to the watch list.

        Args:
            folder: Absolute path to the folder.
            folder_id: Database ID of the watch folder entry.
        """
        with self._lock:
            self._watched_paths[folder] = {str(folder_id)}
        if self._observer and self._observer.is_alive():
            try:
                self._observer.schedule(self._handler, folder, recursive=True)
            except Exception as ex:
                logger.warning(f"watch_scanner: failed to add watch {folder}: {ex}")

    def remove_watch(self, folder: str):
        """Remove a folder from the watch list.

        Args:
            folder: Absolute path to the folder.
        """
        with self._lock:
            self._watched_paths.pop(folder, None)
        # watchdog does not support unschedule by path easily,
        # so restart observer to refresh watched paths
        if self._observer and self._observer.is_alive():
            self.stop()
            self.start()

    def refresh(self):
        """Refresh all watches (restart observer with current paths)."""
        if self._observer and self._observer.is_alive():
            self.stop()
        self.start()

    async def scan_all(self) -> int:
        """Perform a full scan of all watched folders.

        Returns:
            Total number of tracks imported.
        """
        total = 0
        with self._lock:
            folders = list(self._watched_paths.keys())
        for folder in folders:
            try:
                n = await trepo.scan_directory_async(folder, recursive=True)
                total += n
            except Exception as ex:
                logger.warning(f"watch_scanner: scan failed for {folder}: {ex}")
        return total
