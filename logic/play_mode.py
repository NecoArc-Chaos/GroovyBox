"""Shared play mode logic for GroovyBox."""

import flet as ft

_PLAY_MODE_CYCLE = [
    (False, "all"),  # List repeat
    (False, "one"),  # Single repeat
    (True, "none"),  # Shuffle
    (False, "none"),  # Sequential
]


def cycle_play_mode(page):
    app = page.session.store.get("app")
    if not app or not app.audio_player:
        return
    player = app.audio_player
    current = (player.shuffle, player.repeat_mode or "none")
    try:
        idx = (_PLAY_MODE_CYCLE.index(current) + 1) % len(_PLAY_MODE_CYCLE)
    except ValueError:
        idx = 0
    player.shuffle, player.repeat_mode = _PLAY_MODE_CYCLE[idx]


def get_play_mode_icon(page):
    app = page.session.store.get("app")
    if not app or not app.audio_player:
        return ft.Icons.REPEAT, ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)
    player = app.audio_player
    if player.shuffle:
        return ft.Icons.SHUFFLE, ft.Colors.PRIMARY
    mode = player.repeat_mode or "none"
    if mode == "one":
        return ft.Icons.REPEAT_ONE, ft.Colors.PRIMARY
    if mode == "all":
        return ft.Icons.REPEAT, ft.Colors.PRIMARY
    return ft.Icons.REPEAT, ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)
