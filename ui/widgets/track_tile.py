"""Track Tile Widget for GroovyBox.

This module provides a reusable TrackTile function that creates a
consistent track list item with album art, title, artist info,
and optional trailing actions. Used across library, playlist,
and artist screens.
"""

import flet as ft
from typing import Optional, Callable
from data.models import Track
from logic.metadata_service import format_duration
from logic.localize import tr
from ui.widgets.universal_image import UniversalImage


def TrackTile(
    track: Track,
    on_tap: Optional[Callable] = None,
    on_long_press: Optional[Callable] = None,
    is_playing: bool = False,
    show_trailing: bool = False,
    on_trailing_pressed: Optional[Callable] = None,
    leading: Optional[ft.Control] = None,
    padding: float = 8,
    trailing_icon: str = ft.Icons.MORE_VERT,
    is_missing: bool = False,
) -> ft.Container:
    """Create a track list item widget.

    Renders a track with album art thumbnail, title, artist/duration
    subtitle, and optional action button. Highlights the currently
    playing track with primary color accents.

    Args:
        track: The Track data object to display.
        on_tap: Callback when the tile is tapped.
        on_long_press: Callback when the tile is long-pressed.
        is_playing: Whether this track is currently playing (enables highlighting).
        show_trailing: Whether to show the trailing action button.
        on_trailing_pressed: Callback when the trailing button is pressed.
        leading: Optional leading control (e.g., track number).
        padding: Vertical padding override for the tile.
        trailing_icon: Icon to use for the trailing button.
        is_missing: Whether the track file is missing on disk.

    Returns:
        A Container widget with the styled track tile.
    """
    # Apply highlighting for the currently playing track
    bg = ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY) if is_playing else ft.Colors.TRANSPARENT
    title_color = ft.Colors.PRIMARY if is_playing else ft.Colors.ON_SURFACE
    title_weight = ft.FontWeight.BOLD if is_playing else ft.FontWeight.NORMAL

    if is_missing:
        title_color = ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)
        bg = ft.Colors.with_opacity(0.05, ft.Colors.ERROR)

    # Build subtitle: "Artist • Duration"
    subtitle = f"{track.artist or tr('unknownArtist', 'Unknown Artist')} \u2022 {format_duration(track.duration)}"

    tile = ft.ListTile(
        leading=ft.Row(
            tight=True,
            controls=[
                leading or ft.Container(width=0),
                UniversalImage(
                    uri=track.art_uri,
                    width=48,
                    height=48,
                    border_radius=8,
                    fallback_icon=ft.Icons.MUSIC_NOTE,
                    fallback_icon_size=24,
                ),
            ],
        ),
        title=ft.Text(
            track.title,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            color=title_color,
            weight=title_weight,
        ),
        subtitle=ft.Text(
            subtitle,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
            size=12,
        ),
        trailing=(
            ft.IconButton(
                icon=trailing_icon,
                icon_size=20,
                on_click=on_trailing_pressed,
            )
            if show_trailing
            else (ft.Icon(ft.Icons.PLAY_ARROW, color=ft.Colors.PRIMARY, size=20) if is_playing else None)
        ),
        on_click=on_tap,
        on_long_press=on_long_press,
    )

    return ft.Container(
        content=tile,
        bgcolor=bg,
        border_radius=8,
        padding=ft.Padding(16, padding - 8, 16, padding - 8) if padding != 8 else ft.Padding(16, 0, 16, 0),
    )
