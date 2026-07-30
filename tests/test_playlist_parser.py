"""Tests for playlist_parser.py."""

import os

import pytest


@pytest.fixture
def tmp_m3u_file(tmp_path):
    """Create a temporary M3U file."""
    m3u = tmp_path / "test.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        "#EXTINF:180,Song A - Artist A\n"
        "music/song_a.mp3\n"
        "# Comment line\n"
        "song_b.mp3\n"
        "\n"
        "music/song_c.mp3\n",
        encoding="utf-8",
    )
    return m3u


@pytest.fixture
def tmp_m3u8_file(tmp_path):
    """Create a temporary M3U8 file (UTF-8 with BOM)."""
    m3u8 = tmp_path / "test.m3u8"
    m3u8.write_bytes(
        b"\xef\xbb\xbf#EXTM3U\n"
        b"#EXTINF:180,Song A\n"
        b"music/song_a.mp3\n"
        b"song_b.mp3\n"
    )
    return m3u8


@pytest.fixture
def tmp_pls_file(tmp_path):
    """Create a temporary PLS file."""
    pls = tmp_path / "test.pls"
    pls.write_text(
        "[playlist]\n"
        "File1=music/song_a.mp3\n"
        "Title1=Song A\n"
        "Length1=180\n"
        "File10=music/song_j.mp3\n"
        "Title10=Song J\n"
        "Length10=200\n"
        "File2=song_b.mp3\n",
        encoding="utf-8",
    )
    return pls


@pytest.fixture
def tmp_gbk_m3u_file(tmp_path):
    """Create a temporary M3U file with GBK encoding."""
    m3u = tmp_path / "test_gbk.m3u"
    content = "#EXTM3U\n#EXTINF:180,歌曲 A\nmusic/song_a.mp3\n"
    m3u.write_bytes(content.encode("gbk"))
    return m3u


def test_parse_m3u_basic(tmp_m3u_file, tmp_path):
    """parse_m3u should return existing audio files."""
    from logic.playlist_parser import parse_m3u

    # Create the referenced files
    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")
    (tmp_path / "music" / "song_c.mp3").write_text("fake")
    (tmp_path / "song_b.mp3").write_text("fake")  # Relative path

    result = parse_m3u(str(tmp_m3u_file))
    assert len(result) == 3
    assert all(os.path.isfile(p) for p in result)


def test_parse_m3u_skips_missing_files(tmp_m3u_file):
    """parse_m3u should skip files that don't exist on disk."""
    from logic.playlist_parser import parse_m3u

    result = parse_m3u(str(tmp_m3u_file))
    assert len(result) == 0


def test_parse_m3u_skips_comments_and_empty(tmp_path):
    """parse_m3u should skip comments and empty lines."""
    from logic.playlist_parser import parse_m3u

    m3u = tmp_path / "empty.m3u"
    m3u.write_text("# Comment\n\n  \n# Another comment\n", encoding="utf-8")

    result = parse_m3u(str(m3u))
    assert len(result) == 0


def test_parse_m3u_utf8_bom(tmp_m3u8_file, tmp_path):
    """parse_m3u should handle UTF-8 BOM encoded files."""
    from logic.playlist_parser import parse_m3u

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")
    (tmp_path / "song_b.mp3").write_text("fake")

    result = parse_m3u(str(tmp_m3u8_file))
    assert len(result) == 2


def test_parse_m3u_gbk_encoding(tmp_gbk_m3u_file, tmp_path):
    """parse_m3u should fallback to GBK encoding."""
    from logic.playlist_parser import parse_m3u

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")

    result = parse_m3u(str(tmp_gbk_m3u_file))
    assert len(result) == 1


def test_parse_m3u_resolves_relative_paths(tmp_m3u_file, tmp_path):
    """parse_m3u should resolve relative paths against playlist directory."""
    from logic.playlist_parser import parse_m3u

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")
    (tmp_path / "song_b.mp3").write_text("fake")  # Relative to playlist dir

    result = parse_m3u(str(tmp_m3u_file))
    assert any("song_a.mp3" in p for p in result)
    assert any("song_b.mp3" in p for p in result)


def test_parse_pls_basic(tmp_pls_file, tmp_path):
    """parse_pls should return existing audio files."""
    from logic.playlist_parser import parse_pls

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")
    (tmp_path / "song_b.mp3").write_text("fake")

    result = parse_pls(str(tmp_pls_file))
    assert len(result) == 2


def test_parse_pls_skips_missing_files(tmp_pls_file):
    """parse_pls should skip files that don't exist."""
    from logic.playlist_parser import parse_pls

    result = parse_pls(str(tmp_pls_file))
    assert len(result) == 0


def test_parse_pls_regex_matching(tmp_path):
    """parse_pls should match FileN=path entries."""
    from logic.playlist_parser import parse_pls

    pls = tmp_path / "test.pls"
    pls.write_text(
        "[playlist]\n"
        "File1=music/song_a.mp3\n"
        "File10=music/song_j.mp3\n"
        "File2=song_b.mp3\n",
        encoding="utf-8",
    )

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")
    (tmp_path / "music" / "song_j.mp3").write_text("fake")
    (tmp_path / "song_b.mp3").write_text("fake")

    result = parse_pls(str(pls))
    assert len(result) == 3


def test_parse_pls_encoding_fallback(tmp_path):
    """parse_pls should try multiple encodings."""
    from logic.playlist_parser import parse_pls

    pls = tmp_path / "test.pls"
    pls.write_bytes(b"[playlist]\nFile1=music/song.mp3\n")

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song.mp3").write_text("fake")

    result = parse_pls(str(pls))
    assert len(result) == 1


def test_parse_playlist_m3u(tmp_m3u_file, tmp_path):
    """parse_playlist should route to parse_m3u for .m3u files."""
    from logic.playlist_parser import parse_playlist

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")

    result = parse_playlist(str(tmp_m3u_file))
    assert len(result) == 1


def test_parse_playlist_m3u8(tmp_m3u8_file, tmp_path):
    """parse_playlist should route to parse_m3u for .m3u8 files."""
    from logic.playlist_parser import parse_playlist

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")

    result = parse_playlist(str(tmp_m3u8_file))
    assert len(result) == 1


def test_parse_playlist_pls(tmp_pls_file, tmp_path):
    """parse_playlist should route to parse_pls for .pls files."""
    from logic.playlist_parser import parse_playlist

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song_a.mp3").write_text("fake")

    result = parse_playlist(str(tmp_pls_file))
    assert len(result) == 1


def test_parse_playlist_unknown_extension(tmp_path):
    """parse_playlist should default to parse_m3u for unknown extensions."""
    from logic.playlist_parser import parse_playlist

    m3u = tmp_path / "test.unknown"
    m3u.write_text("music/song.mp3\n", encoding="utf-8")

    (tmp_path / "music").mkdir(exist_ok=True)
    (tmp_path / "music" / "song.mp3").write_text("fake")

    result = parse_playlist(str(m3u))
    assert len(result) == 1


def test_parse_playlist_nonexistent_file():
    """parse_playlist should return empty list for nonexistent files."""
    from logic.playlist_parser import parse_playlist

    result = parse_playlist("/nonexistent/playlist.m3u")
    assert len(result) == 0


def test_parse_m3u_empty_file(tmp_path):
    """parse_m3u should return empty list for empty files."""
    from logic.playlist_parser import parse_m3u

    m3u = tmp_path / "empty.m3u"
    m3u.write_text("", encoding="utf-8")

    result = parse_m3u(str(m3u))
    assert len(result) == 0


def test_parse_pls_empty_file(tmp_path):
    """parse_pls should return empty list for empty files."""
    from logic.playlist_parser import parse_pls

    pls = tmp_path / "empty.pls"
    pls.write_text("", encoding="utf-8")

    result = parse_pls(str(pls))
    assert len(result) == 0
