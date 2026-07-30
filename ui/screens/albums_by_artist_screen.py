"""Albums by Artist Screen for GroovyBox.

This module displays a grid of artist cards, each showing the artist's
album art, name, and album/track counts. Tapping an artist navigates
to the artist detail screen.
"""

import flet as ft

from data import playlist_repository as prepo
from logic.localize import tr
from ui.widgets.universal_image import UniversalImage


def AlbumsByArtistScreen(page: ft.Page) -> ft.Control:
    """Build the albums-by-artist grid screen.

    Displays all artists who have albums, with their first album's
    art as the avatar. Shows album count and track count for each artist.

    Args:
        page: The Flet page instance.

    Returns:
        A scrollable GridView of artist cards, or a "no albums" message.
    """
    artists = prepo.watch_artists_with_albums()

    if not artists:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(tr("noAlbumsFound"), color=ft.Colors.GREY),
        )

    def open_artist(artist_name):
        """Navigate to the artist detail screen."""
        page.session.store.set("artist_data", artist_name)
        page.run_task(page.push_route, "/artist")

    # Build artist cards for the grid
    cards = []
    for art in artists:
        card = ft.Container(
            content=ft.Column(
                [
                    UniversalImage(
                        uri=art.albums[0].art_uri if art.albums else None,
                        width=80,
                        height=80,
                        border_radius=40,
                        fallback_icon=ft.Icons.PERSON,
                        fallback_icon_size=40,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        art.artist,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        size=14,
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"{len(art.albums)} {tr('albums')} \u2022 {art.track_count} {tr('tracks')}",
                        size=11,
                        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=12,
            padding=16,
            on_click=lambda e, a=art.artist: open_artist(a),
            ink=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        cards.append(card)

    return ft.Container(
        expand=True,
        padding=16,
        content=ft.GridView(
            expand=True,
            runs_count=0,
            max_extent=160,
            child_aspect_ratio=0.9,
            spacing=12,
            run_spacing=12,
            controls=cards,
        ),
    )
