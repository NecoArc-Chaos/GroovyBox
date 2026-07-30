"""Pytest configuration and shared fixtures."""

import sys
from unittest.mock import patch

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
