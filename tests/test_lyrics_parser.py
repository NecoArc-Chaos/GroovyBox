"""Tests for lyrics parser module."""

from logic.lyrics_parser import LyricsData, LyricsLine, lyrics_from_json, lyrics_to_json, parse


def test_parse_lrc():
    content = "[00:12.34]Hello\n[00:15.00]World"
    data = parse(content, "test.lrc")
    assert data.type == "timed"
    assert len(data.lines) == 2
    assert data.lines[0].text == "Hello"
    assert data.lines[0].time_ms == 12340
    assert data.lines[1].text == "World"
    assert data.lines[1].time_ms == 15000


def test_parse_srt():
    content = """1
00:00:20,000 --> 00:00:24,400
Hello world

2
00:00:25,000 --> 00:00:28,000
Second line"""
    data = parse(content, "test.srt")
    assert data.type == "timed"
    assert len(data.lines) == 2
    assert data.lines[0].text == "Hello world"
    assert data.lines[0].time_ms == 20000
    assert data.lines[1].text == "Second line"
    assert data.lines[1].time_ms == 25000


def test_parse_plaintext():
    content = "Line 1\nLine 2\n\nLine 3"
    data = parse(content, "test.txt")
    assert data.type == "plain"
    assert len(data.lines) == 3
    assert data.lines[0].text == "Line 1"
    assert data.lines[2].text == "Line 3"


def test_lyrics_roundtrip():
    data = LyricsData(
        type="timed",
        lines=[LyricsLine(time_ms=1000, text="A"), LyricsLine(time_ms=2000, text="B")],
    )
    json_str = lyrics_to_json(data)
    restored = lyrics_from_json(json_str)
    assert restored.type == "timed"
    assert len(restored.lines) == 2
    assert restored.lines[0].text == "A"
    assert restored.lines[0].time_ms == 1000
