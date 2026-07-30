"""Tests for localization module."""

import pytest

from logic.localize import get_locale, load_locale, tr


@pytest.fixture(autouse=True)
def reset_locale():
    """Reset locale to English between tests."""
    load_locale("en")
    yield
    load_locale("en")


def test_get_locale_default():
    assert get_locale() == "en"


def test_tr_existing_key():
    val = tr("appName")
    assert val == "GroovyBox"
    assert isinstance(val, str)


def test_tr_missing_key_returns_key():
    val = tr("nonexistent_key_xyz")
    assert val == "nonexistent_key_xyz"


def test_tr_with_single_placeholder():
    val = tr("searchTracksWithCount", 5)
    assert "5" in val


def test_tr_with_multiple_placeholders():
    val = tr("searchTracksFiltered", 10, 20)
    assert "10" in val
    assert "20" in val


def test_load_locale_chinese():
    load_locale("zh")
    val = tr("appName")
    assert val == "聆阁"  # Chinese translation of appName
    load_locale("en")


def test_tr_unknown_artist():
    val = tr("unknownArtist", "Unknown Artist")
    # unknownArtist key doesn't exist in locale, falls back to key with arg
    assert "Unknown Artist" in val or val == "unknownArtist"
