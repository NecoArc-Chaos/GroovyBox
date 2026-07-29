import threading
import sys

# pystray is desktop-only and imports X11/AppKit backends at module load time,
# which crashes on Android/iOS. Guard by platform so mobile never attempts it.
_MOBILE = sys.platform in ("android", "ios")
if not _MOBILE:
    try:
        import pystray
        from PIL import Image
        _HAS_TRAY = True
    except Exception:
        _HAS_TRAY = False
else:
    _HAS_TRAY = False


class SystemTrayManager:
    def __init__(self, icon_path, on_show_callback=None, on_exit_callback=None):
        self._icon = None
        self._on_show_callback = on_show_callback
        self._on_exit_callback = on_exit_callback
        self._enabled = _HAS_TRAY

        if not _HAS_TRAY:
            return

        image = Image.open(icon_path)

        menu = pystray.Menu(
            pystray.MenuItem("Open GroovyBox", self._on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_quit),
        )

        self._icon = pystray.Icon(
            "groovybox",
            icon=image,
            title="GroovyBox",
            menu=menu,
        )

    def run(self):
        if not self._enabled or not self._icon or self._icon.visible:
            return
        threading.Thread(target=self._icon.run, daemon=True).start()

    def stop(self):
        if self._enabled and self._icon and self._icon.visible:
            self._icon.stop()

    @property
    def is_running(self):
        return self._enabled and self._icon is not None and self._icon.visible

    def _on_open(self, icon, item):
        icon.visible = False
        if self._on_show_callback:
            self._on_show_callback()

    def _on_quit(self, icon, item):
        if self._on_exit_callback:
            self._on_exit_callback()
