"""GroovyBox Application Entry Point.

This module serves as the main entry point for the GroovyBox music player
application built with the Flet framework. It initializes the Flet page
and launches the main application instance.
"""

import os

# HOME writability test: on iOS, Flet sets HOME to the app container root
# which is read-only. Python stdlib (ssl, pip, history) and Flet itself
# depend on a writable HOME. Redirect to Library/Application Support when
# HOME is not writable (iOS sandbox). No-op on desktop.
_home = os.path.expanduser("~")
if not os.access(_home, os.W_OK):
    os.environ["HOME"] = os.path.join(_home, "Library", "Application Support")

import flet as ft
from flet import FilePicker
import flet_audio  # Ensure plugin is detected by build scanner
from app import GroovyBoxApp


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
    # Pre-create FilePicker to ensure Flutter plugin registration.
    # Use public API when available; fall back to internal attribute
    # for older Flet versions or build-scanner detection.
    try:
        # Preferred public API (Flet >= 0.27)
        if not hasattr(page, "file_picker") or page.file_picker is None:
            page.file_picker = FilePicker()
    except Exception:
        # Fallback for build-time plugin detection on some Flet versions
        try:
            page._file_picker = FilePicker()
        except Exception:
            pass
    from data import db
    db.init_database()

    GroovyBoxApp(page)


# Launch the application using Flet's built-in runner
ft.run(main)
