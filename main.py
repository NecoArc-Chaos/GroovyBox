"""GroovyBox Application Entry Point.

This module serves as the main entry point for the GroovyBox music player
application built with the Flet framework. It initializes the Flet page
and launches the main application instance.
"""

import os
import traceback

# HOME writability test: on iOS, Flet sets HOME to the app container root
# which is read-only. Python stdlib (ssl, pip, history) and Flet itself
# depend on a writable HOME. Redirect to Library/Application Support when
# HOME is not writable (iOS sandbox). No-op on desktop.
_home = os.path.expanduser("~")
if not os.access(_home, os.W_OK):
    os.environ["HOME"] = os.path.join(_home, "Library", "Application Support")

import flet as ft
from flet import FilePicker, Text
import flet_audio  # Ensure plugin is detected by build scanner


def _show_error(page: ft.Page, title: str, error: Exception):
    """Display a fallback error screen so the user sees something instead of black."""
    try:
        page.views.clear()
        page.views.append(
            ft.View(
                route="/error",
                controls=[
                    Text(f"{title}", size=20, weight=ft.FontWeight.BOLD),
                    Text(str(error), color=ft.Colors.RED),
                ],
            )
        )
        page.update()
    except Exception:
        pass


def main(page: ft.Page):
    """Initialize and run the GroovyBox application.
    
    Pre-creates the FilePicker service at startup so that:
    1. The Flet build scanner detects the required Flutter plugins
       (file_picker, flet_audio) and includes them in the iOS IPA.
    2. The Flutter client registers the invoke-method handlers,
       preventing TimeoutException on mobile.
    
    Args:
        page: The Flet page object provided by the framework.
    """
    try:
        page._file_picker = FilePicker()
        from data import db
        db.init_database()
        from app import GroovyBoxApp
        GroovyBoxApp(page)
        # On Android, page.push_route via run_task can be unreliable during
        # early startup. Force the initial route here so the library screen
        # renders immediately instead of staying on a blank default route.
        try:
            if not page.views:
                page.route = "/library"
        except Exception:
            pass
    except Exception as ex:
        traceback.print_exc()
        _show_error(page, "启动失败", ex)


# Launch the application using Flet's built-in runner
ft.run(main)
