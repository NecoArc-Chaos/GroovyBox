import threading
import pystray
from PIL import Image


class SystemTrayManager:
    def __init__(self, icon_path, on_show_callback=None, on_exit_callback=None):
        self._icon = None
        self._on_show_callback = on_show_callback
        self._on_exit_callback = on_exit_callback

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
        if self._icon and not self._icon.visible:
            threading.Thread(target=self._icon.run, daemon=True).start()

    def stop(self):
        if self._icon and self._icon.visible:
            self._icon.stop()

    @property
    def is_running(self):
        return self._icon is not None and self._icon.visible

    def _on_open(self, icon, item):
        icon.visible = False
        if self._on_show_callback:
            self._on_show_callback()

    def _on_quit(self, icon, item):
        if self._on_exit_callback:
            self._on_exit_callback()
