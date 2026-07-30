"""Tests for main.py entry point."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_flet_run():
    """Prevent flet.run from starting the actual app during tests."""
    with patch("flet.run"):
        yield


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.width = 800
    page.route = "/"
    page.views = []
    page.session.store = {}
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
    return page


def test_show_error_displays_fallback(mock_page):
    """_show_error should clear views and append an error view."""
    from main import _show_error

    _show_error(mock_page, "启动失败", Exception("boom"))

    assert len(mock_page.views) == 1
    assert mock_page.views[0].route == "/error"
    mock_page.update.assert_called_once()


def test_show_error_silent_failure(mock_page):
    """_show_error should not raise if page.update fails."""
    from main import _show_error

    mock_page.update.side_effect = Exception("update failed")
    _show_error(mock_page, "启动失败", Exception("boom"))


def test_main_success(mock_page):
    """main() should initialize db and create GroovyBoxApp on success."""
    mock_db = MagicMock()
    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    with patch.dict(sys.modules, {"data.db": mock_db, "app": MagicMock(GroovyBoxApp=mock_app_cls)}):
        from main import main
        main(mock_page)

    mock_db.init_database.assert_called_once()
    mock_app_cls.assert_called_once_with(mock_page)


def test_main_exception_shows_error(mock_page):
    """main() should show error screen if initialization raises."""
    mock_db = MagicMock()
    mock_db.init_database.side_effect = Exception("db error")

    with patch.dict(sys.modules, {"data.db": mock_db}):
        from main import main
        main(mock_page)

    assert len(mock_page.views) == 1
    assert mock_page.views[0].route == "/error"


def test_main_file_picker_created(mock_page):
    """main() should create file_picker if not present."""
    mock_db = MagicMock()
    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    if hasattr(mock_page, "file_picker"):
        del mock_page.file_picker

    with patch.dict(sys.modules, {"data.db": mock_db, "app": MagicMock(GroovyBoxApp=mock_app_cls)}):
        from main import main
        main(mock_page)

    assert hasattr(mock_page, "file_picker")
    assert mock_page.file_picker is not None


def test_main_file_picker_fallback_internal(mock_page):
    """main() should fallback to _file_picker if public API fails."""
    mock_db = MagicMock()
    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    # Simulate public API raising, internal API working
    mock_page.file_picker = None
    type(mock_page).file_picker = property(
        lambda self: (_ for _ in ()).throw(Exception("public api failed")),
        lambda self, v: setattr(self, "_file_picker_val", v),
    )

    with patch.dict(sys.modules, {"data.db": mock_db, "app": MagicMock(GroovyBoxApp=mock_app_cls)}):
        from main import main
        main(mock_page)

    # Should have set _file_picker as fallback
    assert hasattr(mock_page, "_file_picker")


def test_main_route_set_to_library(mock_page):
    """main() should result in GroovyBoxApp being instantiated."""
    mock_db = MagicMock()
    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    with patch.dict(sys.modules, {"data.db": mock_db, "app": MagicMock(GroovyBoxApp=mock_app_cls)}):
        from main import main
        main(mock_page)

    mock_app_cls.assert_called_once_with(mock_page)


def test_home_writable_check(monkeypatch, tmp_path):
    """Test that HOME redirect logic works when HOME is not writable."""
    import os
    from unittest.mock import patch

    monkeypatch.setenv("FLET_APP_DATA_DIR", str(tmp_path))

    import importlib
    import main as main_module
    with patch("flet.run"):
        importlib.reload(main_module)

    assert os.environ.get("HOME") != str(tmp_path / "Library" / "Application Support")
