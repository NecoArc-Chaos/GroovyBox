"""Tests for library screen logic."""

import pytest
from unittest.mock import MagicMock
from ui.screens.library_screen import LibraryScreen
from data.models import Track


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.width = 800
    page.session.store = {}
    return page


def test_filter_tracks_empty_query(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Song A", artist="Artist X"),
        Track(title="Song B", artist="Artist Y"),
    ]
    result = screen._filter_tracks(tracks)
    assert len(result) == 2


def test_filter_tracks_by_title(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Song A", artist="Artist X"),
        Track(title="Song B", artist="Artist Y"),
    ]
    screen.search_query = "Song A"
    result = screen._filter_tracks(tracks)
    assert len(result) == 1
    assert result[0].title == "Song A"


def test_filter_tracks_by_artist(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Song A", artist="Artist X"),
        Track(title="Song B", artist="Artist Y"),
    ]
    screen.search_query = "Artist Y"
    result = screen._filter_tracks(tracks)
    assert len(result) == 1
    assert result[0].artist == "Artist Y"


def test_filter_tracks_case_insensitive(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Hello World", artist="Test"),
    ]
    screen.search_query = "hello"
    result = screen._filter_tracks(tracks)
    assert len(result) == 1


def test_filter_tracks_no_match(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Song A", artist="Artist X"),
    ]
    screen.search_query = "Nonexistent"
    result = screen._filter_tracks(tracks)
    assert len(result) == 0


def test_filter_tracks_with_album(mock_page):
    screen = LibraryScreen(mock_page)
    tracks = [
        Track(title="Song A", album="Album1"),
        Track(title="Song B", album="Album2"),
    ]
    screen.search_query = "Album1"
    result = screen._filter_tracks(tracks)
    assert len(result) == 1
    assert result[0].album == "Album1"


def test_toggle_select(mock_page):
    screen = LibraryScreen(mock_page)
    screen.selected_ids = set()
    screen._build = MagicMock()
    screen.update = MagicMock()
    screen._sel_count_text = MagicMock()

    screen._toggle_select(1)
    assert 1 in screen.selected_ids
    screen._build.assert_called_once()
    screen.update.assert_called_once()


def test_toggle_select_deselect(mock_page):
    screen = LibraryScreen(mock_page)
    screen.selected_ids = {1}
    screen._build = MagicMock()
    screen.update = MagicMock()
    screen._sel_tile_refs = {}
    screen._sel_count_text = MagicMock()

    screen._toggle_select(1)
    assert 1 not in screen.selected_ids
    screen._build.assert_called_once()
    screen.update.assert_called_once()


def test_exit_selection_mode(mock_page):
    screen = LibraryScreen(mock_page)
    screen.selected_ids = {1, 2, 3}
    screen._build = MagicMock()
    screen.update = MagicMock()

    screen._exit_selection_mode()
    assert len(screen.selected_ids) == 0
    screen._build.assert_called_once()
    screen.update.assert_called_once()
