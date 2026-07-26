"""GroovyBox Main Application Module.

This module contains the core GroovyBoxApp class that orchestrates the entire
application lifecycle. It manages routing, theme configuration, audio playback
callbacks, and UI synchronization between screens.
"""

import asyncio
import json
import time
from typing import List, Optional
import flet as ft
from logic.logger import logger
from logic.localize import tr, load_locale
from data import db
from data import track_repository as trepo
from logic.metadata_service import get_metadata
from logic.key_bindings import DEFAULT_KEY_BINDINGS
from logic.tray_manager import SystemTrayManager
import os


class GroovyBoxApp:
    """Main application controller for GroovyBox.
    
    Responsible for initializing the database, loading user preferences,
    setting up the audio player, and managing navigation between screens.
    Acts as the central hub connecting the audio engine, data layer, and UI.
    
    Attributes:
        page: The Flet page instance.
        current_track: Currently playing track data (CurrentTrackData or None).
        current_metadata: Metadata of the currently playing track.
        theme_seed_color: Material 3 seed color for theming.
        theme_mode: Current theme mode (system/light/dark).
        shell: The main ShellView instance when in library/settings views.
        audio_player: The AudioPlayer instance for playback control.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_track = None
        self.current_metadata = None
        self.theme_seed_color = "#2EB0C6"
        self.theme_mode = ft.ThemeMode.SYSTEM
        self.shell = None

        # Initialize database and load user settings
        db.init_database()
        self._load_locale()
        self._load_theme_mode()
        self._setup_theme()

        # Configure logging level from saved settings
        from logic.logger import set_log_level
        set_log_level(db.get_setting("log_level", "normal"))

        # Store app reference in session for access from other components
        page.session.store.set("app", self)

        # Initialize audio player with flet_audio backend
        from logic.audio_handler import AudioPlayer
        self.audio_player = AudioPlayer(page)

        # Register audio event callbacks
        self.audio_player.on_track_change = self._on_track_change
        self.audio_player.on_loading_change = self._on_loading_change
        self.audio_player.on_play_state_change = self._on_play_state_change
        self.audio_player.on_position_change = self._on_position_change
        self.audio_player.on_missing_tracks = self._on_missing_tracks

        # Capture the UI event loop for thread-safe callbacks
        page.run_task(self.audio_player.capture_ui_loop)

        # Set up routing handlers
        page.on_route_change = self._on_route_change
        page.on_view_pop = self._on_view_pop

        # Track last window size and register resize listener
        self._last_window_width = page.width
        page.on_resize = self._on_window_resize

        # Global keyboard shortcuts for desktop
        page.on_keyboard_event = self._on_global_keyboard

        # Check for missing track files on startup (async, non-blocking)
        self._missing_count = 0
        page.run_task(self._check_missing_tracks_on_startup)

        # Configure window properties
        page.title = tr("appName")
        try:
            page.window.min_width = 400
            page.window.min_height = 300
        except Exception:
            pass

        # System tray and close behavior (desktop only)
        self._tray_manager = None
        self._tray_pending_show = False
        self._tray_pending_exit = False
        self._is_closing = False
        self._last_back_press = 0
        try:
            page.window.prevent_close = True
        except Exception:
            logger.warning("prevent_close not supported")
        try:
            page.window.on_event = self._on_window_event
        except Exception:
            try:
                page.on_window_event = self._on_window_event
            except Exception:
                logger.warning("window.on_event not supported")

        # Navigate to the library screen as the initial view
        page.run_task(page.push_route, "/library")
        page.run_task(self._tray_watch)
        self._set_window_icon()

    def _is_dark_mode(self):
        if self.theme_mode == ft.ThemeMode.DARK:
            return True
        if self.theme_mode == ft.ThemeMode.LIGHT:
            return False
        try:
            return self.page.platform_brightness == ft.Brightness.DARK
        except Exception:
            return False

    def _get_icon_suffix(self):
        return "-dark" if self._is_dark_mode() else ""

    def _set_window_icon(self):
        try:
            suffix = self._get_icon_suffix()
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "images", f"icon{suffix}.ico")
            if os.path.exists(icon_path):
                self.page.window.icon = icon_path
                self.page.update()
        except Exception:
            pass

    def _on_window_event(self, e):
        if self._is_closing:
            return
        evt_type = getattr(e, 'type', None) or getattr(e, 'name', None) or getattr(e, 'data', None) or ''
        if "close" in str(evt_type).lower():
            self._handle_close()

    def _handle_close(self):
        behavior = db.get_setting("close_behavior", "hide")
        if behavior == "exit":
            self._tray_pending_exit = True
        else:
            self._hide_to_tray()

    def _hide_to_tray(self):
        suffix = self._get_icon_suffix()
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "images", f"icon{suffix}.png")
        if not self._tray_manager:
            self._tray_manager = SystemTrayManager(
                icon_path=icon_path,
                on_show_callback=self._on_tray_show,
                on_exit_callback=self._on_tray_exit,
            )
        self._tray_manager.run()
        self.page.window.visible = False
        try:
            self.page.window.skip_task_bar = True
        except Exception:
            pass
        self.page.update()

    def _show_from_tray(self):
        if self._tray_manager:
            self._tray_manager.stop()
        try:
            self.page.window.visible = True
        except Exception:
            return
        try:
            self.page.window.skip_task_bar = False
        except Exception:
            pass
        try:
            self.page.window.to_front()
        except Exception:
            try:
                self.page.window_to_front()
            except Exception:
                pass
        self.page.update()

    async def _really_close(self):
        if self._tray_manager:
            self._tray_manager.stop()
        self._is_closing = True
        self.page.window.prevent_close = False
        try:
            await self.page.window.destroy()
        except Exception:
            try:
                await self.page.window.close()
            except Exception:
                import os
                os._exit(0)

    def _on_tray_show(self):
        self._tray_pending_show = True

    def _on_tray_exit(self):
        self._tray_pending_exit = True

    async def _tray_watch(self):
        while True:
            try:
                if self._tray_pending_exit:
                    self._tray_pending_exit = False
                    await self._really_close()
                    return
                if self._tray_pending_show:
                    self._tray_pending_show = False
                    self._show_from_tray()
                await asyncio.sleep(0.2)
            except Exception:
                return

    async def _check_missing_tracks_on_startup(self):
        loop = asyncio.get_running_loop()
        missing = await loop.run_in_executor(None, trepo.get_missing_tracks)
        self._missing_count = len(missing)
        if self._missing_count > 0:
            logger.warning(f"Found {self._missing_count} missing track(s) on startup")
            msg = tr("missingTracksFound").format(self._missing_count)

            def do_remove(e):
                self.page.pop_dialog()
                self.page.run_task(self._remove_missing_tracks)

            dlg = ft.AlertDialog(
                title=ft.Text(tr("missingTracks")),
                content=ft.Text(msg),
                actions=[
                    ft.TextButton(tr("ignore"), on_click=lambda e: self.page.pop_dialog()),
                    ft.FilledButton(tr("removeAllMissing"), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=do_remove),
                ],
            )
            self.page.show_dialog(dlg)
            self.page.update()

    async def _remove_missing_tracks(self):
        loop = asyncio.get_running_loop()
        missing = await loop.run_in_executor(None, trepo.get_missing_tracks)
        ids = [t.id for t in missing]
        await loop.run_in_executor(None, trepo.delete_tracks, ids)
        self._missing_count = 0
        self._reload_ui()

    def _load_locale(self):
        """Load the user's preferred language from settings."""
        lang = db.get_setting("language", "en")
        load_locale(lang)

    def _load_theme_mode(self):
        """Load and apply the saved theme mode (system/light/dark)."""
        mode = db.get_setting("theme_mode", "system")
        mode_map = {
            "system": ft.ThemeMode.SYSTEM,
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
        }
        self.theme_mode = mode_map.get(mode, ft.ThemeMode.SYSTEM)

    def _setup_theme(self):
        """Configure Material 3 theme with the seed color for both light and dark modes."""
        self.page.theme = ft.Theme(
            color_scheme_seed=self.theme_seed_color,
            use_material3=True,
        )
        self.page.dark_theme = ft.Theme(
            color_scheme_seed=self.theme_seed_color,
            use_material3=True,
        )
        self.page.theme_mode = self.theme_mode

    def _on_track_change(self, track_data):
        """Handle track change events from the audio player.
        
        Updates the current track reference, loads metadata (including album art),
        and refreshes all UI components.
        
        Args:
            track_data: CurrentTrackData instance with the new track info.
        """
        self.current_track = track_data
        if track_data and track_data.path:
            self._update_metadata(track_data.path)
        self._refresh_ui()

    def _on_loading_change(self, loading):
        """Handle loading state changes (e.g., buffering)."""
        self._refresh_ui()

    def _on_play_state_change(self, playing):
        """Handle play/pause state changes.
        
        Updates the mini player and full player screen play button icon.
        
        Args:
            playing: True if currently playing, False if paused.
        """
        try:
            if self.shell:
                self.shell.mini_player.refresh_play_state(playing)
            self._call_player_method("refresh_play_state", playing)
            self.page.update()
        except Exception as ex:
            logger.warning(f"_on_play_state_change skipped: {ex}")

    def _on_position_change(self, pos_ms):
        """Handle playback position updates.
        
        Updates progress bars in both the mini player and full player screen.
        
        Args:
            pos_ms: Current playback position in milliseconds.
        """
        try:
            dur_ms = self.audio_player.duration_ms if self.audio_player else 0
            if self.shell:
                self.shell.mini_player.refresh_position(pos_ms, dur_ms)
            self._call_player_method("refresh_position", pos_ms, dur_ms)
        except Exception as ex:
            logger.warning(f"_on_position_change skipped: {ex}")

    def _on_missing_tracks(self, names: List[str], from_user: bool):
        """Handle missing track files during playback.
        
        Shows an AlertDialog for explicit user actions (play/queue),
        or a SnackBar for automatic navigation skips.
        
        Args:
            names: List of missing track display names.
            from_user: True if triggered by explicit user action.
        """
        try:
            if from_user and len(names) > 0:
                if len(names) == 1:
                    msg = f"File not found: {names[0]}"
                else:
                    preview = ", ".join(names[:3])
                    extra = f"... (Total {len(names)})" if len(names) > 3 else ""
                    msg = f"Files not found: {preview}{extra}"
                dlg = ft.AlertDialog(
                    title=ft.Text("Error"),
                    content=ft.Text(msg),
                    actions=[ft.TextButton("OK", on_click=lambda e: self.page.pop_dialog())],
                )
                self.page.show_dialog(dlg)
                self.page.update()
            elif not from_user and len(names) == 1:
                self.page.show_dialog(
                    ft.SnackBar(ft.Text(f"File not found: {names[0]}"), duration=3000)
                )
                self.page.update()
        except Exception as ex:
            logger.warning(f"_on_missing_tracks failed: {ex}")

    def _call_player_method(self, method_name, *args):
        """Call a method on the PlayerScreen if it's the current top view.
        
        This allows the app to push updates directly to the player screen
        without maintaining a direct reference to it.
        
        Args:
            method_name: Name of the method to call on PlayerScreen.
            *args: Arguments to pass to the method.
        """
        if len(self.page.views) > 0:
            top = self.page.views[-1]
            if getattr(top, 'route', None) == "/player" and top.controls:
                ctrl = top.controls[0]
                method = getattr(ctrl, method_name, None)
                if method:
                    method(*args)

    def _update_metadata(self, path):
        """Load and cache metadata for the currently playing track.
        
        Extracts title, artist, album, and cover art from the audio file.
        Falls back to stored album art if extraction yields no results.
        
        Args:
            path: File path of the audio track.
        """
        from data import track_repository as trepo
        track = trepo.get_track_by_path(path)
        if track:
            meta = get_metadata(path)
            # Use stored art_uri as fallback if metadata has no embedded art
            if track.art_uri and not meta.art_bytes:
                try:
                    with open(track.art_uri, "rb") as f:
                        meta.art_bytes = f.read()
                except Exception:
                    pass
            self.current_metadata = meta
        else:
            self.current_metadata = None

    def _reload_ui(self):
        """Force a complete UI rebuild (used after data changes)."""
        self.page.title = tr("appName")
        self._sync_views()

    def _refresh_ui(self):
        """Refresh the current UI state without full rebuild.
        
        Updates the content view, mini player, and player screen
        to reflect the latest playback state.
        """
        try:
            if self.shell:
                self.shell.content_view.update()
                self.shell.mini_player.refresh()
            self._call_player_method("refresh")
            self.page.update()
        except Exception as ex:
            logger.warning(f"_refresh_ui skipped: {ex}")

    def _on_route_change(self, e):
        """Handle route changes by synchronizing views.
        
        Args:
            e: Route change event from the Flet framework.
        """
        self._sync_views()

    def _on_window_resize(self, e):
        """Handle window resize by notifying the current active screen."""
        try:
            current_width = self.page.width
            if current_width == self._last_window_width:
                return
            self._last_window_width = current_width
            self._notify_active_screen_window_resize()
        except Exception as ex:
            logger.warning(f"_on_window_resize failed: {ex}")

    def _notify_active_screen_window_resize(self):
        """Notify the currently active screen to rebuild after window resize."""
        try:
            route = self.page.route
            if route == "/player" and self.page.views:
                top = self.page.views[-1]
                if top.controls and hasattr(top.controls[0], 'on_window_size_changed'):
                    top.controls[0].on_window_size_changed()
                return
            if self.shell and self.shell.content_view.controls:
                content_screen = self.shell.content_view.controls[0]
                if hasattr(content_screen, 'on_window_size_changed'):
                    content_screen.on_window_size_changed()
                if self.shell and hasattr(self.shell, 'on_window_size_changed'):
                    self.shell.on_window_size_changed()
        except Exception as ex:
            logger.warning(f"_notify_active_screen_window_resize failed: {ex}")

    def _load_key_bindings(self):
        """Load custom key bindings from database, fall back to defaults."""
        raw = db.get_setting("key_bindings", "")
        if raw:
            try:
                stored = json.loads(raw)
                defaults = dict(DEFAULT_KEY_BINDINGS)
                defaults.update(stored)
                return defaults
            except Exception:
                pass
        return dict(DEFAULT_KEY_BINDINGS)

    def _on_global_keyboard(self, e: ft.KeyboardEvent):
        """Handle global keyboard shortcuts across all screens.
        
        Global shortcuts (work everywhere):
        - Space: Toggle play/pause
        - N: Next track
        - B: Previous track
        - Escape: Exit player screen
        
        Player-screen-only shortcuts:
        - Arrow Up/Down: Volume +/-5%
        - Arrow Left/Right: Seek +/-5s
        """
        # Check if key capture mode is active (from settings)
        capture_cb = self.page.session.store.get("__key_capture_callback")
        if capture_cb:
            capture_cb(e.key)
            return

        player = self.audio_player
        route = self.page.route
        b = self._load_key_bindings()

        try:
            key = e.key
            # Global shortcuts
            if key == b.get("play_pause", "Space") or key in (" ", "MediaPlayPause"):
                if player:
                    player.toggle_play_pause()
                self.page.update()
            elif key == b.get("next_track", "N"):
                if player:
                    player.next()
                self.page.update()
            elif key == b.get("prev_track", "B"):
                if player:
                    player.previous()
                self.page.update()
            elif key == b.get("exit_player", "Escape"):
                if route == "/player":
                    self.page.run_task(self.page.push_route, "/library")
            # Player-screen-only shortcuts (avoid UI conflicts elsewhere)
            elif route == "/player":
                if key == b.get("volume_up", "Arrow Up"):
                    if player:
                        player.set_volume(min(1.0, player.volume + 0.05))
                    self.page.update()
                elif key == b.get("volume_down", "Arrow Down"):
                    if player:
                        player.set_volume(max(0.0, player.volume - 0.05))
                    self.page.update()
                elif key == b.get("seek_back", "Arrow Left"):
                    if player:
                        player.seek(max(0, player.position_ms - 5000))
                    self.page.update()
                elif key == b.get("seek_forward", "Arrow Right"):
                    if player:
                        player.seek(min(player.duration_ms, player.position_ms + 5000))
                    self.page.update()
        except Exception as ex:
            logger.warning(f"_on_global_keyboard failed: {ex}")

    async def _on_view_pop(self, e):
        """Handle back navigation or prompt to exit on main page.
        
        Pops the top view if there are multiple views.
        On mobile with a single view, shows "press again to exit" toast.
        Desktop: no-op on single view.
        """
        if len(self.page.views) > 1:
            self.page.views.pop()
            top = self.page.views[-1]
            await self.page.push_route(top.route)
        elif db.is_mobile():
            now = time.time()
            if now - self._last_back_press < 2:
                try:
                    await self.page.window.destroy()
                except Exception:
                    try:
                        await self.page.window.close()
                    except Exception:
                        os._exit(0)
            else:
                self._last_back_press = now
                self.page.show_dialog(ft.SnackBar(ft.Text(tr("pressBackAgainToExit"))))

    def _sync_views(self):
        """Synchronize the page views with the current route.
        
        This is the main routing logic that determines which screen to display
        based on the URL route. Handles:
        - /player: Full-screen player view
        - /library or /: Main library with tracks/albums/playlists tabs
        - /artist: Artist detail view
        - /album: Album detail view
        - /playlist: Playlist detail view
        - /settings: Application settings
        - /live-sync: Lyrics sync mode (no-op, handled by player)
        """
        route = self.page.route

        # Player screen takes full page (no shell)
        if route == "/player":
            self.page.views.clear()
            from ui.screens.player_screen import PlayerScreen
            v = ft.View(
                route="/player",
                padding=0, spacing=0,
                controls=[PlayerScreen(self.page)],
            )
            self.page.views.append(v)
            self.page.update()
            return

        # Live-sync is handled within the player screen
        if route == "/live-sync":
            return

        # All other routes use the shell layout (toolbar + content + mini player)
        self.page.views.clear()
        from ui.shell import ShellView
        self.shell = ShellView(self.page)

        # Determine which content screen to display
        if route == "/" or route == "/library":
            from ui.screens.library_screen import LibraryScreen
            content = LibraryScreen(self.page)
        elif route == "/artist":
            from ui.screens.artist_detail_screen import ArtistDetailScreen
            artist = self.page.session.store.get("artist_data")
            if artist:
                content = ArtistDetailScreen(self.page, artist)
            else:
                from ui.screens.library_screen import LibraryScreen
                content = LibraryScreen(self.page)
        elif route == "/settings":
            from ui.screens.settings_screen import SettingsScreen
            content = SettingsScreen(self.page)
        elif route == "/album":
            from ui.screens.album_detail_screen import AlbumDetailView
            album = self.page.session.store.get("album_data")
            if album:
                content = AlbumDetailView(self.page, album)
            else:
                from ui.screens.library_screen import LibraryScreen
                content = LibraryScreen(self.page)
        elif route == "/playlist":
            from ui.screens.playlist_detail_screen import PlaylistDetailView
            playlist = self.page.session.store.get("playlist_data")
            if playlist:
                content = PlaylistDetailView(self.page, playlist)
            else:
                from ui.screens.library_screen import LibraryScreen
                content = LibraryScreen(self.page)
        else:
            # Default to library screen for unknown routes
            from ui.screens.library_screen import LibraryScreen
            content = LibraryScreen(self.page)

        # Assemble the shell with content and mini player
        self.shell.content_view.controls = [content]
        self.shell.mini_player.bind(self)
        self.page.views.append(self.shell)
        self.shell.mini_player.refresh()
        self.page.update()
