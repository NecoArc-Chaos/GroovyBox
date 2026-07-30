"""Tests for library screen logic."""

import pytest
from unittest.mock import MagicMock, patch
from ui.screens.library_screen import LibraryScreen
from data.models import Track


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.width = 800
    page.session.store = {}
    return page


def _make_track(tid, title="Song", artist="Artist", album="Album", path="/music/song.mp3"):
    t = MagicMock()
    t.id = tid
    t.title = title
    t.artist = artist
    t.album = album
    t.path = path
    return t


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


# === Extended tests ===

def test_build_handles_exception_gracefully(mock_page):
    """LibraryScreen._build should show error view on exception."""
    with patch.dict("sys.modules", {"data.track_repository": MagicMock(watch_all_tracks=MagicMock(return_value=[]))}):
        screen = LibraryScreen(mock_page)

    with patch.object(screen, "_build_large_layout", side_effect=Exception("boom")):
        screen._build()

    assert len(screen.controls) > 0
    container = screen.controls[0]
    assert hasattr(container, "content")


def test_filter_tracks_by_artist_and_album(mock_page):
    """_filter_tracks should match artist and album."""
    screen = LibraryScreen(mock_page)
    tracks = [
        _make_track(1, "Song A", "Artist X", "Album1"),
        _make_track(2, "Song B", "Artist Y", "Album2"),
        _make_track(3, "Song C", "Artist X", "Album1"),
    ]
    screen.search_query = "Artist X"
    result = screen._filter_tracks(tracks)
    assert len(result) == 2
    assert all(t.artist == "Artist X" for t in result)


def test_filter_tracks_by_album(mock_page):
    """_filter_tracks should match album field."""
    screen = LibraryScreen(mock_page)
    tracks = [
        _make_track(1, "Song A", "Artist X", "Album1"),
        _make_track(2, "Song B", "Artist Y", "Album2"),
    ]
    screen.search_query = "Album2"
    result = screen._filter_tracks(tracks)
    assert len(result) == 1
    assert result[0].album == "Album2"


def test_build_track_tiles_with_missing_set(mock_page):
    """_build_track_tiles should mark missing tracks correctly."""
    screen = LibraryScreen(mock_page)
    tracks = [_make_track(1, "Song", "Artist")]
    missing_set = {1}
    tiles = screen._build_track_tiles(tracks, missing_set)
    assert len(tiles) == 1
    assert tiles[0].is_missing is True


def test_build_track_tiles_without_missing_set(mock_page):
    """_build_track_tiles should default missing_set to empty set."""
    screen = LibraryScreen(mock_page)
    tracks = [_make_track(1, "Song", "Artist")]
    tiles = screen._build_track_tiles(tracks)
    assert len(tiles) == 1
    assert tiles[0].is_missing is False


def test_search_debounce_cancels_previous(mock_page):
    """_search_debounce should cancel previous timer."""
    screen = LibraryScreen(mock_page)
    screen._search_timer = MagicMock()
    screen._search_debounce()
    screen._search_timer.cancel.assert_called_once()


def test_on_search_change_updates_query(mock_page):
    """on_search_change should update search_query."""
    screen = LibraryScreen(mock_page)
    screen._build = MagicMock()
    screen.update = MagicMock()

    event = MagicMock()
    event.control.value = "test query"
    screen._on_search_change(event)

    assert screen.search_query == "test query"
    screen._build.assert_called_once()
    screen.update.assert_called_once()


def test_toggle_select_enters_selection_mode(mock_page):
    """_toggle_select should rebuild when entering selection mode."""
    screen = LibraryScreen(mock_page)
    screen.selected_ids = set()
    screen._build = MagicMock()
    screen.update = MagicMock()
    screen._sel_count_text = MagicMock()

    screen._toggle_select(1)

    assert 1 in screen.selected_ids
    screen._build.assert_called_once()
    screen.update.assert_called_once()


def test_toggle_select_exits_selection_mode(mock_page):
    """_toggle_select should rebuild when exiting selection mode."""
    screen = LibraryScreen(mock_page)
    screen.selected_ids = {1}
    screen._build = MagicMock()
    screen.update = MagicMock()
    screen._sel_count_text = MagicMock()
    screen._sel_tile_refs = {}

    screen._toggle_select(1)

    assert 1 not in screen.selected_ids
    screen._build.assert_called_once()
    screen.update.assert_called_once()


def test_play_track_delegates_to_app(mock_page):
    """_play_track should call app.audio_player.play_track."""
    screen = LibraryScreen(mock_page)
    mock_app = MagicMock()
    mock_page.session.store = {"app": mock_app}
    track = _make_track(1, "Test", "Artist")

    screen._play_track(track)

    mock_app.audio_player.play_track.assert_called_once_with(track)


def test_play_track_no_app_logs_error(mock_page):
    """_play_track should log error when app is None."""
    screen = LibraryScreen(mock_page)
    mock_page.session.store = {}
    track = _make_track(1)

    with patch("ui.screens.library_screen.logger") as mock_logger:
        screen._play_track(track)
    mock_logger.error.assert_called_once()
