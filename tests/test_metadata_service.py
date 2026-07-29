"""Tests for metadata service module."""

import pytest
from logic.metadata_service import get_metadata, format_duration, SUPPORTED_EXTENSIONS


def test_format_duration_none():
    assert format_duration(None) == "--:--"


def test_format_duration_seconds():
    assert format_duration(0) == "0:00"
    assert format_duration(1000) == "0:01"
    assert format_duration(65000) == "1:05"
    assert format_duration(125000) == "2:05"


def test_get_metadata_missing_file():
    meta = get_metadata("/nonexistent/path.mp3")
    assert meta.title is None
    assert meta.artist is None
    assert meta.duration is None
    assert meta.art_bytes is None


def test_supported_extensions_non_empty():
    assert len(SUPPORTED_EXTENSIONS) > 0
    assert ".mp3" in SUPPORTED_EXTENSIONS
    assert ".flac" in SUPPORTED_EXTENSIONS
