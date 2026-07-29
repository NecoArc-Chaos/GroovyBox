"""Tests for key_bindings.py."""

import pytest


def test_default_key_bindings_keys():
    """DEFAULT_KEY_BINDINGS should contain all expected actions."""
    from logic.key_bindings import DEFAULT_KEY_BINDINGS

    expected_keys = [
        "play_pause",
        "next_track",
        "prev_track",
        "volume_up",
        "volume_down",
        "seek_back",
        "seek_forward",
        "exit_player",
    ]
    for key in expected_keys:
        assert key in DEFAULT_KEY_BINDINGS


def test_default_key_bindings_values():
    """DEFAULT_KEY_BINDINGS should have correct default values."""
    from logic.key_bindings import DEFAULT_KEY_BINDINGS

    assert DEFAULT_KEY_BINDINGS["play_pause"] == "Space"
    assert DEFAULT_KEY_BINDINGS["next_track"] == "N"
    assert DEFAULT_KEY_BINDINGS["prev_track"] == "B"
    assert DEFAULT_KEY_BINDINGS["volume_up"] == "Arrow Up"
    assert DEFAULT_KEY_BINDINGS["volume_down"] == "Arrow Down"
    assert DEFAULT_KEY_BINDINGS["seek_back"] == "Arrow Left"
    assert DEFAULT_KEY_BINDINGS["seek_forward"] == "Arrow Right"
    assert DEFAULT_KEY_BINDINGS["exit_player"] == "Escape"


def test_action_names_mapping():
    """ACTION_NAMES should map action keys to localization keys."""
    from logic.key_bindings import ACTION_NAMES

    assert ACTION_NAMES["play_pause"] == "playPause"
    assert ACTION_NAMES["next_track"] == "nextTrack"
    assert ACTION_NAMES["prev_track"] == "previousTrack"
    assert ACTION_NAMES["volume_up"] == "volumeUp"
    assert ACTION_NAMES["volume_down"] == "volumeDown"
    assert ACTION_NAMES["seek_back"] == "seekBack"
    assert ACTION_NAMES["seek_forward"] == "seekForward"
    assert ACTION_NAMES["exit_player"] == "exitPlayer"


def test_action_order_list():
    """ACTION_ORDER should list all actions in display order."""
    from logic.key_bindings import ACTION_ORDER

    assert len(ACTION_ORDER) == 8
    assert ACTION_ORDER[0] == "play_pause"
    assert ACTION_ORDER[1] == "next_track"
    assert ACTION_ORDER[2] == "prev_track"
    assert ACTION_ORDER[3] == "volume_up"
    assert ACTION_ORDER[4] == "volume_down"
    assert ACTION_ORDER[5] == "seek_back"
    assert ACTION_ORDER[6] == "seek_forward"
    assert ACTION_ORDER[7] == "exit_player"


def test_action_order_matches_defaults():
    """ACTION_ORDER should contain all keys from DEFAULT_KEY_BINDINGS."""
    from logic.key_bindings import ACTION_ORDER, DEFAULT_KEY_BINDINGS

    assert set(ACTION_ORDER) == set(DEFAULT_KEY_BINDINGS.keys())


def test_action_names_matches_defaults():
    """ACTION_NAMES should contain all keys from DEFAULT_KEY_BINDINGS."""
    from logic.key_bindings import ACTION_NAMES, DEFAULT_KEY_BINDINGS

    assert set(ACTION_NAMES.keys()) == set(DEFAULT_KEY_BINDINGS.keys())


def test_default_key_bindings_immutable_copy():
    """DEFAULT_KEY_BINDINGS should be a dict (mutable, but that's expected)."""
    from logic.key_bindings import DEFAULT_KEY_BINDINGS

    # Just verify it's a dict
    assert isinstance(DEFAULT_KEY_BINDINGS, dict)


def test_action_names_localization_keys():
    """ACTION_NAMES values should be valid localization key strings."""
    from logic.key_bindings import ACTION_NAMES

    for key, value in ACTION_NAMES.items():
        assert isinstance(value, str)
        assert len(value) > 0
        # Should be camelCase or similar
        assert value.isalpha() or "_" in value or any(c.isupper() for c in value)
