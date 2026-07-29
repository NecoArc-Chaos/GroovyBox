"""Pytest configuration and shared fixtures."""

import sys
from unittest.mock import patch, MagicMock

import pytest

# Patch flet.run before any test modules are imported to prevent
# the app from launching during test collection/import.
_patcher = patch("flet.run")
_patcher.start()

# Also patch pystray/PIL imports to avoid display issues in CI
_pystray_patcher = patch.dict(sys.modules, {
    "pystray": None,
    "PIL": None,
    "PIL.Image": None,
})
_pystray_patcher.start()

# Create a global mock for data.db to avoid requiring a real database
_mock_db = MagicMock()
_mock_db.get_setting.return_value = ""
_mock_db.get_connection.return_value.__enter__ = MagicMock(return_value=MagicMock(
    execute=MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[]))
))
_mock_db.get_connection.return_value.__exit__ = MagicMock(return_value=False)

# Patch data.db and all its usages at module level
_db_patcher = patch.dict(sys.modules, {
    "data.db": _mock_db,
})
_db_patcher.start()

# Also patch db in modules that import it directly
_ui_shell_db_patcher = patch("ui.shell.db", _mock_db)
_ui_shell_db_patcher.start()

_settings_db_patcher = patch("ui.screens.settings_screen.db", _mock_db)
_settings_db_patcher.start()


@pytest.fixture(autouse=True)
def mock_db_reads():
    """Provide the mock database to tests that need it."""
    yield _mock_db
