"""Audio Handler for GroovyBox.

This module provides the AudioPlayer class that manages audio playback
using flet_audio across all platforms (Windows, Linux, macOS, Android, iOS).

The player handles track queue management, playback controls, position
tracking, and cross-thread UI updates via callbacks.
"""

import asyncio
import os
import random
import threading
import time
from collections.abc import Callable

import flet as ft

from data import db
from data.models import CurrentTrackData, Track
from logic.logger import logger


class AudioPlayer:
    """Core audio playback engine for GroovyBox.

    Manages a queue of tracks, handles play/pause/seek operations,
    and provides real-time position updates to the UI. Uses the
    flet_audio backend on all platforms.

    Attributes:
        queue: List of Track objects in the playback queue.
        current_index: Index of the currently playing track in the queue.
        shuffle: Whether shuffle mode is enabled.
        repeat_mode: Current repeat mode ("none", "one", or "all").
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.queue: list[Track] = []
        self.current_index = -1
        self.shuffle = False
        self.repeat_mode = "none"
        self._volume = float(db.get_setting("player_volume", "0.8"))
        self._is_playing = False
        self._position_ms = 0
        self._duration_ms = 0
        self._loading = False

        # UI event loop reference for thread-safe callbacks
        self._ui_loop: asyncio.AbstractEventLoop | None = None

        # Lock for thread-safe state mutations
        self._state_lock = threading.Lock()

        # Callback functions for UI updates
        self.on_track_change: Callable | None = None
        self.on_position_change: Callable | None = None
        self.on_play_state_change: Callable | None = None
        self.on_queue_change: Callable | None = None
        self.on_loading_change: Callable | None = None
        self.on_missing_tracks: Callable[[list[str], bool], None] | None = None

        # Timer for position polling; audio instance is created on first play
        self._timer_active = True
        self._fa_tick_thread = None
        self._start_fa_timer()

    def _start_fa_timer(self):
        def _loop():
            while self._timer_active:
                with self._state_lock:
                    if self._is_playing:
                        self._position_ms += 100
                    pos = self._position_ms
                if self.on_position_change:
                    self._call_on_ui(self.on_position_change, pos)
                time.sleep(0.1)

        self._fa_tick_thread = threading.Thread(target=_loop, daemon=True)
        self._fa_tick_thread.start()

    def _fa_on_loaded(self, e):
        """Handle audio loaded event from flet_audio.

        Starts playback once Flutter confirms the audio control is ready.
        page.update() flushes the play command to the Flutter side.
        """
        with self._state_lock:
            self._loading = False
            is_playing = self._is_playing
        if is_playing:
            asyncio.create_task(self._audio.play())
            self.page.update()
        if self.on_loading_change:
            self._call_on_ui(self.on_loading_change, False)

    def _fa_on_duration(self, e):
        """Handle duration change event from flet_audio."""
        if e.duration is not None:
            with self._state_lock:
                self._duration_ms = e.duration.in_milliseconds

    def _fa_on_position(self, e):
        """Handle position change event from flet_audio."""
        with self._state_lock:
            self._position_ms = e.position

    def _fa_on_state(self, e):
        """Handle state change event from flet_audio (detects track completion)."""
        from flet_audio import AudioState

        if e.state == AudioState.COMPLETED:
            self._call_on_ui(self._on_track_ended)

    def _fa_get_duration(self, path: str) -> int:
        """Get duration using mutagen as fallback for flet_audio.

        Args:
            path: Path to the audio file.

        Returns:
            Duration in milliseconds, or 0 if unavailable.
        """
        try:
            import mutagen

            mf = mutagen.File(path)
            if mf and mf.info:
                return int(mf.info.length * 1000)
        except Exception as ex:
            logger.debug(f"Failed to get duration for {path}: {ex}")
        return 0

    def _recreate_audio(self, path: str):
        """Remove old audio instance and create a new one with src at construction.

        Playback starts in _fa_on_loaded after Flutter confirms readiness.

        Args:
            path: Absolute path to the audio file.
        """
        from flet_audio import Audio as FletAudio
        from flet_audio import ReleaseMode

        if hasattr(self, "_audio") and self._audio is not None:
            try:
                if self._audio in self.page.services:
                    self.page.services.remove(self._audio)
            except Exception as ex:
                logger.debug(f"Failed to remove old audio service: {ex}")
            self.page.update()

        self._audio = FletAudio(
            src=path,
            autoplay=False,
            volume=self._volume,
            release_mode=ReleaseMode.STOP,
            on_loaded=self._fa_on_loaded,
            on_duration_change=self._fa_on_duration,
            on_position_change=self._fa_on_position,
            on_state_change=self._fa_on_state,
        )
        self.page.services.append(self._audio)
        self.page.update()
        # play() is called in _fa_on_loaded after Flutter confirms readiness

    # ======================== Cross-backend helpers ========================

    async def capture_ui_loop(self):
        """Capture the UI event loop reference for thread-safe callbacks.

        Called once during app initialization to store the running event loop.
        """
        self._ui_loop = asyncio.get_running_loop()

    def _call_on_ui(self, fn, *args):
        """Safely call a function on the UI thread.

        Attempts multiple strategies to ensure the callback runs on the
        main UI thread: direct event loop call, stored loop reference,
        or direct invocation as fallback.

        Args:
            fn: The callback function to invoke.
            *args: Arguments to pass to the function.
        """
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                loop.call_soon_threadsafe(fn, *args)
                return
        except RuntimeError:
            pass
        if self._ui_loop is not None:
            self._ui_loop.call_soon_threadsafe(fn, *args)
            return
        try:
            fn(*args)
        except Exception as ex:
            logger.error(f"_call_on_ui error: {ex}")

    # ======================== Public API ========================

    def shutdown(self):
        self._timer_active = False
        if hasattr(self, "_audio") and self._audio is not None:
            try:
                if self._audio in self.page.services:
                    self.page.services.remove(self._audio)
            except Exception:
                pass
            self._audio = None
        if self._fa_tick_thread and self._fa_tick_thread.is_alive():
            self._fa_tick_thread.join(timeout=1)
        logger.debug("Audio player shut down")

    def play_track(self, track: Track):
        """Play a single track, replacing the current queue.

        Args:
            track: The Track object to play.
        """
        logger.info(f"play_track: {track.title}")
        if not os.path.exists(track.path):
            name = track.title or os.path.basename(track.path)
            logger.warning(f"play_track: file not found - {name}")
            if self.on_missing_tracks:
                self._call_on_ui(self.on_missing_tracks, [name], True)
            return
        self.queue = [track]
        self.current_index = 0
        self._load_current()

    def play_tracks(self, tracks: list[Track], initial_index: int = 0):
        """Play a list of tracks starting from the specified index.

        Args:
            tracks: List of Track objects to add to the queue.
            initial_index: Index in the list to start playing from.
        """
        if not tracks:
            return
        valid = [t for t in tracks if os.path.exists(t.path)]
        missing = [t for t in tracks if not os.path.exists(t.path)]
        if missing:
            names = [t.title or os.path.basename(t.path) for t in missing]
            logger.warning(f"play_tracks: {len(names)} files not found")
            if self.on_missing_tracks:
                self._call_on_ui(self.on_missing_tracks, names, True)
        if not valid:
            return
        logger.info(f"play_tracks: {len(valid)} tracks, start index={initial_index}")
        self.queue = valid
        self.current_index = min(initial_index, len(valid) - 1)
        self._load_current()

    def _load_current(self):
        """Load and start playing the track at current_index.

        Handles file existence check, metadata loading, and
        recreates the flet_audio instance with the new source. Triggers all
        registered callbacks for track change, play state, and queue updates.
        """
        if self.current_index < 0 or self.current_index >= len(self.queue):
            logger.warning(f"_load_current: invalid index {self.current_index}")
            return
        track = self.queue[self.current_index]
        logger.info(f"_load_current: index={self.current_index} track={track.title}")
        path = track.path
        if not os.path.exists(path):
            track_name = track.title or os.path.basename(path)
            logger.error(f"File not found: {path}")
            with self._state_lock:
                self._loading = False
                self._is_playing = False
            if self.on_loading_change:
                self._call_on_ui(self.on_loading_change, False)
            if self.on_play_state_change:
                self._call_on_ui(self.on_play_state_change, False)
            if self.on_missing_tracks:
                self._call_on_ui(self.on_missing_tracks, [track_name], False)
            # Find next valid track, avoid infinite loop
            for _ in range(len(self.queue)):
                self.current_index = (self.current_index + 1) % len(self.queue)
                nxt = self.queue[self.current_index]
                if os.path.exists(nxt.path):
                    self._load_current()
                    return
            # All remaining tracks missing
            self.current_index = -1
            return

        with self._state_lock:
            self._loading = True
        if self.on_loading_change:
            self._call_on_ui(self.on_loading_change, True)

        duration = track.duration or self._fa_get_duration(path)
        with self._state_lock:
            self._position_ms = 0
            self._duration_ms = duration
            self._is_playing = True
        self._recreate_audio(path)

        with self._state_lock:
            self._loading = False

        # Notify UI components of the changes
        if self.on_loading_change:
            self._call_on_ui(self.on_loading_change, False)
        if self.on_play_state_change:
            self._call_on_ui(self.on_play_state_change, True)
        if self.on_track_change:
            self._call_on_ui(
                self.on_track_change,
                CurrentTrackData(
                    id=track.id,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    path=track.path,
                    art_uri=track.art_uri,
                    lyrics=track.lyrics,
                    lyrics_offset=track.lyrics_offset,
                ),
            )
        if self.on_queue_change:
            self._call_on_ui(self.on_queue_change)

    def play_current(self):
        """Restart the current track from the beginning."""
        if self.current_index >= 0 and self.current_index < len(self.queue):
            self.seek(0)
            with self._state_lock:
                self._is_playing = True
            if self.on_play_state_change:
                self._call_on_ui(self.on_play_state_change, True)

    def toggle_play_pause(self):
        """Toggle between play and pause states.

        If no track is loaded but the queue has items, starts playback.
        """
        with self._state_lock:
            is_playing = self._is_playing
        if is_playing:
            asyncio.create_task(self._audio.pause())
            with self._state_lock:
                self._is_playing = False
            if self.on_play_state_change:
                self._call_on_ui(self.on_play_state_change, False)
        else:
            if self.current_index >= 0 and self.current_index < len(self.queue):
                asyncio.create_task(self._audio.resume())
                with self._state_lock:
                    self._is_playing = True
                if self.on_play_state_change:
                    self._call_on_ui(self.on_play_state_change, True)
            elif self.queue:
                self._load_current()

    def next(self):
        """Advance to the next track in the queue.

        Respects shuffle and repeat modes:
        - shuffle: Random next track
        - repeat all: Wraps to beginning
        - no repeat: Stops at end of queue
        """
        if not self.queue:
            return
        if self.shuffle:
            self.current_index = random.randrange(0, len(self.queue))
        else:
            self.current_index += 1
        if self.current_index >= len(self.queue):
            if self.repeat_mode == "all" and self.queue:
                self.current_index = 0
            else:
                self.current_index = len(self.queue) - 1
                return
        self._load_current()

    def previous(self):
        """Go back to the previous track in the queue.

        Clamps to index 0 if already at the beginning.
        """
        if not self.queue:
            return
        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = 0
        self._load_current()

    def seek(self, position_ms: int):
        """Seek to a specific position in the current track.

        Args:
            position_ms: Target position in milliseconds.
        """
        asyncio.create_task(self._audio.seek(position_ms))
        with self._state_lock:
            self._position_ms = position_ms
        if self.on_position_change:
            self._call_on_ui(self.on_position_change, position_ms)

    def set_volume(self, volume: float):
        with self._state_lock:
            self._volume = max(0.0, min(1.0, volume))
            vol = self._volume
        db.set_setting("player_volume", str(round(vol, 2)))
        if hasattr(self, "_audio") and self._audio is not None:
            self._audio.volume = vol
        self.page.update()

    def get_current_track(self) -> Track | None:
        """Get the currently playing track object.

        Returns:
            The current Track object, or None if no track is loaded.
        """
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def _on_track_ended(self):
        """Handle natural track completion.

        Implements repeat-one, repeat-all, and sequential playback logic.
        Stops playback if at the end of the queue with no repeat.
        """
        logger.debug("Track ended naturally")
        if self.repeat_mode == "one":
            self.play_current()
        elif self.current_index < len(self.queue) - 1:
            self.next()
        elif self.repeat_mode == "all" and self.queue:
            self.current_index = 0
            self._load_current()
        else:
            with self._state_lock:
                self._is_playing = False
            if self.on_play_state_change:
                self._call_on_ui(self.on_play_state_change, False)
            if self.on_loading_change:
                self._call_on_ui(self.on_loading_change, False)

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing."""
        return self._is_playing

    @property
    def position_ms(self) -> int:
        """Current playback position in milliseconds."""
        return self._position_ms

    @property
    def duration_ms(self) -> int:
        """Total duration of the current track in milliseconds."""
        return self._duration_ms

    @property
    def volume(self) -> float:
        """Current volume level (0.0 to 1.0)."""
        return self._volume

    @property
    def loading(self) -> bool:
        """Whether a track is currently being loaded."""
        return self._loading
