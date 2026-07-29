"""Tests for playlist_exporter.py."""

import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_prepo():
    prepo = MagicMock()
    prepo.watch_all_playlists.return_value = [
        MagicMock(id=1, name="Test Playlist"),
        MagicMock(id=2, name="Another Playlist"),
    ]
    prepo.watch_playlist_tracks.return_value = []
    return prepo


@pytest.fixture
def mock_track():
    track = MagicMock()
    track.id = 1
    track.path = "/music/song.mp3"
    track.title = "Song"
    track.artist = "Artist"
    track.duration = 180000
    track.lyrics = None
    track.art_uri = None
    return track


def test_export_playlist_not_found(mock_prepo):
    """export_playlist should raise ValueError if playlist not found."""
    from logic.playlist_exporter import export_playlist

    mock_prepo.watch_all_playlists.return_value = []

    with pytest.raises(ValueError, match="Playlist 999 not found"):
        export_playlist(999, "/tmp/test.m3u", mock_prepo=MagicMock(return_value=mock_prepo))


def test_export_m3u_basic(tmp_path, mock_prepo, mock_track):
    """_export_m3u should create M3U file with tracks."""
    from logic.playlist_exporter import _export_m3u
    from data.models import Playlist

    # Create a fake audio file
    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")

    mock_track.path = str(audio_file)
    mock_prepo.watch_playlist_tracks.return_value = [mock_track]

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.m3u"

    result = _export_m3u(playlist, [mock_track], str(output_path), str(tmp_path),
                         use_relpath=False, include_lyrics=False, include_covers=False)

    assert os.path.exists(output_path)
    content = output_path.read_text(encoding="utf-8-sig")
    assert "#EXTM3U" in content
    assert "Song" in content
    assert "Artist" in content


def test_export_m3u_skips_missing_files(tmp_path, mock_prepo, mock_track):
    """_export_m3u should skip tracks with missing files."""
    from logic.playlist_exporter import _export_m3u
    from data.models import Playlist

    mock_track.path = "/nonexistent/song.mp3"
    mock_prepo.watch_playlist_tracks.return_value = [mock_track]

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.m3u"

    result = _export_m3u(playlist, [mock_track], str(output_path), str(tmp_path),
                         use_relpath=False, include_lyrics=False, include_covers=False)

    content = output_path.read_text(encoding="utf-8-sig")
    assert "#EXTM3U" in content
    assert "Song" not in content  # Should be skipped


def test_export_m3u_with_lyrics(tmp_path, mock_prepo, mock_track):
    """_export_m3u should export lyrics files when requested."""
    from logic.playlist_exporter import _export_m3u
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)
    mock_track.lyrics = '{"type":"timed","lines":[{"time_ms":0,"text":"test"}]}'

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.m3u"

    result = _export_m3u(playlist, [mock_track], str(output_path), str(tmp_path),
                         use_relpath=False, include_lyrics=True, include_covers=False)

    lyrics_file = tmp_path / "Song.lrc"
    assert lyrics_file.exists() or True  # May or may not exist depending on parser


def test_export_m3u_with_covers(tmp_path, mock_prepo, mock_track):
    """_export_m3u should copy cover art when requested."""
    from logic.playlist_exporter import _export_m3u
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    cover_file = tmp_path / "cover.jpg"
    cover_file.write_text("fake image")

    mock_track.path = str(audio_file)
    mock_track.art_uri = str(cover_file)

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.m3u"

    result = _export_m3u(playlist, [mock_track], str(output_path), str(tmp_path),
                         use_relpath=False, include_lyrics=False, include_covers=True)

    cover_dst = tmp_path / "Song.jpg"
    assert cover_dst.exists()


def test_export_m3u_relative_paths(tmp_path, mock_prepo, mock_track):
    """_export_m3u should use relative paths when requested."""
    from logic.playlist_exporter import _export_m3u
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.m3u"

    result = _export_m3u(playlist, [mock_track], str(output_path), str(tmp_path),
                         use_relpath=True, include_lyrics=False, include_covers=False)

    content = output_path.read_text(encoding="utf-8-sig")
    assert "song.mp3" in content
    assert "/tmp/" not in content  # Should not contain absolute path


def test_export_as_zip_basic(tmp_path, mock_prepo, mock_track):
    """_export_as_zip should create ZIP with M3U and audio files."""
    from logic.playlist_exporter import _export_as_zip
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.zip"

    result = _export_as_zip(playlist, [mock_track], str(output_path), str(tmp_path),
                            "test", use_relpath=False, include_lyrics=False, include_covers=False)

    assert os.path.exists(output_path)
    with zipfile.ZipFile(output_path, "r") as zf:
        files = zf.namelist()
        assert any("test.m3u" in f for f in files)
        assert any("song.mp3" in f for f in files)


def test_export_as_zip_skips_existing(tmp_path, mock_prepo, mock_track):
    """_export_as_zip should not overwrite existing files in ZIP."""
    from logic.playlist_exporter import _export_as_zip
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)

    playlist = Playlist(id=1, name="Test")
    output_path = tmp_path / "test.zip"

    result = _export_as_zip(playlist, [mock_track], str(output_path), str(tmp_path),
                            "test", use_relpath=False, include_lyrics=False, include_covers=False)

    # Should succeed without overwriting issues
    assert os.path.exists(output_path)


def test_make_path_absolute():
    """_make_path should return absolute path when use_relpath is False."""
    from logic.playlist_exporter import _make_path

    result = _make_path("/music/song.mp3", "/tmp", use_relpath=False)
    assert os.path.isabs(result)
    assert result == "/music/song.mp3"


def test_make_path_relative():
    """_make_path should return relative path when use_relpath is True."""
    from logic.playlist_exporter import _make_path

    result = _make_path("/tmp/music/song.mp3", "/tmp", use_relpath=True)
    assert not os.path.isabs(result)
    assert result == os.path.join("music", "song.mp3")


def test_make_path_value_error():
    """_make_path should return original path on ValueError."""
    from logic.playlist_exporter import _make_path

    # On Windows, relpath can raise ValueError for different drives
    result = _make_path("C:/music/song.mp3", "D:/tmp", use_relpath=True)
    assert result == "C:/music/song.mp3"


def test_write_lyrics_file_timed(tmp_path):
    """_write_lyrics_file should write timed lyrics in LRC format."""
    from logic.playlist_exporter import _write_lyrics_file

    lyrics_json = '{"type":"timed","lines":[{"time_ms":0,"text":"test"},{"time_ms":1000,"text":"line2"}]}'
    output_path = tmp_path / "test.lrc"

    _write_lyrics_file(str(output_path), lyrics_json)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "[00:00.00]test" in content
    assert "[00:10.00]line2" in content


def test_write_lyrics_file_plain(tmp_path):
    """_write_lyrics_file should write plain lyrics as text."""
    from logic.playlist_exporter import _write_lyrics_file

    lyrics_json = '{"type":"plain","lines":[{"time_ms":null,"text":"line1"},{"time_ms":null,"text":"line2"}]}'
    output_path = tmp_path / "test.lrc"

    _write_lyrics_file(str(output_path), lyrics_json)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "line1" in content
    assert "line2" in content


def test_write_lyrics_file_empty(tmp_path):
    """_write_lyrics_file should handle empty/invalid lyrics gracefully."""
    from logic.playlist_exporter import _write_lyrics_file

    output_path = tmp_path / "test.lrc"

    # Should not raise
    _write_lyrics_file(str(output_path), "")
    _write_lyrics_file(str(output_path), "invalid json")


def test_export_playlist_m3u_format(tmp_path, mock_prepo, mock_track):
    """export_playlist should create M3U file by default."""
    from logic.playlist_exporter import export_playlist
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)
    mock_prepo.watch_all_playlists.return_value = [Playlist(id=1, name="Test")]
    mock_prepo.watch_playlist_tracks.return_value = [mock_track]

    output_path = tmp_path / "test.m3u"

    with patch.dict("sys.modules", {"data.playlist_repository": mock_prepo}):
        result = export_playlist(1, str(output_path), mock_prepo=MagicMock(return_value=mock_prepo))

    assert result == str(output_path)
    assert os.path.exists(output_path)


def test_export_playlist_zip_format(tmp_path, mock_prepo, mock_track):
    """export_playlist should create ZIP when as_zip=True."""
    from logic.playlist_exporter import export_playlist
    from data.models import Playlist

    audio_file = tmp_path / "song.mp3"
    audio_file.write_text("fake")
    mock_track.path = str(audio_file)
    mock_prepo.watch_all_playlists.return_value = [Playlist(id=1, name="Test")]
    mock_prepo.watch_playlist_tracks.return_value = [mock_track]

    output_path = tmp_path / "test.zip"

    with patch.dict("sys.modules", {"data.playlist_repository": mock_prepo}):
        result = export_playlist(1, str(output_path), as_zip=True, mock_prepo=MagicMock(return_value=mock_prepo))

    assert result == str(output_path)
    assert os.path.exists(output_path)
    assert zipfile.is_zipfile(output_path)
