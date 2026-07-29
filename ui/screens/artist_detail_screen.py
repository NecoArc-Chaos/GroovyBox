"""Artist Detail Screen for GroovyBox.

This module displays the detail view for a specific artist, showing
the artist avatar, track count, and a list of all tracks by the artist.
Provides options for track management including add to playlist,
edit metadata, and delete.
"""

import os
import flet as ft
from data import playlist_repository as prepo
from logic.localize import tr
from ui.widgets.track_tile import TrackTile
from ui.widgets.track_actions import show_track_details, show_edit_dialog, show_add_to_playlist


def ArtistDetailScreen(page: ft.Page, artist_name: str) -> ft.Control:
    """Build the artist detail screen.

    Displays the artist's avatar, name, track count, and all tracks.
    Includes a "Play All" button and track context menus for management.

    Args:
        page: The Flet page instance.
        artist_name: Name of the artist to display.

    Returns:
        A Column widget with the artist detail layout.
    """
    tracks = prepo.watch_artist_tracks(artist_name)

    def play_all(e):
        """Play all tracks by this artist."""
        app = page.session.store.get("app")
        if app and tracks:
            app.audio_player.play_tracks(tracks)

    # Artist header with avatar and info
    header = ft.Container(
        padding=16,
        content=ft.Row([
            ft.Container(
                width=80, height=80, border_radius=40,
                bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY),
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(ft.Icons.PERSON, size=40, color=ft.Colors.PRIMARY),
            ),
            ft.Container(width=16),
            ft.Column([
                ft.Text(artist_name, size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"{len(tracks)} {tr('tracks')}",
                    size=13,
                    color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                ),
            ]),
            ft.Container(expand=True),
            ft.FilledButton(tr("playAll"), on_click=play_all),
        ]),
    )

    # Build track tiles
    track_tiles = []
    for t in tracks:
        tile = TrackTile(
            track=t,
            show_trailing=True,
            is_missing=not os.path.isfile(t.path),
            on_tap=lambda e, trk=t: _play_track(trk),
            on_long_press=lambda e, trk=t: _show_options(trk),
            on_trailing_pressed=lambda e, trk=t: _show_options(trk),
            padding=4,
        )
        track_tiles.append(tile)

    def _play_track(track):
        """Play a single track."""
        app = page.session.store.get("app")
        if app:
            app.audio_player.play_track(track)

    def _show_options(track):
        """Show the context menu for a track."""
        def do_add_to_pl(e):
            page.pop_dialog()
            _show_add_to_playlist(track)
        def do_view_details(e):
            page.pop_dialog()
            _show_track_details(track)
        def do_edit(e):
            page.pop_dialog()
            _show_edit_dialog(track)
        def do_delete(e):
            page.pop_dialog()
            from data import track_repository as trepo
            trepo.delete_track(track.id)
            page.run_task(page.push_route, "/library")

        bs = ft.BottomSheet(
            content=ft.Column(
                tight=True,
                controls=[
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.PLAYLIST_ADD),
                        title=ft.Text(tr("addToPlaylist")),
                        on_click=do_add_to_pl,
                    ),
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.INFO),
                        title=ft.Text(tr("viewDetails")),
                        on_click=do_view_details,
                    ),
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.EDIT),
                        title=ft.Text(tr("editMetadata")),
                        on_click=do_edit,
                    ),
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED),
                        title=ft.Text(tr("delete"), color=ft.Colors.RED),
                        on_click=do_delete,
                    ),
                ],
            ),
        )
        page.show_dialog(bs)

    def _show_add_to_playlist(track):
        show_add_to_playlist(page, track)

    def _show_track_details(track):
        show_track_details(page, track)

    def _show_edit_dialog(track):
        show_edit_dialog(page, track)

    return ft.Column(
        expand=True,
        spacing=0,
        controls=[
            header,
            ft.Divider(height=1),
            ft.Container(expand=True, content=ft.Column(
                spacing=2,
                scroll=ft.ScrollMode.AUTO,
                controls=track_tiles,
            )),
        ],
    )
