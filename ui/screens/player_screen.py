"""Player Screen for GroovyBox.

This module implements the full-screen music player with multiple view modes:
- Cover: Album art with playback controls
- Lyrics: Synchronized lyrics display (curved or flat mode)
- Queue: Reorderable playback queue

Features include keyboard shortcuts, lyrics synchronization, online lyrics
fetching from multiple sources, and a lyrics offset adjustment tool.
"""

import asyncio
import flet as ft
import os
import threading
from logic.localize import tr
from logic.lyrics_parser import lyrics_from_json, lyrics_to_json
from logic.metadata_service import format_duration
from logic.play_mode import cycle_play_mode
from data import db
from data import track_repository as trepo
from logic.logger import logger


def _safe_seek(e, player):
    """Safely seek to a position, catching runtime errors during shutdown."""
    try:
        player.seek(int(e.control.value))
    except RuntimeError:
        pass


def _safe_volume(e, player):
    """Safely set volume, catching runtime errors during shutdown."""
    try:
        player.set_volume(e.control.value / 100)
    except RuntimeError:
        pass


class PlayerScreen(ft.Container):
    """Full-screen music player with cover art, lyrics, and queue views.
    
    Provides multiple display modes and handles keyboard shortcuts,
    lyrics synchronization, and real-time position tracking.
    
    Attributes:
        _view_mode: Current display mode ("cover", "lyrics", or "queue").
    """

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, padding=0)
        self._page = page
        self._view_mode = page.session.store.get("player_view") or "cover"

        self._inner = ft.Stack(expand=True)
        self.content = self._inner

        # UI element references for efficient updates
        self._pos_slider = None
        self._pos_text = None
        self._dur_text = None
        self._play_btn = None
        self._prev_view_mode = None
        self._last_lyrics_idx = -1
        self._cached_dur = 0
        
        # Lyrics sync state
        self._sync_active = False
        self._sync_track = None
        self._sync_temp_offset = 0
        self._seeking = False
        
        # Curved lyrics state
        self._lyrics_column = None
        self._lyrics_need_initial_scroll = False
        self._lyrics_user_scrolling = False
        self._lyrics_snap_timer = None
        self._lyrics_programmatic_scroll = False
        self._lyrics_current_idx = 0
        self._last_lyrics_progress = 0.0

        self._initialized = False
        self._rebuild()
        self._initialized = True

    def _get_app(self):
        """Get the application instance from the session store."""
        return self._page.session.store.get("app")

    def _get_player(self):
        """Get the audio player instance."""
        app = self._get_app()
        return app.audio_player if app else None

    def on_window_size_changed(self):
        """Handle window resize by rebuilding the player screen."""
        if not self._sync_active:
            self._rebuild()

    def cycle_view(self, e=None):
        """Cycle between cover and lyrics view modes."""
        modes = ["cover", "lyrics"]
        idx = (modes.index(self._view_mode) + 1) % 2 if self._view_mode in modes else 0
        self._view_mode = modes[idx]
        self._page.session.store.set("player_view", self._view_mode)
        self._rebuild()

    def toggle_queue(self, e=None):
        """Toggle the queue view on/off."""
        if self._view_mode == "queue":
            self._view_mode = self._prev_view_mode or "cover"
        else:
            self._prev_view_mode = self._view_mode
            self._view_mode = "queue"
        self._page.session.store.set("player_view", self._view_mode)
        self._rebuild()

    def refresh(self):
        """Force a complete rebuild of the player screen."""
        self._rebuild()

    def _progress_ratio(self, pos_ms: int, dur_ms: int) -> float:
        """Calculate progress as a ratio (0.0 to 1.0)."""
        max_val = max(dur_ms, 1)
        pos = max(0, min(pos_ms, max_val))
        return float(pos) / float(max_val)

    def refresh_position(self, pos_ms: int, dur_ms: int):
        """Update position display and progress bar efficiently.
        
        Also handles lyrics line highlighting and sync preview updates.
        
        Args:
            pos_ms: Current playback position in milliseconds.
            dur_ms: Total track duration in milliseconds.
        """
        max_val = max(dur_ms, 1)
        if self._pos_slider and not self._seeking:
            if max_val != getattr(self, "_cached_dur", 0):
                self._pos_slider.min = 0
                self._pos_slider.max = float(max_val)
                self._cached_dur = max_val
            self._pos_slider.value = float(max(0, min(pos_ms, max_val)))
            self._pos_slider.update()
            if self._pos_text:
                self._pos_text.value = format_duration(pos_ms)
                self._pos_text.update()
        if self._dur_text:
            self._dur_text.value = format_duration(dur_ms)
            self._dur_text.update()

        # Update sync preview if in sync mode
        if self._sync_active:
            self._refresh_sync_preview()

        # Update lyrics highlighting
        if self._view_mode == "lyrics":
            player = self._get_player()
            if player and player.queue:
                track = player.get_current_track()
                if track and track.lyrics and player.duration_ms > 0:
                    offset = track.lyrics_offset
                    adj_pos = pos_ms + offset
                    new_idx = 0
                    try:
                        data = getattr(self, '_lyrics_data', None)
                        if data and data.type == "timed":
                            for i, ln in enumerate(data.lines):
                                if (ln.time_ms or 0) <= adj_pos:
                                    new_idx = i
                                else:
                                    break
                            if getattr(self, '_lyrics_need_initial_scroll', False):
                                self._lyrics_need_initial_scroll = False
                                self._last_lyrics_idx = new_idx
                                self._lyrics_current_idx = new_idx
                            self._update_lyrics_styles(new_idx)
                    except Exception:
                        pass

        self._page.update()

    def refresh_play_state(self, is_playing: bool):
        """Update the play/pause button icon.
        
        Args:
            is_playing: True if currently playing, False if paused.
        """
        if self._play_btn:
            self._play_btn.icon = ft.Icons.PAUSE_ROUNDED if is_playing else ft.Icons.PLAY_ARROW_ROUNDED
            self._play_btn.update()

    def _rebuild(self):
        """Rebuild the entire player screen based on current state."""
        # Show sync content if in lyrics sync mode
        if self._sync_active:
            content = self._build_sync_content()
            self._inner.controls = [content]
            if self._initialized:
                self.update()
            return

        app = self._get_app()
        player = self._get_player()

        # Show empty state if no tracks loaded
        if not player or not player.queue:
            self._inner.controls = [
                ft.Container(
                    expand=True,
                alignment=ft.Alignment(-1, 0),
                    content=ft.Text(tr("noMediaSelected")),
                )
            ]
            if self._initialized:
                self.update()
            return

        track = player.get_current_track()
        meta = app.current_metadata if app else None
        is_desktop = (self._page.width or 0) > 800
        ly_mode = db.get_setting("lyrics_mode", "auto")
        use_curved = (ly_mode == "curved") or (ly_mode == "auto" and is_desktop)

        # Build background with blurred album art
        bg = self._build_background(track)
        content = self._build_main_content(track, meta, player, is_desktop, use_curved)

        self._inner.controls = [bg, content]
        if self._initialized:
            self.update()
        if getattr(self, '_lyrics_need_initial_scroll', False):
            self._schedule_initial_lyrics_scroll()

    def _build_background(self, track):
        """Build the player background with optional blur and global fallback."""
        blur_enabled = db.get_setting("blur_background", "true") == "true"
        blur_val = int(db.get_setting("blur_intensity", "30"))
        global_bg = db.get_setting("global_bg_path", "")
        bg_hidden = db.get_setting("global_bg_hidden", "false") == "true"

        src = None
        if track and track.art_uri:
            src = track.art_uri
        elif global_bg and os.path.isfile(global_bg) and not bg_hidden:
            src = global_bg

        arts = []
        if src:
            arts.append(
                ft.Container(
                    expand=True,
                    image=ft.DecorationImage(src=src, fit=ft.BoxFit.COVER),
                )
            )
            if blur_enabled:
                arts.append(
                    ft.Container(
                        expand=True,
                        blur=blur_val,
                    )
                )
        arts.append(
            ft.Container(
                expand=True,
                bgcolor=ft.Colors.with_opacity(0.65, ft.Colors.SURFACE),
            )
        )
        return ft.Stack(expand=True, controls=arts)

    def _build_main_content(self, track, meta, player, is_desktop, use_curved=False):
        """Build the main content area based on the current view mode.
        
        Args:
            track: Current track data.
            meta: Current track metadata.
            player: AudioPlayer instance.
            is_desktop: Whether running on a wide screen.
            use_curved: Whether to use curved lyrics mode.
        
        Returns:
            A Stack with the main content and overlay controls.
        """
        if self._view_mode == "cover":
            inner = self._build_cover_view(track, meta, player, is_desktop)
        elif self._view_mode == "lyrics":
            if is_desktop:
                inner = self._build_split_view(track, meta, player, "lyrics")
            else:
                inner = self._build_mobile_lyrics_layout(track, player, use_curved)
        else:
            inner = self._build_split_view(track, meta, player, "queue") if is_desktop else self._build_queue_view(player)

        # Top-right view toggle buttons
        top_right_controls = [
            ft.IconButton(
                icon=_get_view_icon(self._view_mode),
                icon_size=28,
                on_click=self.cycle_view,
                tooltip=_get_view_tooltip(self._view_mode),
            ),
        ]
        if is_desktop:
            top_right_controls.append(
                ft.IconButton(
                    icon=ft.Icons.QUEUE_MUSIC,
                    icon_size=28,
                    on_click=self.toggle_queue,
                    tooltip=tr("showCover") if self._view_mode == "queue" else tr("showQueue"),
                    icon_color=ft.Colors.PRIMARY if self._view_mode == "queue" else None,
                ),
            )

        return ft.Stack(
            expand=True,
            controls=[
                inner,
                ft.Container(
                    left=4, top=4,
                    content=ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_size=24,
                        on_click=lambda _: self._page.run_task(self._page.push_route, "/library"),
                        tooltip=tr("back"),
                    ),
                ),
                ft.Container(
                    right=0, top=0,
                    padding=ft.Padding(0, 2, 2, 0),
                    content=ft.Row(
                        tight=True,
                        controls=top_right_controls,
                    ),
                ),
            ],
        )

    def _build_split_view(self, track, meta, player, right_mode):
        """Build desktop split view with cover on left and content on right.
        
        Args:
            track: Current track data.
            meta: Current track metadata.
            player: AudioPlayer instance.
            right_mode: Content for right panel ("lyrics" or "queue").
        
        Returns:
            A Row with cover view and lyrics/queue side by side.
        """
        left = ft.Container(
            content=self._build_cover_view(track, meta, player, is_desktop=True, compact=True),
            expand=3,
        )
        if right_mode == "lyrics":
            right = ft.Container(content=self._build_lyrics_view(track, player, use_curved=True), expand=4)
        else:
            right = ft.Container(content=self._build_queue_view(player), expand=4)
        return ft.Row(expand=True, spacing=0, controls=[left, right])

    def _build_mobile_lyrics_layout(self, track, player, use_curved=False):
        """Build mobile lyrics layout with lyrics on top and controls at bottom.
        
        Args:
            track: Current track data.
            player: AudioPlayer instance.
            use_curved: Whether to use curved lyrics mode.
        
        Returns:
            A Column with lyrics and bottom control panel.
        """
        lyrics_content = self._build_lyrics_view(track, player, use_curved)

        progress = self._build_progress_slider(player)
        self._play_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED if player.is_playing else ft.Icons.PLAY_ARROW_ROUNDED,
            icon_size=36,
            on_click=lambda e: player.toggle_play_pause(),
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
        )
        from logic.play_mode import get_play_mode_icon as _gpm
        _pm_icon, _pm_color = _gpm(self._page)
        ctrl_row = ft.Row(
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.IconButton(_pm_icon, icon_color=_pm_color, on_click=lambda e: (cycle_play_mode(self._page), self._page.update())),
                ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_size=28, on_click=lambda e: player.previous()),
                self._play_btn,
                ft.IconButton(ft.Icons.SKIP_NEXT, icon_size=28, on_click=lambda e: player.next()),
                ft.IconButton(
                    icon=ft.Icons.QUEUE_MUSIC,
                    icon_size=24,
                    on_click=self.toggle_queue,
                    tooltip=tr("showCover") if self._view_mode == "queue" else tr("showQueue"),
                    icon_color=ft.Colors.PRIMARY if self._view_mode == "queue" else None,
                ),
            ],
        )
        bottom_controls = ft.Container(
            padding=ft.Padding(16, 12, 16, 12),
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.SURFACE),
            border_radius=ft.border_radius.BorderRadius(16, 16, 0, 0),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[progress, ctrl_row],
            ),
        )
        return ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(expand=True, content=lyrics_content),
                bottom_controls,
            ],
        )

    def _build_volume_row(self, player):
        """Build the volume control slider row.
        
        Args:
            player: AudioPlayer instance.
        
        Returns:
            A Row with volume icon and slider.
        """
        pw = self._page.width or 400
        is_desktop = pw > 800
        if is_desktop:
            vol_w = max(80, int((min(400, pw - 80)) * 0.85))
            return ft.Row(
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.VOLUME_UP, size=20, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                    ft.Container(
                        width=vol_w,
                        content=ft.Slider(
                            value=player.volume * 100, min=0, max=100, divisions=100,
                            on_change=lambda e: _safe_volume(e, player),
                        ),
                    ),
                ],
            )
        return ft.Row(
            tight=False,
            controls=[
                ft.Icon(ft.Icons.VOLUME_UP, size=20, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                ft.Container(
                    expand=True,
                    content=ft.Slider(
                        value=player.volume * 100, min=0, max=100, divisions=100,
                        on_change=lambda e: _safe_volume(e, player),
                    ),
                ),
            ],
        )

    def _build_cover_view(self, track, meta, player, is_desktop, compact=False):
        """Build the album art cover view with controls.
        
        Args:
            track: Current track data.
            meta: Current track metadata.
            player: AudioPlayer instance.
            is_desktop: Whether on a wide screen.
            compact: Whether to use compact sizing (for split view).
        
        Returns:
            A Container with album art, title, controls, and progress.
        """
        has_art = track and track.art_uri
        title = meta.title if meta and meta.title else (track.title if track else "")
        artist = meta.artist if meta and meta.artist else (track.artist or "")

        # Calculate art size based on screen
        if compact:
            art_size = 180
        elif is_desktop:
            art_size = min(360, int((self._page.width or 400) * 0.28))
        else:
            art_size = min(260, int((self._page.width or 400) - 80))

        art_content = ft.Image(
            src=track.art_uri, fit=ft.BoxFit.COVER,
            error_content=ft.Icon(ft.Icons.MUSIC_NOTE, size=art_size // 3, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
        ) if has_art else ft.Icon(ft.Icons.MUSIC_NOTE, size=art_size // 3, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE))

        art = ft.Container(
            width=art_size, height=art_size,
            border_radius=24,
            shadow=ft.BoxShadow(blur_radius=20, color=ft.Colors.with_opacity(0.3, ft.Colors.SHADOW)),
            content=art_content,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        self._play_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED if player.is_playing else ft.Icons.PLAY_ARROW_ROUNDED,
            icon_size=48,
            on_click=lambda e: player.toggle_play_pause(),
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
        )

        from logic.play_mode import get_play_mode_icon as _gpm
        _pm_icon, _pm_color = _gpm(self._page)
        ctrl_row = ft.Row(
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.IconButton(_pm_icon, icon_color=_pm_color, on_click=lambda e: (cycle_play_mode(self._page), self._page.update())),
                ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_size=32, on_click=lambda e: player.previous()),
                ft.Container(
                    padding=ft.Padding(12, 0, 12, 0),
                    content=self._play_btn,
                ),
                ft.IconButton(ft.Icons.SKIP_NEXT, icon_size=32, on_click=lambda e: player.next()),
            ],
        )

        progress = self._build_progress_slider(player)

        if is_desktop:
            col = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(alignment=ft.Alignment(0, 0), content=art),
                    ft.Container(height=12),
                    ft.Text(title, size=18 if compact else 22, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(artist, size=14 if compact else 16, color=ft.Colors.PRIMARY,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=12),
                    progress,
                    ctrl_row,
                    ft.Row(
                        tight=True,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.LYRICS,
                                icon_size=20,
                                on_click=lambda e: self._show_lyrics_menu(track, player),
                                tooltip=tr("lyricsOptions"),
                            ),
                            self._build_volume_row(player),
                        ],
                    ),
                    ft.Container(height=16),
                ],
            )
        else:
            col = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Container(alignment=ft.Alignment(0, 0), content=art),
                    ft.Container(height=12),
                    ft.Container(alignment=ft.Alignment(0, 0), content=ft.Text(
                        title, size=18 if compact else 22, weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    )),
                    ft.Container(alignment=ft.Alignment(0, 0), content=ft.Text(
                        artist, size=14 if compact else 16, color=ft.Colors.PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    )),
                    ft.Container(height=12),
                    progress,
                    ft.Container(alignment=ft.Alignment(0, 0), content=ctrl_row),
                    ft.Container(
                        content=ft.Row(
                            tight=False,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.LYRICS,
                                    icon_size=20,
                                    on_click=lambda e: self._show_lyrics_menu(track, player),
                                    tooltip=tr("lyricsOptions"),
                                ),
                                ft.Container(expand=True, content=self._build_volume_row(player)),
                            ],
                        ),
                    ),
                    ft.Container(height=16),
                ],
            )

        return ft.Container(
            expand=True,
            padding=ft.Padding(32, 0, 32, 0) if not compact else ft.Padding(16, 0, 16, 0),
            content=col,
        )

    def _build_progress_slider(self, player):
        """Build the progress slider with time labels.
        
        Shows an indeterminate ProgressBar while loading, then switches to
        a Slider once the audio duration is known and playback is ready.
        
        Args:
            player: AudioPlayer instance.
        
        Returns:
            A Column with slider/loading bar and position/duration labels.
        """
        is_desktop = (self._page.width or 400) > 800
        bar_width = min(400, self._page.width - (64 if not is_desktop else 80)) if self._page.width else 400
        if player.loading or self._pos_slider is None and player.duration_ms <= 0:
            self._pos_slider = None
            if is_desktop:
                return ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=bar_width,
                            height=24,
                            content=ft.ProgressBar(
                                color=ft.Colors.PRIMARY,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            ),
                        ),
                        ft.Row(
                            width=bar_width,
                            tight=True,
                            controls=[
                                ft.Text("--:--", size=12),
                                ft.Container(expand=True),
                                ft.Text("--:--", size=12),
                            ],
                        ),
                    ],
                )
            return ft.Column(
                tight=True,
                controls=[
                    ft.ProgressBar(
                        color=ft.Colors.PRIMARY,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    ),
                    ft.Row(
                        tight=True,
                        controls=[
                            ft.Text("--:--", size=12),
                            ft.Container(expand=True),
                            ft.Text("--:--", size=12),
                        ],
                    ),
                ],
            )
        max_val = max(player.duration_ms, 1)
        pos_val = max(0, min(player.position_ms, max_val))
        self._cached_dur = max_val
        def _on_seek_start(e: ft.ControlEvent) -> None:
            self._seeking = True
        def _on_seek_change(e: ft.ControlEvent) -> None:
            if self._pos_text:
                self._pos_text.value = format_duration(int(e.control.value))
                self._pos_text.update()
        def _on_seek_end(e: ft.ControlEvent) -> None:
            _safe_seek(e, player)
            self._seeking = False
        slider_width = bar_width if is_desktop else None
        self._pos_slider = ft.Slider(
            value=float(pos_val),
            min=0,
            max=float(max_val),
            divisions=1000,
            width=slider_width,
            height=24,
            active_color=ft.Colors.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
            thumb_color=ft.Colors.WHITE,
            overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            on_change_start=_on_seek_start,
            on_change=_on_seek_change,
            on_change_end=_on_seek_end,
        )
        self._pos_text = ft.Text(format_duration(pos_val), size=12)
        self._dur_text = ft.Text(format_duration(player.duration_ms), size=12)
        if is_desktop:
            return ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self._pos_slider,
                    ft.Row(
                        width=bar_width,
                        tight=True,
                        controls=[
                            self._pos_text,
                            ft.Container(expand=True),
                            self._dur_text,
                        ],
                    ),
                ],
            )
        return ft.Column(
            tight=True,
            controls=[
                self._pos_slider,
                ft.Row(
                    tight=True,
                    controls=[
                        self._pos_text,
                        ft.Container(expand=True),
                        self._dur_text,
                    ],
                ),
            ],
        )

    def _build_lyrics_view(self, track, player, use_curved=False):
        """Build the lyrics display view.
        
        Args:
            track: Current track data.
            player: AudioPlayer instance.
            use_curved: Whether to use curved lyrics mode.
        
        Returns:
            A lyrics display widget (curved, flat, or plain).
        """
        if track is None or not track.lyrics:
            return ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(tr("noLyricsAvailable")),
                        ft.Container(height=16),
                        ft.TextButton(tr("fetchLyrics"), icon=ft.Icons.DOWNLOAD, on_click=lambda e: self._show_lyrics_options(track, player)),
                    ],
                ),
            )

        try:
            data = lyrics_from_json(track.lyrics)
        except Exception:
            return ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(tr("errorLoadingLyrics").replace("{}", "parse error")),
            )

        if data.type == "timed":
            lyrics_content = self._build_timed_lyrics(data, player, track.lyrics_offset, use_curved)
        else:
            lyrics_content = self._build_plain_lyrics(data)

        return lyrics_content

    def _show_lyrics_menu(self, track, player):
        """Show the lyrics options bottom sheet.
        
        Options: Fetch online, Manual import, Clear lyrics, Adjust offset
        """
        def do_fetch(e):
            self._page.pop_dialog()
            self._show_fetch_lyrics(track, player)

        def do_manual(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_lyrics_file, track)

        def do_clear(e):
            self._page.pop_dialog()
            self._clear_lyrics(track)

        def do_offset(e):
            self._page.pop_dialog()
            self._sync_active = True
            self._sync_track = track
            self._sync_temp_offset = track.lyrics_offset
            self._rebuild()

        items = [
            ft.ListTile(leading=ft.Icon(ft.Icons.SEARCH), title=ft.Text(tr("fetchLyrics")), on_click=do_fetch),
            ft.ListTile(leading=ft.Icon(ft.Icons.FILE_UPLOAD), title=ft.Text(tr("manualImport")), on_click=do_manual),
        ]
        if track.lyrics:
            items.append(ft.ListTile(leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED), title=ft.Text(tr("clear"), color=ft.Colors.RED), on_click=do_clear))
        items.append(ft.ListTile(leading=ft.Icon(ft.Icons.TUNE), title=ft.Text(tr("offsetMs")), on_click=do_offset))

        bs = ft.BottomSheet(content=ft.Column(tight=True, controls=items))
        self._page.show_dialog(bs)

    def _build_sync_content(self):
        """Build the lyrics synchronization adjustment interface.
        
        Provides controls for fine-tuning lyrics offset with
        real-time preview of the adjusted lyrics.
        
        Returns:
            A Container with sync controls and lyrics preview.
        """
        player = self._get_player()
        if not player:
            return ft.Container(expand=True, content=ft.Text(tr("noMediaSelected")))
        track = self._sync_track if self._sync_track else player.get_current_track()
        if not track:
            return ft.Container(expand=True, content=ft.Text(tr("noLyricsAvailable")))
        max_w = max(480, int((self._page.width or 400) * 0.4))
        offset_text = ft.Text(str(self._sync_temp_offset), size=32,
                              weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
        fine_slider = ft.Slider(min=-5000, max=5000, divisions=100,
                                value=float(self._sync_temp_offset), on_change=None)
        play_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED if player.is_playing else ft.Icons.PLAY_ARROW_ROUNDED,
            icon_size=36, on_click=lambda e: player.toggle_play_pause())
        max_val = max(float(player.duration_ms), 1)
        self._pos_slider = ft.Slider(
            value=float(player.position_ms),
            min=0,
            max=max_val,
            width=max_w,
            height=24,
            active_color=ft.Colors.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
            thumb_color=ft.Colors.WHITE,
            overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            on_change=lambda e: player.seek(int(e.control.value)),
        )
        self._pos_text = ft.Text(format_duration(player.position_ms), size=12)
        self._dur_text = ft.Text(format_duration(player.duration_ms), size=12)
        self._play_btn = play_btn

        def update_offset(v):
            self._sync_temp_offset = v
            offset_text.value = str(v)
            offset_text.update()
            fine_slider.value = float(v)
            fine_slider.update()
            self._refresh_sync_preview()

        def on_slider(e):
            update_offset(int(e.control.value))
        fine_slider.on_change = on_slider

        def adjust(delta):
            update_offset(self._sync_temp_offset + delta)

        preview_content = self._build_sync_lyrics_preview(track, player, self._sync_temp_offset)

        self._sync_preview_container = preview_content
        if preview_content and hasattr(self, '_sync_preview_listview') and self._sync_preview_listview:
            try:
                self._sync_preview_listview.scroll_to(key=f"sync_line_{self._sync_preview_current_idx}", duration=200)
            except Exception:
                pass

        inner = [
            ft.Text(tr("offsetMs"), size=14, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
            offset_text,
            ft.Row(tight=True, alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.IconButton(ft.Icons.FAST_REWIND, icon_size=20, tooltip="-100ms", on_click=lambda e: adjust(-100)),
                ft.IconButton(ft.Icons.KEYBOARD_ARROW_LEFT, icon_size=20, tooltip="-10ms", on_click=lambda e: adjust(-10)),
                ft.TextButton(tr("reset"), on_click=lambda e: adjust(-self._sync_temp_offset)),
                ft.IconButton(ft.Icons.KEYBOARD_ARROW_RIGHT, icon_size=20, tooltip="+10ms", on_click=lambda e: adjust(10)),
                ft.IconButton(ft.Icons.FAST_FORWARD, icon_size=20, tooltip="+100ms", on_click=lambda e: adjust(100)),
            ]),
            ft.Text(tr("fineAdjustment"), size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
            fine_slider,
            ft.Divider(height=1),
            ft.Row(tight=True, alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_size=28, on_click=lambda e: player.previous()),
                play_btn,
                ft.IconButton(ft.Icons.SKIP_NEXT, icon_size=28, on_click=lambda e: player.next()),
            ]),
            self._pos_slider,
            ft.Row(tight=True, controls=[self._pos_text, ft.Container(expand=True), self._dur_text]),
            ft.Divider(height=1),
            ft.Text(tr("liveLyricsSync"), size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
            preview_content if preview_content else ft.Text(tr("noLyricsAvailable")),
        ]

        return ft.Container(
            expand=True, bgcolor=ft.Colors.SURFACE,
            content=ft.Column(expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Row(tight=True, controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=24, on_click=lambda e: self._on_sync_back()),
                    ft.Container(expand=True),
                    ft.Text(tr("liveLyricsSync"), size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.CHECK, icon_size=24, on_click=lambda e: self._on_sync_save()),
                ]),
                ft.Divider(height=1),
                ft.Container(expand=True, content=ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, controls=[
                    ft.Container(width=max_w, content=ft.Column(tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, controls=inner)),
                ])),
            ]),
        )

    def _on_sync_back(self):
        """Cancel lyrics sync and return to player view."""
        self._sync_active = False
        self._rebuild()

    def _on_sync_save(self):
        """Save the lyrics offset and return to player view."""
        track = self._sync_track
        if track:
            adj = self._sync_temp_offset - track.lyrics_offset
            if adj != 0:
                from data import track_repository as trepo
                trepo.update_lyrics_offset(track.id, self._sync_temp_offset)
                track.lyrics_offset = self._sync_temp_offset
                try:
                    player = self._get_player()
                    if player and hasattr(player, 'current_track') and player.current_track:
                        player.current_track.lyrics_offset = self._sync_temp_offset
                except AttributeError:
                    pass
        self._sync_active = False
        self._rebuild()

    def _build_sync_lyrics_preview(self, track, player, temp_offset):
        """Build a preview of lyrics with the current sync offset.
        
        Args:
            track: Current track data.
            player: AudioPlayer instance.
            temp_offset: Temporary offset being tested.
        
        Returns:
            A Container with scrollable lyrics preview, or None.
        """
        if not track or not track.lyrics:
            return None
        try:
            data = lyrics_from_json(track.lyrics)
        except Exception:
            return None
        if data.type != "timed":
            return None
        pos = player.position_ms + temp_offset
        current_idx = 0
        for i, ln in enumerate(data.lines):
            if (ln.time_ms or 0) <= pos:
                current_idx = i
            else:
                break
        items = []
        self._sync_preview_lines = []
        self._sync_preview_data = data
        for i, ln in enumerate(data.lines):
            is_active = i == current_idx
            progress = 0.0
            if is_active:
                s = ln.time_ms or 0
                e = (data.lines[i + 1].time_ms or s) if i < len(data.lines) - 1 else player.duration_ms
                if e > s:
                    progress = max(0.0, min(1.0, (pos - s) / (e - s)))
            container = ft.Container(key=f"sync_line_{i}", padding=ft.Padding(16, 4, 16, 4))
            self._set_sync_line_content(container, ln, is_active, progress)
            self._sync_preview_lines.append((i, container))
            items.append(container)
        self._sync_preview_current_idx = current_idx
        self._sync_preview_listview = ft.Column(
            controls=items,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        return ft.Container(
            height=300,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                left=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
            ),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=self._sync_preview_listview,
        )

    @staticmethod
    def _set_sync_line_content(container, ln, is_active, progress):
        """Set the content of a sync preview line with gradient highlighting.
        
        Args:
            container: The Container to update.
            ln: The LyricsLine data.
            is_active: Whether this is the current line.
            progress: Progress within the line (0.0 to 1.0).
        """
        if is_active and 0 < progress < 1:
            container.content = ft.ShaderMask(
                shader=ft.LinearGradient(
                    begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                    colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)],
                    stops=[progress, progress],
                ),
                content=ft.Text(ln.text, size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                blend_mode=ft.BlendMode.SRC_IN,
            )
        else:
            container.content = ft.Text(
                ln.text, size=18 if is_active else 14,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                text_align=ft.TextAlign.CENTER,
            )

    def _refresh_sync_preview(self):
        """Refresh the lyrics preview in sync mode with current playback position."""
        if not self._sync_active:
            return
        player = self._get_player()
        if not player:
            return
        track = player.get_current_track()
        if not track or not track.lyrics:
            return
        data = getattr(self, '_sync_preview_data', None)
        if not data:
            try:
                data = lyrics_from_json(track.lyrics)
            except Exception:
                return
        if data.type != "timed" or not data.lines:
            return
        pos = player.position_ms + self._sync_temp_offset
        new_idx = 0
        for i, ln in enumerate(data.lines):
            if (ln.time_ms or 0) <= pos:
                new_idx = i
            else:
                break
        old_idx = getattr(self, '_sync_preview_current_idx', -1)
        lines = getattr(self, '_sync_preview_lines', [])
        listview = getattr(self, '_sync_preview_listview', None)

        if new_idx != old_idx or not lines:
            self._sync_preview_current_idx = new_idx
            for line_idx, container in lines:
                is_active = line_idx == new_idx
                progress = 0.0
                if is_active:
                    s = data.lines[new_idx].time_ms or 0
                    e = (data.lines[new_idx + 1].time_ms or s) if new_idx < len(data.lines) - 1 else player.duration_ms
                    if e > s:
                        progress = max(0.0, min(1.0, (pos - s) / (e - s)))
                self._set_sync_line_content(container, data.lines[line_idx], is_active, progress)
                try:
                    container.update()
                except RuntimeError:
                    pass
            if listview:
                try:
                    listview.scroll_to(key=f"sync_line_{new_idx}", duration=300)
                except Exception:
                    pass
        else:
            progress = 0.0
            s = data.lines[new_idx].time_ms or 0
            e = (data.lines[new_idx + 1].time_ms or s) if new_idx < len(data.lines) - 1 else player.duration_ms
            if e > s:
                progress = max(0.0, min(1.0, (pos - s) / (e - s)))
            for line_idx, container in lines:
                if line_idx == new_idx:
                    self._set_sync_line_content(container, data.lines[new_idx], True, progress)
                    try:
                        container.update()
                    except RuntimeError:
                        pass
                    break

    def _show_lyrics_options(self, track, player):
        """Show lyrics management options for a track without lyrics."""
        def do_refetch(e):
            self._page.pop_dialog()
            self._show_fetch_lyrics(track, player)

        def do_clear(e):
            self._page.pop_dialog()
            self._clear_lyrics(track)

        def do_manual_import(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_lyrics_file, track)

        def do_adjust_offset(e):
            self._page.pop_dialog()

        items = []
        if track.lyrics:
            items.append(ft.ListTile(leading=ft.Icon(ft.Icons.REFRESH), title=ft.Text(tr("refetch")), on_click=do_refetch))
            items.append(ft.ListTile(leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED), title=ft.Text(tr("clear"), color=ft.Colors.RED), on_click=do_clear))
        else:
            items.append(ft.ListTile(leading=ft.Icon(ft.Icons.SEARCH), title=ft.Text(tr("fetchLyrics")), on_click=do_refetch))
        items.append(ft.ListTile(leading=ft.Icon(ft.Icons.FILE_UPLOAD), title=ft.Text(tr("manualImport")), on_click=do_manual_import))

        bs = ft.BottomSheet(content=ft.Column(tight=True, controls=items))
        self._page.show_dialog(bs)

    def _show_fetch_lyrics(self, track, player):
        """Show lyrics source selection for online fetching."""
        def search_musixmatch(e):
            self._page.pop_dialog()
            self._search_lyrics_online(track, "musixmatch")

        def search_netease(e):
            self._page.pop_dialog()
            self._search_lyrics_online(track, "netease")

        def search_lrclib(e):
            self._page.pop_dialog()
            self._search_lyrics_online(track, "lrclib")

        bs = ft.BottomSheet(
            content=ft.Column(
                tight=True,
                controls=[
                    ft.ListTile(leading=ft.Icon(ft.Icons.SEARCH), title=ft.Text(tr("musixmatch")), on_click=search_musixmatch),
                    ft.ListTile(leading=ft.Icon(ft.Icons.SEARCH), title=ft.Text(tr("netease")), on_click=search_netease),
                    ft.ListTile(leading=ft.Icon(ft.Icons.SEARCH), title=ft.Text(tr("lrclib")), on_click=search_lrclib),
                ],
            ),
        )
        self._page.show_dialog(bs)

    def _search_lyrics_online(self, track, source):
        """Search and fetch lyrics from an online source.
        
        Supported sources: lrclib, netease
        
        Args:
            track: The track to fetch lyrics for.
            source: The lyrics source identifier.
        """
        query = f"{track.artist or ''} {track.title or ''}".strip()
        if not query:
            self._page.show_dialog(ft.SnackBar(ft.Text(tr("error").replace("{}", "No track info"))))
            return
        try:
            import urllib.request
            import urllib.parse
            import json as _json
            url = ""
            if source == "lrclib":
                safe = urllib.parse.quote(query)
                url = f"https://lrclib.net/api/search?q={safe}"
            elif source == "netease":
                safe = urllib.parse.quote(query)
                url = f"https://music.163.com/api/search/get?type=1&s={safe}"
            if not url:
                self._page.show_dialog(ft.SnackBar(ft.Text(tr("noLyricsAvailable"))))
                return
            req = urllib.request.Request(url, headers={"User-Agent": "GroovyBox/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            lyrics_text = None
            if source == "lrclib" and isinstance(data, list) and data:
                lyrics_text = data[0].get("syncedLyrics") or data[0].get("plainLyrics")
            elif source == "netease":
                songs = data.get("result", {}).get("songs", [])
                if songs:
                    sid = songs[0]["id"]
                    lyric_url = f"https://music.163.com/api/song/lyric?os=pc&id={sid}&lv=-1&kv=-1&tv=-1"
                    lreq = urllib.request.Request(lyric_url, headers={"User-Agent": "GroovyBox/1.0"})
                    with urllib.request.urlopen(lreq, timeout=10) as lresp:
                        ldata = _json.loads(lresp.read().decode("utf-8"))
                    lyric_str = ldata.get("lrc", {}).get("lyric", "")
                    if lyric_str.strip():
                        lyrics_text = lyric_str
            if lyrics_text:
                from logic.lyrics_parser import parse, lyrics_to_json
                lyr_data = parse(lyrics_text, f"{track.title}.lrc")
                json_str = lyrics_to_json(lyr_data)
                trepo.update_lyrics(track.id, json_str)
                player = self._get_player()
                if player and 0 <= player.current_index < len(player.queue):
                    queued = player.queue[player.current_index]
                    if queued.id == track.id:
                        queued.lyrics = json_str
                self._rebuild()
                self._page.show_dialog(ft.SnackBar(ft.Text(tr("importedLyricsLines").replace("{}", str(len(lyr_data.lines))).replace("{}", track.title or ""))))
            else:
                self._page.show_dialog(ft.SnackBar(ft.Text(tr("noLyricsAvailable"))))
        except Exception as ex:
            logger.error(f"Lyrics search failed: {ex}")
            self._page.show_dialog(ft.SnackBar(ft.Text(tr("error").replace("{}", str(ex)))))

    def _clear_lyrics(self, track):
        """Remove lyrics from a track."""
        trepo.update_lyrics(track.id, None)
        player = self._get_player()
        if player and hasattr(player, 'current_track') and player.current_track and player.current_track.id == track.id:
            player.current_track.lyrics = None
        self._rebuild()

    async def _import_lyrics_file(self, track):
        """Import lyrics from a file picker dialog.
        
        Args:
            track: The track to import lyrics for.
        """
        from logic.file_dialog import pick_files
        from data.track_repository import LYRICS_EXTENSIONS
        paths = await pick_files(self._page, title=tr("manualImport"), extensions=list(LYRICS_EXTENSIONS))
        if not paths:
            return
        from logic.encoding_helper import read_with_encoding
        from logic.lyrics_parser import parse, lyrics_to_json
        content = read_with_encoding(paths[0])
        ldata = parse(content, os.path.basename(paths[0]))
        json_str = lyrics_to_json(ldata)
        trepo.update_lyrics(track.id, json_str)
        player = self._get_player()
        if player and 0 <= player.current_index < len(player.queue):
            queued = player.queue[player.current_index]
            if queued.id == track.id:
                queued.lyrics = json_str
        self._rebuild()
        self._page.show_dialog(ft.SnackBar(ft.Text(tr("importedLyricsLines").replace("{}", str(len(ldata.lines))).replace("{}", track.title or ""))))

    # Curved lyrics constants
    _LY_HALF = 5          # Number of lines above/below center
    _LY_ARC = 0.45        # Arc rotation intensity
    _LY_ITEM_H = 40       # Height per lyrics line
    _LY_ANIM_MS = 400     # Animation duration in ms
    _LY_ANIM_CURVE = ft.AnimationCurve.EASE_OUT_CUBIC

    @staticmethod
    def _estimate_text_width(text, font_size):
        """Estimate text pixel width (CJK chars count as full-width)."""
        w = 0.0
        for ch in text:
            if ord(ch) > 0x7F:
                w += font_size * 1.0
            else:
                w += font_size * 0.55
        return w

    def _build_scrolling_lyric_line(self, text, font_size, font_weight, color,
                                     container_width, progress, text_align):
        """Build a horizontally scrolling lyric line for long text.
        
        Args:
            text: The lyrics text.
            font_size: Font size in pixels.
            font_weight: Font weight.
            color: Text color.
            container_width: Available width.
            progress: Scroll progress (0.0 to 1.0).
            text_align: Text alignment.
        
        Returns:
            A Container with scrolling text if overflow, otherwise static.
        """
        text_w = self._estimate_text_width(text, font_size)
        overflow_px = max(0.0, text_w - container_width)

        if overflow_px > 0 and 0 < progress < 1:
            scroll_px = overflow_px * progress
            return ft.Container(
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                width=container_width,
                content=ft.Stack(
                    controls=[
                        ft.Container(
                            left=-scroll_px,
                            content=ft.Text(
                                text,
                                size=font_size,
                                weight=font_weight,
                                no_wrap=True,
                                text_align=text_align,
                            ),
                        ),
                    ],
                ),
            )
        else:
            return ft.Container(
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                width=container_width,
                content=ft.Text(
                    text,
                    size=font_size,
                    weight=font_weight,
                    color=color,
                    no_wrap=True,
                    text_align=text_align,
                ),
            )

    def _style_lyric_line(self, container, i, current_idx):
        """Apply curved styling to a lyrics line based on distance from center.
        
        Args:
            container: The Container to style.
            i: Index of this line.
            current_idx: Index of the currently active line.
        """
        half = self._LY_HALF
        arc = self._LY_ARC
        dist = abs(i - current_idx)
        in_window = dist <= half
        direction = -1 if i < current_idx else 1
        t = min(dist / half, 1.0) if half > 0 else 0
        if in_window:
            rotate_val = direction * t * arc
            v_pivot = direction * t * 2 if i != current_idx else 0
            h_off = int(200 * t * t)
            container.rotate = ft.Rotate(rotate_val, ft.Alignment(-1.2, v_pivot))
            container.padding = ft.Padding(28 - h_off, 0, 28, 0)
            container.opacity = 1.0 if i == current_idx else max(0.25, 1.0 - t * 0.6)
        else:
            container.rotate = ft.Rotate(0, ft.Alignment(-1.2, 0))
            container.padding = ft.Padding(32, 0, 32, 0)
            container.opacity = 0.0
        txt = container.content
        alpha = max(0.4, 0.85 - t * 0.45)
        txt.size = 16
        txt.weight = ft.FontWeight.NORMAL
        txt.color = ft.Colors.with_opacity(alpha, ft.Colors.ON_SURFACE)

    def _build_visible_lines(self, data, viewport_center, highlight_idx, player, max_w, text_align, progress=0.0):
        """Build centered visible lyrics lines with curved styling.
        
        Args:
            data: LyricsData object.
            viewport_center: Index of the center line.
            highlight_idx: Index of the highlighted (active) line.
            player: AudioPlayer instance.
            max_w: Maximum width for lyrics text.
            text_align: Text alignment.
            progress: Progress within the highlighted line (0.0 to 1.0).
        
        Returns:
            List of controls for the lyrics column.
        """
        half = self._LY_HALF
        total = len(data.lines)
        self._lyrics_widgets = []
        above_count = min(half, viewport_center)
        below_count = min(half, total - 1 - viewport_center)
        start_idx = viewport_center - above_count
        end_idx = viewport_center + below_count + 1

        controls = []
        controls.append(ft.Container(height=self._LY_ITEM_H * (half - above_count + 1)))

        for i in range(start_idx, end_idx):
            line = data.lines[i]
            container = ft.Container(
                height=self._LY_ITEM_H,
                width=max_w,
                alignment=ft.Alignment(0, 0),
                animate_rotation=ft.Animation(self._LY_ANIM_MS, self._LY_ANIM_CURVE),
                animate_opacity=ft.Animation(self._LY_ANIM_MS, self._LY_ANIM_CURVE),
                animate_margin=ft.Animation(self._LY_ANIM_MS, self._LY_ANIM_CURVE),
                on_click=lambda e, ts=line.time_ms: player.seek(ts) if ts else None,
                content=ft.Text(
                    line.text,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=text_align,
                ),
            )
            self._style_lyric_line(container, i, viewport_center)
            if i == highlight_idx:
                line_text = line.text
                text_w = self._estimate_text_width(line_text, 19)
                adj_progress = progress
                if text_w > max_w:
                    adj_progress = min(1.0, progress * (text_w / max_w))

                scroll_widget = self._build_scrolling_lyric_line(
                    line_text, 19, ft.FontWeight.BOLD, ft.Colors.PRIMARY,
                    max_w, adj_progress, text_align,
                )
                container.content = ft.ShaderMask(
                    shader=ft.LinearGradient(
                        begin=ft.Alignment(-1, 0),
                        end=ft.Alignment(1, 0),
                        colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)],
                        stops=[adj_progress, adj_progress],
                    ),
                    content=scroll_widget,
                    blend_mode=ft.BlendMode.SRC_IN,
                )
            self._lyrics_widgets.append(container)
            controls.append(container)

        controls.append(ft.Container(height=self._LY_ITEM_H * (half - below_count + 1)))
        return controls

    def _build_curved_listview(self, data, current_idx, player, max_w, text_align):
        """Build the curved lyrics view with gesture controls.
        
        Args:
            data: LyricsData object.
            current_idx: Initial active line index.
            player: AudioPlayer instance.
            max_w: Maximum width for lyrics.
            text_align: Text alignment.
        
        Returns:
            A GestureDetector with curved lyrics display.
        """
        self._lyrics_data_lines = data.lines
        self._lyrics_current_idx = current_idx
        self._lyrics_max_w = max_w
        self._lyrics_text_align = text_align
        self._lyrics_player = player
        self._lyrics_drag_accum = 0.0

        controls = self._build_visible_lines(data, current_idx, current_idx, player, max_w, text_align)

        column = ft.Column(
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=controls,
        )
        self._lyrics_column = column

        padded_column = ft.Container(
            padding=ft.Padding(32, 0, 32, 0),
            content=column,
        )

        switcher = ft.AnimatedSwitcher(
            content=padded_column,
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=300,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            expand=True,
        )
        self._lyrics_switcher = switcher

        gesture = ft.GestureDetector(
            expand=True,
            mouse_cursor=ft.MouseCursor.BASIC,
            content=switcher,
            on_scroll=self._on_lyrics_wheel,
            on_vertical_drag_start=lambda e: None,
            on_vertical_drag_update=self._on_lyrics_drag_update,
            on_vertical_drag_end=self._on_lyrics_drag_end,
        )
        return gesture

    def _rebuild_lyrics_column(self, viewport_center, highlight_idx, progress=0.0):
        """Rebuild the curved lyrics column with updated styling."""
        controls = self._build_visible_lines(
            self._lyrics_data_obj, viewport_center, highlight_idx,
            self._lyrics_player, self._lyrics_max_w, self._lyrics_text_align,
            progress=progress,
        )
        new_column = ft.Column(
            controls=controls,
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._lyrics_column = new_column
        self._lyrics_switcher.content = ft.Container(
            padding=ft.Padding(48, 0, 16, 0),
            content=new_column,
        )
        try:
            self._lyrics_switcher.update()
        except RuntimeError:
            pass

    def _on_lyrics_wheel(self, e: ft.ScrollEvent):
        """Handle mouse wheel events for lyrics scrolling."""
        delta_y = e.scroll_delta.y
        if delta_y > 10:
            self._step_lyrics(1)
        elif delta_y < -10:
            self._step_lyrics(-1)

    def _on_lyrics_drag_update(self, e):
        """Handle touch drag events for lyrics scrolling."""
        self._lyrics_user_scrolling = True
        self._lyrics_drag_accum += e.local_delta.y
        stride = self._LY_ITEM_H
        while self._lyrics_drag_accum >= stride:
            self._step_lyrics(1)
            self._lyrics_drag_accum -= stride
        while self._lyrics_drag_accum <= -stride:
            self._step_lyrics(-1)
            self._lyrics_drag_accum += stride

    def _on_lyrics_drag_end(self, e):
        """Handle end of touch drag - reset accumulator and schedule snap."""
        self._lyrics_drag_accum = 0.0
        self._schedule_snap()

    def _step_lyrics(self, direction):
        """Step to the next/previous lyrics line.
        
        Args:
            direction: 1 for next, -1 for previous.
        """
        self._lyrics_user_scrolling = True
        lines = getattr(self, '_lyrics_data_lines', None)
        if lines is None:
            return
        total = len(lines)
        new_idx = max(0, min(self._lyrics_current_idx + direction, total - 1))
        if new_idx == self._lyrics_current_idx:
            return
        self._lyrics_current_idx = new_idx
        self._rebuild_lyrics_column(new_idx, self._last_lyrics_idx)
        self._schedule_snap()

    def _schedule_snap(self):
        """Reset the snap-back timer for returning to the active lyrics line."""
        if self._lyrics_snap_timer:
            self._lyrics_snap_timer.cancel()
        self._lyrics_snap_timer = threading.Timer(1.0, self._snap_to_nearest_line)
        self._lyrics_snap_timer.daemon = True
        self._lyrics_snap_timer.start()

    def _snap_to_nearest_line(self):
        """Clear user scrolling flag to resume auto-tracking."""
        self._lyrics_user_scrolling = False

    def _on_flat_lyrics_scroll(self, e):
        """Detect user scroll in flat lyrics and schedule snap-back."""
        if self._lyrics_programmatic_scroll:
            return
        self._lyrics_user_scrolling = True
        self._schedule_snap()

    def _scroll_flat_lyrics_to(self, target_idx, duration=200):
        """Scroll flat lyrics column to the given line index."""
        self._lyrics_programmatic_scroll = True
        column = getattr(self, '_lyrics_flat_column', None)
        if not column:
            self._lyrics_programmatic_scroll = False
            return

        async def _do_scroll():
            try:
                offset = target_idx * 32
                await column.scroll_to(offset=offset, duration=duration)
            except Exception:
                pass
            self._lyrics_programmatic_scroll = False

        self._page.run_task(_do_scroll)

    def _schedule_initial_lyrics_scroll(self):
        """Schedule initial scroll to the current lyrics line after build."""
        target_idx = getattr(self, '_last_lyrics_idx', 0)

        async def _do_scroll():
            await asyncio.sleep(0.15)
            try:
                self._scroll_flat_lyrics_to(target_idx, duration=300)
                self._lyrics_need_initial_scroll = False
            except Exception:
                pass

        self._page.run_task(_do_scroll)

    def _build_timed_lyrics(self, data, player, offset, use_curved=False):
        """Build timed lyrics display (curved or flat mode).
        
        Args:
            data: LyricsData with timed lines.
            player: AudioPlayer instance.
            offset: Lyrics synchronization offset in ms.
            use_curved: Whether to use curved display mode.
        
        Returns:
            A lyrics display widget.
        """
        pos = player.position_ms + offset
        current_idx = 0
        for i, line in enumerate(data.lines):
            if (line.time_ms or 0) <= pos:
                current_idx = i
            else:
                break
        self._last_lyrics_idx = current_idx
        self._lyrics_data = data
        self._lyrics_use_curved = use_curved
        self._lyrics_offset = offset
        self._lyrics_widgets = []

        total = len(data.lines)
        pw = self._page.width or 400
        is_desktop = pw > 800

        max_w = pw if not is_desktop else int(pw * 0.4)
        text_align = ft.TextAlign.CENTER

        self._lyrics_widgets = []
        total = len(data.lines)
        if use_curved:
            self._lyrics_data_obj = data
            gesture = self._build_curved_listview(data, current_idx, player, max_w, text_align)
            return gesture
        else:
            self._lyrics_need_initial_scroll = True
            self._lyrics_start = 0
            self._flat_lyrics_data = data
            self._flat_lyrics_player = player
            self._flat_lyrics_max_w = max_w
            self._flat_lyrics_text_align = text_align
            self._lyrics_player = player
            self._flat_lyrics_current_idx = current_idx

            controls = self._build_flat_lyrics_controls(data, current_idx, 0.0, max_w, text_align, player)

            lyrics_column = ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                on_scroll=self._on_flat_lyrics_scroll,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=controls,
            )
            self._lyrics_flat_column = lyrics_column

            return ft.Container(
                expand=True,
                padding=ft.Padding(0, 20, 0, 20),
                content=lyrics_column,
            )

    def _build_flat_lyrics_controls(self, data, highlight_idx, progress, max_w, text_align, player):
        """Build ALL lyrics line controls with gradient highlighting.
        
        Args:
            data: LyricsData object.
            highlight_idx: Active line index.
            progress: Progress within active line.
            max_w: Maximum width.
            text_align: Text alignment.
            player: AudioPlayer instance.
        
        Returns:
            List of controls for the flat lyrics view.
        """
        line_h = 32
        controls = []
        for i, line in enumerate(data.lines):
            container = ft.Container(
                key=f"lyric_line_{i}",
                height=line_h,
                padding=ft.Padding(28, 0, 28, 0),
                alignment=ft.Alignment(0, 0),
                width=max_w,
                on_click=lambda e, t=line.time_ms: player.seek(t) if t else None,
            )
            if i == highlight_idx:
                line_text = line.text
                text_w = self._estimate_text_width(line_text, 19)
                effective_w = max_w - 56
                adj_progress = progress
                if text_w > effective_w:
                    adj_progress = min(1.0, progress * (text_w / effective_w))

                scroll_widget = self._build_scrolling_lyric_line(
                    line_text, 19, ft.FontWeight.BOLD, ft.Colors.PRIMARY,
                    effective_w, adj_progress, text_align,
                )
                container.content = ft.ShaderMask(
                    shader=ft.LinearGradient(
                        begin=ft.Alignment(-1, 0),
                        end=ft.Alignment(1, 0),
                        colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)],
                        stops=[adj_progress, adj_progress],
                    ),
                    content=scroll_widget,
                    blend_mode=ft.BlendMode.SRC_IN,
                )
            else:
                container.content = ft.Text(
                    line.text,
                    size=16,
                    weight=ft.FontWeight.NORMAL,
                    color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=text_align,
                )
            controls.append(container)
        return controls

    def _rebuild_flat_lyrics(self, highlight_idx, progress=0.0):
        """Rebuild flat lyrics column with updated highlighting."""
        data = getattr(self, '_flat_lyrics_data', None)
        player = getattr(self, '_flat_lyrics_player', None)
        max_w = getattr(self, '_flat_lyrics_max_w', 400)
        text_align = getattr(self, '_flat_lyrics_text_align', ft.TextAlign.LEFT)
        column = getattr(self, '_lyrics_flat_column', None)
        if not data or not player or not column:
            return

        controls = self._build_flat_lyrics_controls(
            data, highlight_idx, progress, max_w, text_align, player,
        )
        column.controls = controls
        try:
            column.update()
        except RuntimeError:
            pass

    def _update_lyrics_styles(self, new_idx):
        """Update lyrics highlighting when the active line changes.
        
        Args:
            new_idx: Index of the newly active lyrics line.
        """
        data = self._lyrics_data
        use_curved = getattr(self, '_lyrics_use_curved', False)
        total = len(data.lines)

        if use_curved:
            if self._lyrics_user_scrolling:
                return

            progress = 0.0
            if 0 <= new_idx < total:
                ln = data.lines[new_idx]
                s = ln.time_ms or 0
                e = (data.lines[new_idx + 1].time_ms or s) if new_idx < total - 1 else self._lyrics_player.duration_ms
                if e > s:
                    player = self._lyrics_player
                    pos = player.position_ms + getattr(self, '_lyrics_offset', 0)
                    progress = max(0.0, min(1.0, (pos - s) / (e - s)))

            if new_idx == self._last_lyrics_idx:
                old_progress = getattr(self, '_last_lyrics_progress', 0.0)
                if abs(progress - old_progress) < 0.005:
                    return
            else:
                self._last_lyrics_idx = new_idx
                self._lyrics_current_idx = new_idx

            self._last_lyrics_progress = progress
            self._rebuild_lyrics_column(new_idx, new_idx, progress=progress)
            return

        if self._lyrics_user_scrolling:
            return

        progress = 0.0
        if 0 <= new_idx < total:
            ln = data.lines[new_idx]
            s = ln.time_ms or 0
            e = (data.lines[new_idx + 1].time_ms or s) if new_idx < total - 1 else self._lyrics_player.duration_ms
            if e > s:
                player = self._lyrics_player
                pos = player.position_ms + getattr(self, '_lyrics_offset', 0)
                progress = max(0.0, min(1.0, (pos - s) / (e - s)))

        if new_idx == self._last_lyrics_idx:
            old_progress = getattr(self, '_last_lyrics_progress', 0.0)
            if abs(progress - old_progress) < 0.005:
                # Still scroll on initial load even if progress barely changed
                if getattr(self, '_lyrics_need_initial_scroll', False):
                    self._scroll_flat_lyrics_to(new_idx)
                    self._lyrics_need_initial_scroll = False
                return

            # Progress-only update on the current highlighted line
            column = getattr(self, '_lyrics_flat_column', None)
            max_w = getattr(self, '_flat_lyrics_max_w', 400)
            text_align = getattr(self, '_flat_lyrics_text_align', ft.TextAlign.LEFT)
            if column and 0 <= new_idx < len(column.controls):
                ctrl = column.controls[new_idx]
                if isinstance(ctrl, ft.Container):
                    ln = data.lines[new_idx]
                    text_w = self._estimate_text_width(ln.text, 19)
                    effective_w = max_w - 56
                    adj_progress = progress
                    if text_w > effective_w:
                        adj_progress = min(1.0, progress * (text_w / effective_w))
                    scroll_widget = self._build_scrolling_lyric_line(
                        ln.text, 19, ft.FontWeight.BOLD, ft.Colors.PRIMARY,
                        effective_w, adj_progress, text_align,
                    )
                    ctrl.content = ft.ShaderMask(
                        shader=ft.LinearGradient(
                            begin=ft.Alignment(-1, 0),
                            end=ft.Alignment(1, 0),
                            colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)],
                            stops=[adj_progress, adj_progress],
                        ),
                        content=scroll_widget,
                        blend_mode=ft.BlendMode.SRC_IN,
                    )
                    try:
                        ctrl.update()
                    except RuntimeError:
                        pass
                # Scroll on initial load
                if getattr(self, '_lyrics_need_initial_scroll', False):
                    self._scroll_flat_lyrics_to(new_idx)
            self._lyrics_need_initial_scroll = False
            self._last_lyrics_progress = progress
            return

        # Line changed — update old and new line in-place
        old_idx = self._last_lyrics_idx
        self._last_lyrics_idx = new_idx
        self._lyrics_current_idx = new_idx
        self._last_lyrics_progress = progress

        column = getattr(self, '_lyrics_flat_column', None)
        max_w = getattr(self, '_flat_lyrics_max_w', 400)
        text_align = getattr(self, '_flat_lyrics_text_align', ft.TextAlign.LEFT)
        if column is None:
            return

        updated = []
        # Reset old line to normal style
        if 0 <= old_idx < len(column.controls):
            old_ctrl = column.controls[old_idx]
            if isinstance(old_ctrl, ft.Container):
                old_line = data.lines[old_idx]
                old_ctrl.content = ft.Text(
                    old_line.text,
                    size=16,
                    weight=ft.FontWeight.NORMAL,
                    color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=text_align,
                )
                updated.append(old_ctrl)

        # Set new line to highlighted style
        if 0 <= new_idx < len(column.controls):
            new_ctrl = column.controls[new_idx]
            if isinstance(new_ctrl, ft.Container):
                new_line = data.lines[new_idx]
                text_w = self._estimate_text_width(new_line.text, 19)
                effective_w = max_w - 56
                adj_progress = progress
                if text_w > effective_w:
                    adj_progress = min(1.0, progress * (text_w / effective_w))

                scroll_widget = self._build_scrolling_lyric_line(
                    new_line.text, 19, ft.FontWeight.BOLD, ft.Colors.PRIMARY,
                    effective_w, adj_progress, text_align,
                )
                new_ctrl.content = ft.ShaderMask(
                    shader=ft.LinearGradient(
                        begin=ft.Alignment(-1, 0),
                        end=ft.Alignment(1, 0),
                        colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)],
                        stops=[adj_progress, adj_progress],
                    ),
                    content=scroll_widget,
                    blend_mode=ft.BlendMode.SRC_IN,
                )
                updated.append(new_ctrl)

        for ctrl in updated:
            try:
                ctrl.update()
            except RuntimeError:
                pass

        # Auto-scroll to current line
        if column:
            self._scroll_flat_lyrics_to(new_idx)

        self._lyrics_need_initial_scroll = False

    def _build_plain_lyrics(self, data):
        """Build plain (unsynchronized) lyrics display.
        
        Args:
            data: LyricsData with plain lines.
        
        Returns:
            A scrollable Column with lyrics text.
        """
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    padding=ft.Padding(32, 4, 32, 4),
                    content=ft.Text(line.text, size=16, text_align=ft.TextAlign.CENTER),
                )
                for line in data.lines
            ],
        )

    def _build_queue_view(self, player):
        """Build the playback queue view.
        
        Args:
            player: AudioPlayer instance.
        
        Returns:
            A scrollable ReorderableListView of queued tracks.
        """
        if not player.queue:
            return ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(tr("noTracksInQueue")),
            )

        from ui.widgets.track_tile import TrackTile

        def on_reorder(e):
            """Handle drag-to-reorder in the queue."""
            old_idx = e.old_index if hasattr(e, 'old_index') else e.oldIndex
            new_idx = e.new_index if hasattr(e, 'new_index') else e.newIndex
            if old_idx < new_idx:
                for i in range(old_idx, new_idx):
                    player.queue[i], player.queue[i + 1] = player.queue[i + 1], player.queue[i]
            elif old_idx > new_idx:
                for i in range(old_idx, new_idx, -1):
                    player.queue[i], player.queue[i - 1] = player.queue[i - 1], player.queue[i]
            if player.current_index == old_idx:
                player.current_index = new_idx
            elif old_idx < player.current_index <= new_idx:
                player.current_index -= 1
            elif new_idx <= player.current_index < old_idx:
                player.current_index += 1
            self._rebuild()

        tracks = []
        for i, t in enumerate(player.queue):
            is_current = i == player.current_index
            tile = TrackTile(
                track=t,
                leading=ft.Text(str(i + 1).zfill(2), size=14),
                is_playing=is_current,
                on_tap=lambda e, idx=i: _jump_to(self._page, idx),
                padding=4,
                show_trailing=True,
                trailing_icon=ft.Icons.DELETE,
                on_trailing_pressed=lambda e, idx=i: self._remove_from_queue(idx),
                is_missing=not os.path.isfile(t.path),
            )
            tracks.append(tile)

        return ft.Container(
            expand=True,
            padding=ft.Padding(16, 80, 16, 80),
            content=ft.ReorderableListView(
                expand=True,
                controls=tracks,
                on_reorder=on_reorder,
                show_default_drag_handles=True,
            ),
        )

    def _remove_from_queue(self, idx):
        """Remove a track from the queue by index.
        
        Args:
            idx: Index of the track to remove.
        """
        player = self._get_player()
        if not player or idx < 0 or idx >= len(player.queue):
            return
        player.queue.pop(idx)
        if idx < player.current_index:
            player.current_index -= 1
        elif idx == player.current_index:
            if player.queue:
                player.current_index = min(player.current_index, len(player.queue) - 1)
                player._load_current()
            else:
                player.current_index = -1
                player._is_playing = False
                self._page.run_task(self._page.push_route, "/library")
                return
        self._rebuild()


# Module-level helper functions

def _get_view_icon(mode: str) -> str:
    """Get the icon for toggling between cover and lyrics views."""
    return ft.Icons.LYRICS if mode == "cover" else ft.Icons.ALBUM


def _get_view_tooltip(mode: str) -> str:
    """Get the tooltip text for the view toggle button."""
    return tr("showLyrics") if mode == "cover" else tr("showCover")


def _jump_to(page, index):
    app = page.session.store.get("app")
    if app and app.audio_player:
        app.audio_player.current_index = index
        app.audio_player._load_current()
