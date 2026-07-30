"""Mini Player Widget for GroovyBox.

This module provides the MiniPlayerWidget that appears at the bottom
of the shell view. Displays current track info, playback controls,
progress bar, and play mode options in a compact format.
Adapts layout for desktop (wide) and mobile (narrow) screens.
"""

import flet as ft

from logic.localize import tr


class MiniPlayerWidget(ft.Container):
    """Compact persistent player widget at the bottom of the screen.

    Shows current track info, play/pause/skip controls, progress bar,
    and play mode cycling. Automatically switches between desktop and
    mobile layouts based on screen width.

    Attributes:
        current_track: The currently playing track data.
    """

    def __init__(self, page: ft.Page):
        super().__init__(height=0)
        self._page = page
        self.current_track = None
        self._is_playing = False
        self._is_loading = False
        self._position_ms = 0
        self._duration_ms = 0
        self._volume = 0.8
        self.repeat_mode = "none"
        self.shuffle = False

        # Callback functions bound to the audio player
        self._on_toggle_play = None
        self._on_next = None
        self._on_prev = None
        self._on_seek = None
        self._on_volume_change = None
        self._on_open_player = None
        self._on_toggle_repeat = None
        self._on_toggle_shuffle = None

        # Inner column for content
        self.inner = ft.Column(tight=True, spacing=0)
        self.content = self.inner

        # State tracking for efficient updates
        self._pos_slider = None
        self._play_btn = None
        self._seeking = False

    @property
    def page(self):
        """Access the Flet page instance."""
        return self._page

    def bind(self, app):
        """Bind the mini player to the application's audio player.

        Sets up all callback references to the audio player's methods.

        Args:
            app: The GroovyBoxApp instance.
        """
        if not app:
            return
        player = app.audio_player
        self._on_toggle_play = player.toggle_play_pause
        self._on_next = player.next
        self._on_prev = player.previous
        self._on_seek = player.seek
        self._on_volume_change = player.set_volume
        self._on_open_player = lambda: self._page.run_task(self._page.push_route, "/player")
        self._on_toggle_repeat = self._toggle_repeat_helper
        self._on_toggle_shuffle = self._toggle_shuffle_helper

    def _toggle_repeat_helper(self):
        """Cycle through repeat modes: none -> one -> all -> none."""
        app = self._page.session.store.get("app")
        if app and app.audio_player:
            modes = ["none", "one", "all"]
            idx = (modes.index(app.audio_player.repeat_mode) + 1) % 3
            app.audio_player.repeat_mode = modes[idx]
            self.refresh()

    def _cycle_play_mode(self):
        from logic.play_mode import cycle_play_mode

        cycle_play_mode(self._page)
        self.refresh()

    def _open_queue(self, e):
        """Show the playback queue in a bottom sheet.

        Displays all tracks in the queue with options to reorder
        and select tracks. The currently playing track is highlighted.
        """
        app = self._page.session.store.get("app")
        if not app or not app.audio_player:
            return
        player = app.audio_player
        queue = player.queue or []
        tracks = []

        def on_reorder(e):
            """Handle drag-to-reorder in the queue."""
            old_idx = e.old_index if hasattr(e, "old_index") else e.oldIndex
            new_idx = e.new_index if hasattr(e, "new_index") else e.newIndex
            if old_idx < new_idx:
                for i in range(old_idx, new_idx):
                    player.queue[i], player.queue[i + 1] = player.queue[i + 1], player.queue[i]
            elif old_idx > new_idx:
                for i in range(old_idx, new_idx, -1):
                    player.queue[i], player.queue[i - 1] = player.queue[i - 1], player.queue[i]
            # Update current_index to follow the moved track
            if player.current_index == old_idx:
                player.current_index = new_idx
            elif old_idx < player.current_index <= new_idx:
                player.current_index -= 1
            elif new_idx <= player.current_index < old_idx:
                player.current_index += 1
            self._open_queue(e)

        for i, t in enumerate(queue):
            is_current = t.id == app.current_track.id if app.current_track else False
            tile = ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.PLAY_ARROW_ROUNDED if is_current else ft.Icons.MUSIC_NOTE_ROUNDED,
                        color=ft.Colors.PRIMARY if is_current else None,
                    ),
                    title=ft.Text(
                        t.title or "?",
                        weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    subtitle=ft.Text(t.artist or "", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    on_click=lambda _, idx=i: self._on_queue_select(idx),
                ),
            )
            tracks.append(tile)

        bs = ft.BottomSheet(
            ft.Container(
                padding=ft.Padding(0, 8, 0, self._page.padding.bottom if self._page.padding else 0),
                content=ft.Column(
                    tight=True,
                    controls=[
                        ft.Row(
                            tight=True,
                            controls=[
                                ft.Container(expand=True),
                                ft.Text(tr("queue"), weight=ft.FontWeight.BOLD, size=16),
                                ft.Container(expand=True),
                                ft.IconButton(ft.Icons.CLOSE, icon_size=20, on_click=lambda e: self._page.pop_dialog()),
                            ],
                        ),
                        ft.Divider(height=1),
                        ft.Container(
                            height=self._page.height * 0.5 if self._page.height else 300,
                            content=(
                                ft.ReorderableListView(
                                    expand=True,
                                    controls=tracks,
                                    on_reorder=on_reorder if len(tracks) > 1 else None,
                                    show_default_drag_handles=True,
                                )
                                if tracks
                                else ft.Container(
                                    expand=True,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Text(tr("noTracksInQueue"), color=ft.Colors.GREY),
                                )
                            ),
                        ),
                    ],
                ),
            ),
        )
        self._page.show_dialog(bs)

    def _on_queue_select(self, idx: int):
        """Handle track selection from the queue sheet.

        Args:
            idx: Index of the selected track in the queue.
        """
        app = self._page.session.store.get("app")
        if app and app.audio_player:
            player = app.audio_player
            if 0 <= idx < len(player.queue):
                player.current_index = idx
                player._load_current()
            self._page.pop_dialog()

    def _toggle_shuffle_helper(self):
        """Toggle shuffle mode on/off."""
        app = self._page.session.store.get("app")
        if app and app.audio_player:
            app.audio_player.shuffle = not app.audio_player.shuffle
            self.refresh()

    def refresh(self):
        """Rebuild the mini player UI based on current state.

        Switches between desktop and mobile layouts based on screen width.
        Hides the player entirely if no track is loaded.
        """
        app = self._page.session.store.get("app")
        if not app or not app.current_track:
            self.height = 0
            self.inner.controls = []
            self.update()
            return

        # Sync state from audio player
        self.current_track = app.current_track
        player = app.audio_player
        self._is_playing = player.is_playing
        self._is_loading = player.loading
        self._position_ms = player.position_ms
        self._duration_ms = player.duration_ms
        self._cached_dur = 0
        self._volume = player.volume
        self.repeat_mode = player.repeat_mode
        self.shuffle = player.shuffle

        # Calculate height with bottom padding for mobile devices
        try:
            bottom_pad = self._page.padding.bottom if self._page.padding else 0
        except RuntimeError:
            bottom_pad = 0
        self.height = 72 + bottom_pad
        is_desktop = (self._page.width or 0) > 800

        self._pos_slider = None
        self._play_btn = None
        self._seeking = False

        # Choose layout based on screen width
        if is_desktop:
            self.inner.controls = [self._build_desktop()]
        else:
            self.inner.controls = [self._build_mobile()]

        self.update()

    def _progress_ratio(self) -> float:
        """Calculate the current progress as a ratio (0.0 to 1.0)."""
        max_val = max(self._duration_ms, 1)
        pos = max(0, min(self._position_ms, max_val))
        return float(pos) / float(max_val)

    def on_window_size_changed(self):
        """Handle window resize by rebuilding the mini player."""
        self.refresh()

    def refresh_position(self, pos_ms: int, dur_ms: int):
        """Update the progress bar position efficiently.

        Only updates the slider widget, avoiding full rebuilds.

        Args:
            pos_ms: Current position in milliseconds.
            dur_ms: Total duration in milliseconds.
        """
        self._position_ms = pos_ms
        self._duration_ms = dur_ms
        if not self._pos_slider or self._seeking:
            return
        max_val = max(dur_ms, 1)
        if max_val != getattr(self, "_cached_dur", 0):
            self._pos_slider.min = 0
            self._pos_slider.max = float(max_val)
            self._cached_dur = max_val
        self._pos_slider.value = float(max(0, min(pos_ms, max_val)))
        self._pos_slider.update()

    def refresh_play_state(self, is_playing: bool):
        """Update the play/pause button icon efficiently.

        Args:
            is_playing: True if currently playing, False if paused.
        """
        self._is_playing = is_playing
        if self._play_btn:
            self._play_btn.icon = ft.Icons.PAUSE_ROUNDED if is_playing else ft.Icons.PLAY_ARROW_ROUNDED
            self._play_btn.update()

    def _on_slider_change_start(self, e: ft.ControlEvent) -> None:
        """Handle progress bar drag start."""
        self._seeking = True

    def _on_slider_change_end(self, e: ft.ControlEvent) -> None:
        """Handle progress bar drag end - seek only on release."""
        seek_ms = int(e.control.value)
        if self._on_seek:
            self._on_seek(seek_ms)
        self._seeking = False

    def _build_progress(self) -> ft.Control:
        """Build the progress bar or loading indicator.

        Returns:
            A ProgressBar during loading, or a Slider for position tracking.
        """
        if self._is_loading:
            self._pos_slider = None
            return ft.Container(
                height=4,
                content=ft.ProgressBar(
                    color=ft.Colors.PRIMARY,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                ),
            )
        max_val = max(self._duration_ms, 1)
        pos = max(0, min(self._position_ms, max_val))
        self._cached_dur = max_val
        self._pos_slider = ft.Slider(
            value=float(pos),
            min=0,
            max=float(max_val),
            divisions=1000,
            height=20,
            active_color=ft.Colors.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
            thumb_color=ft.Colors.WHITE,
            overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            on_change_start=self._on_slider_change_start,
            on_change_end=self._on_slider_change_end,
        )
        return self._pos_slider

    def _build_play_button(self, icon_size: int = 28) -> ft.IconButton:
        """Build the play/pause button.

        Args:
            icon_size: Size of the play/pause icon.

        Returns:
            An IconButton with play or pause icon.
        """
        self._play_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED if self._is_playing else ft.Icons.PLAY_ARROW_ROUNDED,
            icon_size=icon_size,
            on_click=lambda _: self._on_toggle_play() if self._on_toggle_play else None,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
        )
        return self._play_btn

    def _build_mobile(self):
        """Build the mobile layout (narrow screens).

        Layout: Progress bar + [Art | Title/Artist | PlayMode | Play | Queue]
        """
        from logic.play_mode import get_play_mode_icon

        _pm_icon, _pm_color = get_play_mode_icon(self._page)
        return ft.Container(
            height=self.height,
            padding=ft.Padding(0, 0, 0, self._page.padding.bottom if self._page.padding else 0),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(top=ft.BorderSide(color=ft.Colors.OUTLINE_VARIANT, width=1)),
            content=ft.Column(
                tight=True,
                spacing=0,
                controls=[
                    self._build_progress(),
                    ft.Container(
                        expand=True,
                        on_click=lambda _: self._on_open_player() if self._on_open_player else None,
                        content=ft.Row(
                            tight=True,
                            controls=[
                                ft.Container(
                                    width=48,
                                    height=48,
                                    border_radius=8,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    content=(
                                        ft.Image(src=self.current_track.art_uri, fit=ft.BoxFit.COVER)
                                        if self.current_track.art_uri
                                        else ft.Icon(ft.Icons.MUSIC_NOTE, size=20)
                                    ),
                                    bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.GREY),
                                    margin=ft.Margin(left=8, top=0, right=0, bottom=0),
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=ft.Padding(8, 0, 8, 0),
                                    content=ft.Column(
                                        tight=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(
                                                self.current_track.title or "",
                                                weight=ft.FontWeight.BOLD,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                size=13,
                                            ),
                                            ft.Text(
                                                self.current_track.artist or "",
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                size=11,
                                                color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                                            ),
                                        ],
                                    ),
                                ),
                                ft.IconButton(
                                    _pm_icon,
                                    icon_size=20,
                                    icon_color=_pm_color,
                                    on_click=lambda _: self._cycle_play_mode(),
                                ),
                                ft.Container(
                                    padding=ft.Padding(2, 0, 2, 0),
                                    content=self._build_play_button(icon_size=28),
                                ),
                                ft.IconButton(ft.Icons.QUEUE_MUSIC, icon_size=20, on_click=self._open_queue),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _build_desktop(self):
        """Build the desktop layout (wide screens).

        Layout: Progress bar + [Art/Title | PlayMode/Prev/Play/Next/Queue | Volume]
        """
        from logic.play_mode import get_play_mode_icon

        _pm_icon, _pm_color = get_play_mode_icon(self._page)
        return ft.Container(
            height=self.height,
            padding=ft.Padding(0, 0, 0, self._page.padding.bottom if self._page.padding else 0),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(top=ft.BorderSide(color=ft.Colors.OUTLINE_VARIANT, width=1)),
            content=ft.Column(
                tight=True,
                spacing=0,
                controls=[
                    self._build_progress(),
                    ft.Container(
                        expand=True,
                        on_click=lambda _: self._on_open_player() if self._on_open_player else None,
                        content=ft.Row(
                            tight=True,
                            controls=[
                                ft.Container(
                                    expand=3,
                                    content=ft.Row(
                                        tight=True,
                                        controls=[
                                            ft.Container(
                                                width=56,
                                                height=56,
                                                border_radius=8,
                                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                                content=(
                                                    ft.Image(src=self.current_track.art_uri, fit=ft.BoxFit.COVER)
                                                    if self.current_track.art_uri
                                                    else ft.Icon(ft.Icons.MUSIC_NOTE, size=24)
                                                ),
                                                bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.GREY),
                                                margin=ft.Margin(left=8, top=0, right=0, bottom=0),
                                            ),
                                            ft.Container(
                                                expand=True,
                                                padding=ft.Padding(12, 0, 12, 0),
                                                content=ft.Column(
                                                    tight=True,
                                                    spacing=2,
                                                    controls=[
                                                        ft.Text(
                                                            self.current_track.title or "",
                                                            weight=ft.FontWeight.BOLD,
                                                            max_lines=1,
                                                            overflow=ft.TextOverflow.ELLIPSIS,
                                                            size=14,
                                                        ),
                                                        ft.Text(
                                                            self.current_track.artist or "",
                                                            max_lines=1,
                                                            overflow=ft.TextOverflow.ELLIPSIS,
                                                            size=12,
                                                            color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                                                        ),
                                                    ],
                                                ),
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    expand=5,
                                    content=ft.Row(
                                        tight=True,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        controls=[
                                            ft.IconButton(
                                                _pm_icon,
                                                icon_size=20,
                                                icon_color=_pm_color,
                                                on_click=lambda _: self._cycle_play_mode(),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.SKIP_PREVIOUS,
                                                icon_size=24,
                                                on_click=lambda _: self._on_prev() if self._on_prev else None,
                                            ),
                                            ft.Container(
                                                padding=ft.Padding(8, 0, 8, 0),
                                                content=self._build_play_button(icon_size=32),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.SKIP_NEXT,
                                                icon_size=24,
                                                on_click=lambda _: self._on_next() if self._on_next else None,
                                            ),
                                            ft.IconButton(
                                                ft.Icons.QUEUE_MUSIC, icon_size=20, on_click=self._open_queue
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    expand=2,
                                    content=ft.Row(
                                        tight=True,
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.VOLUME_UP,
                                                size=16,
                                                color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                                            ),
                                            ft.Container(
                                                expand=True,
                                                content=ft.Slider(
                                                    value=self._volume * 100,
                                                    min=0,
                                                    max=100,
                                                    divisions=100,
                                                    on_change=lambda e: (
                                                        self._on_volume_change(e.control.value / 100)
                                                        if self._on_volume_change
                                                        else None
                                                    ),
                                                ),
                                                padding=ft.Padding(0, 0, 24, 0),
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )
