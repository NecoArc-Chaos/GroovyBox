"""Tests for app.py GroovyBoxApp."""

import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock

import flet as ft
import pytest


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.width = 800
    page.route = "/"
    page.views = []
    store = {}
    page.session.store = store
    page.update = MagicMock()
    page.run_task = MagicMock()
    page.on_route_change = None
    page.on_view_pop = None
    page.on_resize = None
    page.on_keyboard_event = None
    page.title = ""
    page.window = MagicMock()
    page.platform = "windows"
    page.platform_brightness = None
    page.pop_dialog = MagicMock()
    page.show_dialog = MagicMock()
    page.push_route = MagicMock()
    return page


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_setting.return_value = "system"
    db.init_database = MagicMock()
    return db


@pytest.fixture
def mock_audio_player():
    player = MagicMock()
    player.duration_ms = 300000
    player.position_ms = 150000
    player.volume = 0.8
    player.capture_ui_loop = AsyncMock()
    return player


@pytest.fixture
def app(mock_page, mock_db, mock_audio_player):
    class SessionStore(dict):
        def set(self, key, value):
            self[key] = value

    mock_page.session.store = SessionStore()
    with patch.dict("sys.modules", {"data.db": mock_db, "logic.audio_handler": MagicMock(AudioPlayer=MagicMock(return_value=mock_audio_player))}):
        from app import GroovyBoxApp
        mock_loop = MagicMock()
        with patch("asyncio.get_running_loop", return_value=mock_loop):
            mock_page.session.store.set("app", GroovyBoxApp(mock_page))
        yield mock_page.session.store.get("app")


def test_groovybox_app_initialization(app, mock_page, mock_db):
    """GroovyBoxApp should initialize db, theme, and audio player."""
    mock_db.init_database.assert_called()
    assert app.theme_mode is not None
    assert app.theme_seed_color == "#2EB0C6"
    assert app.shell is None


def test_is_dark_mode_system(app):
    """_is_dark_mode should return False for LIGHT mode."""
    app.theme_mode = "light"
    assert app._is_dark_mode() is False


def test_is_dark_mode_dark(app):
    """_is_dark_mode should return True for DARK mode."""
    app.theme_mode = ft.ThemeMode.DARK
    assert app._is_dark_mode() is True


def test_is_dark_mode_system_brightness_dark(app, mock_page):
    """_is_dark_mode should return True when system brightness is dark."""
    app.theme_mode = ft.ThemeMode.SYSTEM
    mock_page.platform_brightness = ft.Brightness.DARK
    assert app._is_dark_mode() is True


def test_is_dark_mode_system_brightness_light(app, mock_page):
    """_is_dark_mode should return False when system brightness is light."""
    app.theme_mode = ft.ThemeMode.SYSTEM
    mock_page.platform_brightness = ft.Brightness.LIGHT
    assert app._is_dark_mode() is False


def test_get_icon_suffix_dark(app):
    """_get_icon_suffix should return '-dark' in dark mode."""
    app.theme_mode = ft.ThemeMode.DARK
    assert app._get_icon_suffix() == "-dark"


def test_get_icon_suffix_light(app):
    """_get_icon_suffix should return '' in light mode."""
    app.theme_mode = "light"
    assert app._get_icon_suffix() == ""


def test_set_window_icon_exists(app, mock_page, tmp_path):
    """_set_window_icon should set icon if file exists."""
    icon_dir = tmp_path / "assets" / "images"
    icon_dir.mkdir(parents=True)
    icon_path = icon_dir / "icon.ico"
    icon_path.write_text("fake")

    with patch("os.path.exists", return_value=True), patch("os.path.join", return_value=str(icon_path)):
        app._set_window_icon()

    mock_page.window.icon = str(icon_path)
    mock_page.update.assert_called()


def test_set_window_icon_missing(app, mock_page):
    """_set_window_icon should not crash if icon file is missing."""
    with patch("os.path.exists", return_value=False):
        app._set_window_icon()


def test_on_play_state_change(app, mock_page):
    """_on_play_state_change should refresh mini player and player screen."""
    mock_shell = MagicMock()
    mock_shell.mini_player.refresh_play_state = MagicMock()
    app.shell = mock_shell
    app.audio_player = MagicMock()

    app._on_play_state_change(True)

    mock_shell.mini_player.refresh_play_state.assert_called_once_with(True)
    mock_page.update.assert_called()


def test_on_position_change(app, mock_page):
    """_on_position_change should refresh position in mini player and player screen."""
    mock_shell = MagicMock()
    mock_shell.mini_player.refresh_position = MagicMock()
    app.shell = mock_shell
    app.audio_player = MagicMock()
    app.audio_player.duration_ms = 300000

    app._on_position_change(150000)

    mock_shell.mini_player.refresh_position.assert_called_once_with(150000, 300000)
    mock_page.update.assert_called()


def test_on_missing_tracks_from_user(app, mock_page):
    """_on_missing_tracks should show dialog for user-triggered missing tracks."""
    app._on_missing_tracks(["song1.mp3"], from_user=True)
    mock_page.show_dialog.assert_called_once()
    mock_page.update.assert_called()


def test_on_missing_tracks_auto_single(app, mock_page):
    """_on_missing_tracks should show SnackBar for auto-skipped single track."""
    app._on_missing_tracks(["song1.mp3"], from_user=False)
    mock_page.show_dialog.assert_called_once()
    mock_page.update.assert_called()


def test_call_player_method(app, mock_page):
    """_call_player_method should call method on player screen if it's the top view."""
    mock_player_screen = MagicMock()
    mock_view = MagicMock()
    mock_view.route = "/player"
    mock_view.controls = [mock_player_screen]
    mock_page.views = [mock_view]

    app._call_player_method("refresh_play_state", True)

    mock_player_screen.refresh_play_state.assert_called_once_with(True)


def test_call_player_method_no_player_route(app, mock_page):
    """_call_player_method should do nothing if top view is not /player."""
    mock_view = MagicMock()
    mock_view.route = "/library"
    mock_view.controls = [MagicMock()]
    mock_page.views = [mock_view]

    app._call_player_method("refresh_play_state", True)


def test_reload_ui(app, mock_page):
    """_reload_ui should update title and sync views."""
    app._sync_views = MagicMock()
    app._reload_ui()
    app._sync_views.assert_called_once()


def test_show_fallback_view(app, mock_page):
    """_show_fallback_view should display error view with retry button."""
    app._sync_views = MagicMock()
    app._show_fallback_view()

    assert len(mock_page.views) == 1
    assert mock_page.views[0].route == "/"
    mock_page.update.assert_called()


def test_refresh_ui(app, mock_page):
    """_refresh_ui should update shell and player screen."""
    mock_shell = MagicMock()
    mock_shell.content_view.update = MagicMock()
    mock_shell.mini_player.refresh = MagicMock()
    app.shell = mock_shell

    app._refresh_ui()

    mock_shell.content_view.update.assert_called_once()
    mock_shell.mini_player.refresh.assert_called_once()
    mock_page.update.assert_called()


def test_on_route_change_syncs_views(app, mock_page):
    """_on_route_change should call _sync_views."""
    app._sync_views = MagicMock()
    app._on_route_change(MagicMock())
    app._sync_views.assert_called_once()


def test_on_route_change_fallback(app, mock_page):
    """_on_route_change should fallback to /library if sync fails."""
    app._sync_views = MagicMock(side_effect=Exception("sync failed"))
    app._show_fallback_view = MagicMock()

    app._on_route_change(MagicMock())

    assert mock_page.route == "/library"
    app._show_fallback_view.assert_called_once()


def test_on_window_resize(app, mock_page):
    """_on_window_resize should notify active screen on width change."""
    mock_page.width = 900
    app._last_window_width = 800
    app._notify_active_screen_window_resize = MagicMock()

    app._on_window_resize(MagicMock())

    app._notify_active_screen_window_resize.assert_called_once()


def test_on_window_resize_no_change(app, mock_page):
    """_on_window_resize should do nothing if width unchanged."""
    mock_page.width = 800
    app._last_window_width = 800
    app._notify_active_screen_window_resize = MagicMock()

    app._on_window_resize(MagicMock())

    app._notify_active_screen_window_resize.assert_not_called()


def test_load_key_bindings_default(app, mock_db):
    """_load_key_bindings should return defaults when no custom bindings."""
    mock_db.get_setting.return_value = ""
    bindings = app._load_key_bindings()
    assert "play_pause" in bindings
    assert bindings["play_pause"] == "Space"


def test_load_key_bindings_custom(app, mock_db):
    """_load_key_bindings should merge custom bindings with defaults."""
    custom = {"play_pause": "KeyP"}
    mock_db.get_setting.return_value = json.dumps(custom)
    bindings = app._load_key_bindings()
    assert bindings["play_pause"] == "KeyP"
    assert bindings["next_track"] == "N"


def test_on_global_keyboard_play_pause(app, mock_page, mock_audio_player):
    """_on_global_keyboard should toggle play/pause on Space."""
    app.audio_player = mock_audio_player
    mock_page.route = "/library"
    app._load_key_bindings = MagicMock(return_value={"play_pause": "Space"})

    event = MagicMock()
    event.key = "Space"
    app._on_global_keyboard(event)

    mock_audio_player.toggle_play_pause.assert_called_once()
    mock_page.update.assert_called()


def test_on_global_keyboard_next_track(app, mock_page, mock_audio_player):
    """_on_global_keyboard should skip to next track on N."""
    app.audio_player = mock_audio_player
    mock_page.route = "/library"
    app._load_key_bindings = MagicMock(return_value={"next_track": "N"})

    event = MagicMock()
    event.key = "N"
    app._on_global_keyboard(event)

    mock_audio_player.next.assert_called_once()
    mock_page.update.assert_called()


def test_on_global_keyboard_exit_player(app, mock_page):
    """_on_global_keyboard should exit player screen on Escape."""
    mock_page.route = "/player"
    app._load_key_bindings = MagicMock(return_value={"exit_player": "Escape"})

    event = MagicMock()
    event.key = "Escape"
    app._on_global_keyboard(event)

    mock_page.run_task.assert_called_with(mock_page.push_route, "/library")


def test_on_global_keyboard_volume_up(app, mock_page, mock_audio_player):
    """_on_global_keyboard should increase volume on Arrow Up in player."""
    app.audio_player = mock_audio_player
    mock_page.route = "/player"
    app._load_key_bindings = MagicMock(return_value={"volume_up": "Arrow Up"})

    event = MagicMock()
    event.key = "Arrow Up"
    app._on_global_keyboard(event)

    mock_audio_player.set_volume.assert_called_once()
    mock_page.update.assert_called()


def test_on_global_keyboard_key_capture(app, mock_page):
    """_on_global_keyboard should use key capture callback if active."""
    mock_capture = MagicMock()
    mock_page.session.store["__key_capture_callback"] = mock_capture

    event = MagicMock()
    event.key = "A"
    app._on_global_keyboard(event)

    mock_capture.assert_called_once_with("A")
    mock_page.update.assert_not_called()


def test_on_view_pop_multiple_views(app, mock_page):
    """_on_view_pop should pop view if more than one view exists."""
    mock_view = MagicMock()
    mock_view.route = "/library"
    mock_page.views = [MagicMock(), mock_view]

    async def fake_push_route(route):
        mock_page.views.append(mock_view)

    mock_page.push_route = fake_push_route

    asyncio.run(app._on_view_pop(MagicMock()))

    assert len(mock_page.views) == 2


def test_on_view_pop_single_view_mobile(app, mock_page, mock_db):
    """_on_view_pop should show 'press again' toast on mobile with single view."""
    mock_page.views = [MagicMock()]
    mock_db.is_mobile.return_value = True
    app._last_back_press = 0

    asyncio.run(app._on_view_pop(MagicMock()))

    mock_page.show_dialog.assert_called_once()


def test_sync_views_player(app, mock_page):
    """_sync_views should show PlayerScreen for /player route."""
    mock_page.route = "/player"
    mock_player_screen = MagicMock()
    with patch("ui.screens.player_screen.PlayerScreen", return_value=mock_player_screen):
        app._sync_views()

    assert len(mock_page.views) == 1
    assert mock_page.views[0].route == "/player"
    mock_page.update.assert_called()


def test_sync_views_library(app, mock_page):
    """_sync_views should show ShellView with LibraryScreen for /library route."""
    mock_page.route = "/library"
    mock_library_screen = MagicMock()
    mock_shell = MagicMock()
    mock_shell.mini_player = MagicMock()
    with patch("ui.shell.ShellView", return_value=mock_shell), \
         patch("ui.screens.library_screen.LibraryScreen", return_value=mock_library_screen):
        app._sync_views()

    assert len(mock_page.views) == 1
    assert app.shell == mock_shell
    mock_shell.mini_player.bind.assert_called_once_with(app)
    mock_page.update.assert_called()


def test_sync_views_settings(app, mock_page):
    """_sync_views should show SettingsScreen for /settings route."""
    mock_page.route = "/settings"
    mock_settings_screen = MagicMock()
    mock_shell = MagicMock()
    mock_shell.mini_player = MagicMock()
    with patch("ui.shell.ShellView", return_value=mock_shell), \
         patch("ui.screens.settings_screen.SettingsScreen", return_value=mock_settings_screen):
        app._sync_views()

    assert len(mock_page.views) == 1
    mock_shell.mini_player.bind.assert_called_once_with(app)


def test_sync_views_unknown_route(app, mock_page):
    """_sync_views should default to LibraryScreen for unknown routes."""
    mock_page.route = "/unknown"
    mock_library_screen = MagicMock()
    mock_shell = MagicMock()
    mock_shell.mini_player = MagicMock()
    with patch("ui.shell.ShellView", return_value=mock_shell), \
         patch("ui.screens.library_screen.LibraryScreen", return_value=mock_library_screen):
        app._sync_views()

    assert len(mock_page.views) == 1
    mock_shell.content_view.controls = [mock_library_screen]


def test_delayed_initial_sync_fallback(app, mock_page):
    """_delayed_initial_sync should call _sync_views if not yet synced."""
    app._initial_views_synced = False
    app._sync_views = MagicMock()

    asyncio.run(app._delayed_initial_sync())

    app._sync_views.assert_called_once()


def test_delayed_initial_sync_already_synced(app, mock_page):
    """_delayed_initial_sync should skip if already synced."""
    app._initial_views_synced = True
    app._sync_views = MagicMock()

    asyncio.run(app._delayed_initial_sync())

    app._sync_views.assert_not_called()


def test_refresh_watch_scanner(app, mock_page, mock_db):
    """refresh_watch_scanner should update watched paths."""
    mock_db.get_connection.return_value.__enter__ = MagicMock(return_value=MagicMock(
        execute=MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[
            {"path": "/music", "id": 1}
        ])))
    ))
    mock_db.get_connection.return_value.__exit__ = MagicMock(return_value=False)

    app._watch_scanner = MagicMock()
    app.refresh_watch_scanner()

    app._watch_scanner._watched_paths.clear.assert_called_once()
    app._watch_scanner.add_watch.assert_called_once_with("/music", 1)
    app._watch_scanner.refresh.assert_called_once()


def test_refresh_watch_scanner_no_scanner(app, mock_page, mock_db):
    """refresh_watch_scanner should do nothing if scanner is missing."""
    app._watch_scanner = None
    app.refresh_watch_scanner()


def test_update_metadata_with_track(app, mock_page):
    """_update_metadata should load metadata and update current_metadata."""
    mock_trepo = MagicMock()
    mock_trepo.get_track_by_path.return_value = MagicMock(
        id=1, art_uri="/art.jpg"
    )
    with patch.dict("sys.modules", {"data.track_repository": mock_trepo}), \
         patch("app.get_metadata", return_value=MagicMock(art_bytes=None)):
        app._update_metadata("/song.mp3")

    assert app.current_metadata is not None


def test_update_metadata_without_track(app, mock_page):
    """_update_metadata should set current_metadata to None if track not found."""
    mock_trepo = MagicMock()
    mock_trepo.get_track_by_path.return_value = None
    with patch.dict("sys.modules", {"data.track_repository": mock_trepo}):
        app._update_metadata("/nonexistent.mp3")

    assert app.current_metadata is None
