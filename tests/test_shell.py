"""Tests for ui/shell.py ShellView."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def init_db():
    from data import db
    db.init_database()
    yield
    db._SETTING_CACHE.clear()
    db.DB_PATH = None
    conn = getattr(db._thread_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        db._thread_local.connection = None
    try:
        db_path = db.get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.width = 800
    page.session.store = {}
    page.platform = "windows"
    page.navigation_bar = None
    page.update = MagicMock()
    return page


def test_shell_view_initialization_desktop(mock_page):
    """ShellView should initialize correctly on desktop."""
    from ui.shell import ShellView

    mock_page.width = 800
    shell = ShellView(mock_page)

    assert shell._is_mobile is False
    assert shell.navigation_bar is None
    assert shell.content_view is not None
    assert shell.mini_player is not None


def test_shell_view_initialization_mobile(mock_page):
    """ShellView should initialize correctly on mobile."""
    from ui.shell import ShellView

    mock_page.width = 375
    mock_page.platform = "android"
    shell = ShellView(mock_page)

    assert shell._is_mobile is True
    assert shell.navigation_bar is not None


def test_shell_view_initialization_early_init_none_width(mock_page):
    """ShellView should default to mobile detection when width is None."""
    from ui.shell import ShellView

    mock_page.width = None
    mock_page.platform = "ios"
    shell = ShellView(mock_page)

    assert shell._is_mobile is True


def test_detect_mobile_wide_desktop(mock_page):
    """_detect_mobile should return False for wide desktop windows."""
    from ui.shell import ShellView

    mock_page.width = 1200
    mock_page.platform = "windows"
    assert ShellView._detect_mobile(mock_page) is False


def test_detect_mobile_narrow_desktop(mock_page):
    """_detect_mobile should return False for narrow desktop (platform tie-breaker)."""
    from ui.shell import ShellView

    mock_page.width = 500
    mock_page.platform = "windows"
    assert ShellView._detect_mobile(mock_page) is False


def test_detect_mobile_narrow_mobile(mock_page):
    """_detect_mobile should return True for narrow mobile platform."""
    from ui.shell import ShellView

    mock_page.width = 375
    mock_page.platform = "android"
    assert ShellView._detect_mobile(mock_page) is True


def test_detect_mobile_none_width_mobile_platform(mock_page):
    """_detect_mobile should return True when width is None and platform is mobile."""
    from ui.shell import ShellView

    mock_page.width = None
    mock_page.platform = "iphone"
    assert ShellView._detect_mobile(mock_page) is True


def test_detect_mobile_ipad(mock_page):
    """_detect_mobile should return True for iPad platform."""
    from ui.shell import ShellView

    mock_page.width = 800
    mock_page.platform = "ipad"
    assert ShellView._detect_mobile(mock_page) is True


def test_detect_mobile_exception(mock_page):
    """_detect_mobile should return False on exception."""
    from ui.shell import ShellView

    mock_page.width = None
    del mock_page.platform  # Force AttributeError
    assert ShellView._detect_mobile(mock_page) is False


def test_platform_is_mobile_android(mock_page):
    """_platform_is_mobile should return True for Android."""
    from ui.shell import ShellView

    mock_page.platform = "android"
    assert ShellView._platform_is_mobile(mock_page) is True


def test_platform_is_mobile_ios(mock_page):
    """_platform_is_mobile should return True for iOS."""
    from ui.shell import ShellView

    mock_page.platform = "ios"
    assert ShellView._platform_is_mobile(mock_page) is True


def test_platform_is_mobile_windows(mock_page):
    """_platform_is_mobile should return False for Windows."""
    from ui.shell import ShellView

    mock_page.platform = "windows"
    assert ShellView._platform_is_mobile(mock_page) is False


def test_platform_is_mobile_none(mock_page):
    """_platform_is_mobile should return False when platform is None."""
    from ui.shell import ShellView

    mock_page.platform = None
    assert ShellView._platform_is_mobile(mock_page) is False


def test_platform_is_mobile_exception(mock_page):
    """_platform_is_mobile should return False on exception."""
    from ui.shell import ShellView

    del mock_page.platform
    assert ShellView._platform_is_mobile(mock_page) is False


def test_build_global_bg_wrapper_no_bg(mock_page):
    """_build_global_bg_wrapper should return None when no bg configured."""
    from ui.shell import ShellView

    mock_db = MagicMock()
    mock_db.get_setting.return_value = ""
    with patch("ui.shell.db", mock_db):
        shell = ShellView.__new__(ShellView)
        shell._page = mock_page
        result = shell._build_global_bg_wrapper(MagicMock())
        assert result is None


def test_build_global_bg_wrapper_hidden(mock_page):
    """_build_global_bg_wrapper should return None when bg is hidden."""
    from ui.shell import ShellView

    mock_db = MagicMock()
    mock_db.get_setting.side_effect = lambda key, default: "/bg.jpg" if key == "global_bg_path" else "true"
    with patch("ui.shell.db", mock_db), patch("os.path.isfile", return_value=True):
        shell = ShellView.__new__(ShellView)
        shell._page = mock_page
        result = shell._build_global_bg_wrapper(MagicMock())
        assert result is None


def test_build_global_bg_wrapper_active(mock_page):
    """_build_global_bg_wrapper should return Container when bg is active."""
    from ui.shell import ShellView

    mock_db = MagicMock()
    mock_db.get_setting.side_effect = lambda key, default: "/bg.jpg" if key == "global_bg_path" else "false"
    with patch("ui.shell.db", mock_db), patch("os.path.isfile", return_value=True):
        shell = ShellView.__new__(ShellView)
        shell._page = mock_page
        result = shell._build_global_bg_wrapper(MagicMock())
        assert result is not None


def test_build_global_bg_wrapper_file_not_exist(mock_page):
    """_build_global_bg_wrapper should return None when bg file does not exist."""
    from ui.shell import ShellView

    mock_db = MagicMock()
    mock_db.get_setting.side_effect = lambda key, default: "/bg.jpg" if key == "global_bg_path" else "false"
    with patch("ui.shell.db", mock_db), patch("os.path.isfile", return_value=False):
        shell = ShellView.__new__(ShellView)
        shell._page = mock_page
        result = shell._build_global_bg_wrapper(MagicMock())
        assert result is None


def test_go_back_playlist(mock_page):
    """_go_back should navigate to /library from /playlist."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    mock_page.route = "/playlist"
    shell._go_back()
    mock_page.run_task.assert_called_once_with(mock_page.push_route, "/library")


def test_go_back_album(mock_page):
    """_go_back should navigate to /library from /album."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    mock_page.route = "/album"
    shell._go_back()
    mock_page.run_task.assert_called_once_with(mock_page.push_route, "/library")


def test_go_back_artist(mock_page):
    """_go_back should navigate to /library from /artist."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    mock_page.route = "/artist"
    shell._go_back()
    mock_page.run_task.assert_called_once_with(mock_page.push_route, "/library")


def test_go_back_library_noop(mock_page):
    """_go_back should not navigate if already on /library."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    mock_page.route = "/library"
    shell._go_back()
    mock_page.run_task.assert_not_called()


def test_on_back_drag_start(mock_page):
    """_on_back_drag_start should set _swipe_back_started."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._swipe_back_started = False
    shell._on_back_drag_start(MagicMock())
    assert shell._swipe_back_started is True


def test_on_back_drag_update_triggers_back(mock_page):
    """_on_back_drag_update should trigger _go_back when delta > 100."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._swipe_back_started = True
    shell._go_back = MagicMock()

    event = MagicMock()
    event.delta_x = 150
    shell._on_back_drag_update(event)

    shell._go_back.assert_called_once()


def test_on_back_drag_update_no_trigger(mock_page):
    """_on_back_drag_update should not trigger when delta < 100."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._swipe_back_started = True
    shell._go_back = MagicMock()

    event = MagicMock()
    event.delta_x = 50
    shell._on_back_drag_update(event)

    shell._go_back.assert_not_called()


def test_on_back_drag_end(mock_page):
    """_on_back_drag_end should reset _swipe_back_started."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._swipe_back_started = True
    shell._on_back_drag_end(MagicMock())
    assert shell._swipe_back_started is False


def test_refresh_mini_player(mock_page):
    """refresh_mini_player should call mini_player.refresh()."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell.mini_player = MagicMock()
    shell.refresh_mini_player()
    shell.mini_player.refresh.assert_called_once()


def test_on_window_size_changed_mobile_category_change(mock_page):
    """on_window_size_changed should reload UI when mobile category changes."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._is_mobile = False
    shell._detect_mobile = MagicMock(return_value=True)
    mock_app = MagicMock()
    mock_app._reload_ui = MagicMock()
    shell.app = mock_app
    mock_page.session.store = {"app": mock_app}

    shell.on_window_size_changed()

    assert shell._is_mobile is True
    mock_app._reload_ui.assert_called_once()


def test_on_window_size_changed_same_category(mock_page):
    """on_window_size_changed should refresh mini player when category unchanged."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._is_mobile = False
    shell._detect_mobile = MagicMock(return_value=False)
    shell.mini_player = MagicMock()
    shell.mini_player.on_window_size_changed = MagicMock()

    shell.on_window_size_changed()

    shell.mini_player.on_window_size_changed.assert_called_once()


def test_build_toolbar(mock_page):
    """_build_toolbar should return a Container with navigation buttons."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    toolbar = shell._build_toolbar()
    assert toolbar is not None


def test_build_navigation_bar(mock_page):
    """_build_navigation_bar should return a NavigationBar on mobile."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    nav_bar = shell._build_navigation_bar()
    assert nav_bar is not None


def test_show_import_menu(mock_page):
    """_show_import_menu should show a BottomSheet dialog."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._show_import_menu(MagicMock())
    mock_page.show_dialog.assert_called_once()


def test_import_files_no_paths(mock_page):
    """_import_files should return early if no paths selected."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._reload_after_import = AsyncMock()

    asyncio.run(shell._import_files(paths=[]))

    shell._reload_after_import.assert_not_called()


def test_import_folder_no_folder(mock_page):
    """_import_folder should return early if no folder selected."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._reload_after_import = AsyncMock()

    with patch("logic.file_dialog.pick_directory", return_value=None):
        asyncio.run(shell._import_folder())

    shell._reload_after_import.assert_not_called()


def test_handle_path_import_not_exists(mock_page):
    """_handle_path_import should show error if path does not exist."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._reload_after_import = AsyncMock()

    with patch("os.path.exists", return_value=False):
        asyncio.run(shell._handle_path_import("/nonexistent"))

    mock_page.show_dialog.assert_called_once()
    shell._reload_after_import.assert_not_called()


def test_handle_path_import_directory(mock_page):
    """_handle_path_import should scan directory if path is a directory."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._reload_after_import = AsyncMock()

    mock_trepo = MagicMock()
    mock_trepo.scan_directory_async = AsyncMock(return_value=5)

    with patch("os.path.exists", return_value=True), \
         patch("os.path.isdir", return_value=True), \
         patch("data.track_repository", mock_trepo):
        asyncio.run(shell._handle_path_import("/music"))

    mock_trepo.scan_directory_async.assert_called_once_with("/music")
    shell._reload_after_import.assert_called_once()


def test_handle_path_import_audio_file(mock_page):
    """_handle_path_import should import audio file directly."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._import_files = AsyncMock()
    shell._reload_after_import = AsyncMock()

    with patch("os.path.exists", return_value=True), \
         patch("os.path.isdir", return_value=False), \
         patch("os.path.splitext", return_value=(".mp3", ".mp3")):
        asyncio.run(shell._handle_path_import("/song.mp3"))

    shell._import_files.assert_called_once_with(["/song.mp3"])


def test_handle_path_import_unsupported(mock_page):
    """_handle_path_import should show error for unsupported file types."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    shell._reload_after_import = AsyncMock()

    with patch("os.path.exists", return_value=True), \
         patch("os.path.isdir", return_value=False), \
         patch("os.path.splitext", return_value=(".txt", ".txt")):
        asyncio.run(shell._handle_path_import("/file.txt"))

    mock_page.show_dialog.assert_called_once()
    shell._reload_after_import.assert_not_called()


def test_import_lyrics_files_matched(mock_page):
    """_import_lyrics_files should match lyrics to tracks by title."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page

    mock_trepo = MagicMock()
    mock_trepo.watch_all_tracks.return_value = [
        MagicMock(title="Song A", id=1),
        MagicMock(title="Song B", id=2),
    ]
    mock_trepo.update_lyrics = MagicMock()

    mock_parser = MagicMock()
    mock_parser.parse.return_value = MagicMock()
    mock_parser.lyrics_to_json.return_value = "{}"

    with patch("data.track_repository", mock_trepo), \
         patch.dict("sys.modules", {
             "logic.encoding_helper": MagicMock(read_with_encoding=MagicMock(return_value="[00:00]test")),
             "logic.lyrics_parser": mock_parser,
         }):
        asyncio.run(shell._import_lyrics_files(["/lyrics/Song A.lrc"]))

    mock_trepo.update_lyrics.assert_called_once()


def test_import_lyrics_files_no_match(mock_page):
    """_import_lyrics_files should count unmatched lyrics."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page

    mock_trepo = MagicMock()
    mock_trepo.watch_all_tracks.return_value = [
        MagicMock(title="Song A", id=1),
    ]

    with patch("data.track_repository", mock_trepo), \
         patch.dict("sys.modules", {
             "logic.encoding_helper": MagicMock(read_with_encoding=MagicMock(return_value="test")),
             "logic.lyrics_parser": MagicMock(),
         }):
        asyncio.run(shell._import_lyrics_files(["/lyrics/Unknown.lrc"]))

    # Should not crash, just not match
    mock_trepo.update_lyrics.assert_not_called()


def test_reload_after_import(mock_page):
    """_reload_after_import should update UI and reload."""
    from ui.shell import ShellView

    shell = ShellView.__new__(ShellView)
    shell._page = mock_page
    mock_app = MagicMock()
    shell.app = mock_app

    mock_trepo = MagicMock()
    mock_trepo.watch_all_tracks.return_value = [MagicMock(), MagicMock()]

    with patch("data.track_repository", mock_trepo):
        asyncio.run(shell._reload_after_import())

    mock_page.update.assert_called()
    mock_app._reload_ui.assert_called_once()
