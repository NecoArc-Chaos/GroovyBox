"""Tests for audio handler module."""

import pytest
from unittest.mock import MagicMock
from logic.audio_handler import AudioPlayer
from data import db


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.services = []
    page.update = MagicMock()
    db.init_database()
    return page


def test_audio_player_initialization(mock_page):
    player = AudioPlayer(mock_page)
    assert player.queue == []
    assert player.current_index == -1
    assert player.is_playing is False
    assert player.position_ms == 0
    assert player.volume > 0


def test_play_track_file_not_found(mock_page):
    player = AudioPlayer(mock_page)
    track = MagicMock()
    track.path = "/nonexistent/file.mp3"
    track.title = "Missing"
    player.on_missing_tracks = MagicMock()
    player.play_track(track)
    player.on_missing_tracks.assert_called_once()


def test_set_volume_bounds(mock_page):
    player = AudioPlayer(mock_page)
    player.set_volume(1.5)
    assert player.volume <= 1.0
    player.set_volume(-0.5)
    assert player.volume >= 0.0


def test_volume_persists_to_db(mock_page):
    player = AudioPlayer(mock_page)
    player.set_volume(0.5)
    assert db.get_setting("player_volume") == "0.5"


def test_shutdown_idempotent(mock_page):
    player = AudioPlayer(mock_page)
    player.shutdown()
    player.shutdown()  # Should not raise
    assert player._timer_active is False


def test_shutdown_stops_timer(mock_page):
    player = AudioPlayer(mock_page)
    player.shutdown()
    assert player._timer_active is False
