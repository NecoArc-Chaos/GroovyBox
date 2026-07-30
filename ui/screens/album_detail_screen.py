"""Album Detail Screen for GroovyBox.

This module displays the detail view for a specific album, showing
the album art, play controls, and a list of tracks in the album.
"""

import os

import flet as ft

from data import playlist_repository as prepo
from logic.localize import tr
from ui.widgets.track_tile import TrackTile


class AlbumDetailView(ft.Container):
    """Album detail view showing album art and track listing.

    Provides controls to play all tracks or add them to the queue.
    Displays tracks with numbered leading indicators.

    Attributes:
        album: The AlbumData object being displayed.
    """

    def __init__(self, page: ft.Page, album):
        super().__init__()
        self._page = page
        self.album = album
        self._build()

    def _get_app(self):
        """Get the application instance from the session store."""
        return self._page.session.store.get("app")

    def _build(self):
        """Build the album detail view layout.

        Creates a scrollable view with:
        - Back button
        - Album art (240x240)
        - Play All and Add to Queue buttons
        - Numbered track list
        """
        tracks = prepo.watch_album_tracks(self.album.album)

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # Back navigation
                ft.Container(
                    padding=8,
                    content=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self._go_back()),
                ),
                # Album art
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Container(
                        width=240,
                        height=240,
                        border_radius=16,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Image(
                            src=self.album.art_uri,
                            fit=ft.BoxFit.COVER,
                            error_content=ft.Icon(ft.Icons.ALBUM, size=80, color=ft.Colors.WHITE54),
                        ),
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.2, ft.Colors.SHADOW)),
                    ),
                ),
                # Action buttons
                ft.Container(
                    padding=ft.Padding(16, 0, 16, 0),
                    content=ft.Row(
                        tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.FilledButton(
                                tr("playAll"),
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=lambda e: self._play_all(),
                            ),
                            ft.Container(width=12),
                            ft.OutlinedButton(
                                tr("addToQueue"),
                                icon=ft.Icons.QUEUE_MUSIC,
                                on_click=lambda e: self._add_to_queue(tracks),
                            ),
                        ],
                    ),
                ),
                # Track list
                ft.Container(
                    expand=True,
                    padding=ft.Padding(16, 0, 16, 0),
                    content=ft.ListView(
                        spacing=4,
                        controls=[
                            TrackTile(
                                track=t,
                                leading=ft.Text(str(i + 1).zfill(2), color=ft.Colors.GREY, size=14),
                                on_tap=lambda e, idx=i: self._play_at(tracks, idx),
                                padding=4,
                                is_missing=not os.path.isfile(t.path),
                            )
                            for i, t in enumerate(tracks)
                        ]
                        + [ft.Container(height=80)],
                    ),
                ),
            ],
        )

    def _go_back(self):
        """Navigate back to the previous screen."""
        self._page.views.pop()
        self._page.run_task(self._page.push_route, self._page.views[-1].route if self._page.views else "/library")

    def _play_all(self, tracks=None, initial_index=0):
        """Play all tracks in the album.

        Args:
            tracks: Optional pre-loaded track list. If None, fetches from DB.
            initial_index: Index to start playback from.
        """
        if tracks is None:
            tracks = prepo.watch_album_tracks(self.album.album)
        if tracks:
            app = self._get_app()
            if app:
                app.audio_player.play_tracks(tracks, initial_index)

    def _play_at(self, tracks, idx):
        """Play the album starting from a specific track index.

        Args:
            tracks: List of tracks in the album.
            idx: Index of the track to start from.
        """
        self._play_all(tracks, idx)

    def _add_to_queue(self, tracks):
        """Add all album tracks to the playback queue.

        Args:
            tracks: List of tracks to add.
        """
        app = self._get_app()
        if app and tracks:
            for t in tracks:
                app.audio_player.queue.append(t)
            if app.audio_player.on_queue_change:
                app.audio_player.on_queue_change()
