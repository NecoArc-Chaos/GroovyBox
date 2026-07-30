"""Tests for play mode logic."""

from unittest.mock import MagicMock

import flet as ft
import pytest

from logic.play_mode import cycle_play_mode, get_play_mode_icon


@pytest.fixture
def mock_page():
    page = MagicMock()
    store = {}
    page.session.store = store
    return page


def test_cycle_play_mode_sequential_to_repeat_all(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "none"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    cycle_play_mode(mock_page)
    assert player.shuffle is False
    assert player.repeat_mode == "all"


def test_cycle_play_mode_shuffle_to_sequential(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = True
    player.repeat_mode = "none"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    cycle_play_mode(mock_page)
    assert player.shuffle is False
    assert player.repeat_mode == "none"


def test_cycle_play_mode_repeat_all_to_repeat_one(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "all"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    cycle_play_mode(mock_page)
    assert player.shuffle is False
    assert player.repeat_mode == "one"


def test_cycle_play_mode_repeat_one_to_shuffle(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "one"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    cycle_play_mode(mock_page)
    assert player.shuffle is True
    assert player.repeat_mode == "none"


def test_get_play_mode_icon_shuffle(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = True
    player.repeat_mode = "none"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    icon, color = get_play_mode_icon(mock_page)
    assert icon == ft.Icons.SHUFFLE
    assert color == ft.Colors.PRIMARY


def test_get_play_mode_icon_repeat_one(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "one"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    icon, color = get_play_mode_icon(mock_page)
    assert icon == ft.Icons.REPEAT_ONE
    assert color == ft.Colors.PRIMARY


def test_get_play_mode_icon_repeat_all(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "all"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    icon, color = get_play_mode_icon(mock_page)
    assert icon == ft.Icons.REPEAT
    assert color == ft.Colors.PRIMARY


def test_get_play_mode_icon_none(mock_page):
    from data import db
    db.init_database()
    from logic.audio_handler import AudioPlayer
    player = AudioPlayer(mock_page)
    player.shuffle = False
    player.repeat_mode = "none"
    store = mock_page.session.store
    store["app"] = MagicMock()
    store["app"].audio_player = player

    icon, color = get_play_mode_icon(mock_page)
    assert icon == ft.Icons.REPEAT
    assert color == ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)


def test_get_play_mode_icon_no_app(mock_page):
    mock_page.session.store = {}
    icon, color = get_play_mode_icon(mock_page)
    assert icon == ft.Icons.REPEAT
    assert color == ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)
