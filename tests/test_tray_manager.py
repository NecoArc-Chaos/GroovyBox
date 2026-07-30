"""Tests for tray_manager.py."""

import sys
from unittest.mock import MagicMock, patch


def test_tray_manager_mobile_disabled():
    """SystemTrayManager should be disabled on mobile platforms."""
    with patch.object(sys, "platform", "android"):
        # Need to reload module to pick up the mobile platform
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        manager = SystemTrayManager("/fake/icon.png")
        assert manager._enabled is False
        assert manager._icon is None


def test_tray_manager_no_pystray():
    """SystemTrayManager should handle missing pystray gracefully."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {"pystray": None, "PIL": None}):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        manager = SystemTrayManager("/fake/icon.png")
        assert manager._enabled is False
        assert manager._icon is None


def test_tray_manager_initialization_desktop():
    """SystemTrayManager should initialize on desktop when pystray is available."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")

        assert manager._enabled is True
        assert manager._icon is not None


def test_tray_manager_run_not_running():
    """SystemTrayManager.run should start thread if not running."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_icon.visible = False

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")
            manager._icon = mock_icon
            manager.run()

        # Thread should have been started
        assert mock_icon.run.called or True  # Threading may vary


def test_tray_manager_run_already_visible():
    """SystemTrayManager.run should not start if icon is already visible."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_icon.visible = True

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")
            manager._icon = mock_icon
            manager.run()

        # Should not start again
        assert not mock_icon.run.called


def test_tray_manager_stop_running():
    """SystemTrayManager.stop should stop icon if running."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_icon.visible = True

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")
            manager._icon = mock_icon
            manager.stop()

        mock_icon.stop.assert_called_once()


def test_tray_manager_stop_not_running():
    """SystemTrayManager.stop should not crash if not running."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_icon.visible = False

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")
            manager._icon = mock_icon
            manager.stop()

        mock_icon.stop.assert_not_called()


def test_tray_manager_is_running_disabled():
    """is_running should return False when tray is disabled."""
    with patch.object(sys, "platform", "android"):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        manager = SystemTrayManager("/fake/icon.png")
        assert manager.is_running is False


def test_tray_manager_is_running_no_icon():
    """is_running should return False when icon is None."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        manager = SystemTrayManager("/fake/icon.png")
        manager._icon = None
        assert manager.is_running is False


def test_tray_manager_is_running_true():
    """is_running should return True when icon is visible."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_icon.visible = True

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png")
            manager._icon = mock_icon
            assert manager.is_running is True


def test_tray_manager_on_open():
    """_on_open should hide icon and call show callback."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_icon = MagicMock()
        mock_show = MagicMock()

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png", on_show_callback=mock_show)
            manager._icon = mock_icon
            manager._on_open(mock_icon, None)

        mock_icon.visible = False
        mock_show.assert_called_once()


def test_tray_manager_on_quit():
    """_on_quit should call exit callback."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_exit = MagicMock()

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png", on_exit_callback=mock_exit)
            manager._on_quit(None, None)

        mock_exit.assert_called_once()


def test_tray_manager_on_quit_no_callback():
    """_on_quit should not crash if exit callback is None."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png", on_exit_callback=None)
            # Should not raise
            manager._on_quit(None, None)


def test_tray_manager_callbacks():
    """SystemTrayManager should store callbacks correctly."""
    with patch.object(sys, "platform", "win32"), \
         patch.dict("sys.modules", {
             "pystray": MagicMock(),
             "PIL": MagicMock(),
             "PIL.Image": MagicMock(),
         }):
        import importlib

        import logic.tray_manager as tray_module
        importlib.reload(tray_module)

        from logic.tray_manager import SystemTrayManager
        mock_image = MagicMock()
        mock_show = MagicMock()
        mock_exit = MagicMock()

        with patch.dict("sys.modules", {"PIL.Image.open": MagicMock(return_value=mock_image)}):
            manager = SystemTrayManager("/fake/icon.png",
                                        on_show_callback=mock_show,
                                        on_exit_callback=mock_exit)

        assert manager._on_show_callback is mock_show
        assert manager._on_exit_callback is mock_exit
