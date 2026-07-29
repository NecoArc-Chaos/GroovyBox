"""Tests for player screen logic."""

import pytest
from unittest.mock import MagicMock
from ui.screens.player_screen import PlayerScreen
from data.models import Track, CurrentTrackData


@pytest.fixture
def page_mock():
    page = MagicMock()
    page.width = 1000
    store = MagicMock()
    store.get.return_value = None
    page.session.store = store
    page.update = MagicMock()
    return page


def test_progress_ratio(page_mock):
    screen = PlayerScreen(page_mock)
    assert screen._progress_ratio(0, 1000) == 0.0
    assert screen._progress_ratio(500, 1000) == 0.5
    assert screen._progress_ratio(1000, 1000) == 1.0
    assert screen._progress_ratio(1500, 1000) == 1.0  # Clamp
    assert screen._progress_ratio(-100, 1000) == 0.0  # Clamp


def test_cycle_view(page_mock):
    screen = PlayerScreen(page_mock)
    screen._rebuild = MagicMock()
    page_mock.session.store.get.return_value = None

    screen.cycle_view()
    assert screen._view_mode == "lyrics"
    screen._rebuild.assert_called_once()


def test_toggle_queue(page_mock):
    screen = PlayerScreen(page_mock)
    screen._rebuild = MagicMock()
    page_mock.session.store.get.return_value = None

    screen._view_mode = "cover"
    screen.toggle_queue()
    assert screen._view_mode == "queue"
    screen._rebuild.assert_called_once()


def test_refresh_position_updates_slider(page_mock):
    screen = PlayerScreen(page_mock)
    screen._pos_slider = MagicMock()
    screen._pos_text = MagicMock()
    screen._dur_text = MagicMock()
    screen._cached_dur = 1000

    screen.refresh_position(500, 1000)
    screen._pos_slider.update.assert_called_once()
    screen._pos_text.update.assert_called_once()
    screen._dur_text.update.assert_called_once()


def test_refresh_play_state(page_mock):
    screen = PlayerScreen(page_mock)
    screen._play_btn = MagicMock()

    screen.refresh_play_state(True)
    screen._play_btn.update.assert_called_once()


def test_get_app(page_mock):
    screen = PlayerScreen(page_mock)
    page_mock.session.store.get.return_value = "test_app"
    assert screen._get_app() == "test_app"


def test_get_player(page_mock):
    screen = PlayerScreen(page_mock)
    mock_player = MagicMock()
    mock_app = MagicMock()
    mock_app.audio_player = mock_player
    page_mock.session.store.get.return_value = mock_app
    assert screen._get_player() == mock_player


def test_get_player_no_app(page_mock):
    screen = PlayerScreen(page_mock)
    page_mock.session.store.get.return_value = None
    assert screen._get_player() is None
