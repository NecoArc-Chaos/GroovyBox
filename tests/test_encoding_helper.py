"""Tests for encoding_helper.py."""

import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def utf8_file(tmp_path):
    """Create a UTF-8 encoded text file."""
    f = tmp_path / "test_utf8.txt"
    f.write_text("Hello, World!", encoding="utf-8")
    return f


@pytest.fixture
def gbk_file(tmp_path):
    """Create a GBK encoded text file."""
    f = tmp_path / "test_gbk.txt"
    f.write_bytes("你好，世界！".encode("gbk"))
    return f


@pytest.fixture
def utf8_bom_file(tmp_path):
    """Create a UTF-8 with BOM encoded text file."""
    f = tmp_path / "test_bom.txt"
    f.write_bytes(b"\xef\xbb\xbfHello, BOM!")
    return f


@pytest.fixture
def utf16_le_file(tmp_path):
    """Create a UTF-16 LE encoded text file."""
    f = tmp_path / "test_utf16.txt"
    f.write_bytes("Hello, UTF-16!".encode("utf-16-le"))
    return f


def test_detect_by_bom_utf8_sig(tmp_path):
    """_detect_by_bom should detect UTF-8 BOM."""
    from logic.encoding_helper import _detect_by_bom

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfHello")
    assert _detect_by_bom(str(f)) == "utf-8-sig"


def test_detect_by_bom_utf16_le(tmp_path):
    """_detect_by_bom should detect UTF-16 LE BOM."""
    from logic.encoding_helper import _detect_by_bom

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xff\xfeH\x00e\x00")
    assert _detect_by_bom(str(f)) == "utf-16-le"


def test_detect_by_bom_utf16_be(tmp_path):
    """_detect_by_bom should detect UTF-16 BE BOM."""
    from logic.encoding_helper import _detect_by_bom

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xfe\xff\x00H\x00e")
    assert _detect_by_bom(str(f)) == "utf-16-be"


def test_detect_by_bom_no_bom(tmp_path):
    """_detect_by_bom should return None for files without BOM."""
    from logic.encoding_helper import _detect_by_bom

    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello")
    assert _detect_by_bom(str(f)) is None


def test_detect_with_chardet_success(tmp_path):
    """_detect_with_chardet should return encoding when chardet succeeds."""
    from logic.encoding_helper import _detect_with_chardet

    f = tmp_path / "test.txt"
    f.write_bytes("Hello, World!".encode("utf-8"))

    mock_result = {"encoding": "utf-8", "confidence": 0.99}
    with patch.dict("sys.modules", {"chardet": MagicMock(detect=MagicMock(return_value=mock_result))}):
        result = _detect_with_chardet(str(f))
        assert result == "utf-8"


def test_detect_with_chardet_low_confidence(tmp_path):
    """_detect_with_chardet should return None when confidence is low."""
    from logic.encoding_helper import _detect_with_chardet

    f = tmp_path / "test.txt"
    f.write_bytes("Hello".encode("utf-8"))

    mock_result = {"encoding": "utf-8", "confidence": 0.3}
    with patch.dict("sys.modules", {"chardet": MagicMock(detect=MagicMock(return_value=mock_result))}):
        result = _detect_with_chardet(str(f))
        assert result is None


def test_detect_with_chardet_no_chardet(tmp_path):
    """_detect_with_chardet should return None when chardet is not installed."""
    from logic.encoding_helper import _detect_with_chardet

    f = tmp_path / "test.txt"
    f.write_bytes("Hello".encode("utf-8"))

    with patch.dict("sys.modules", {"chardet": None}):
        result = _detect_with_chardet(str(f))
        assert result is None


def test_detect_with_chardet_exception(tmp_path):
    """_detect_with_chardet should return None on exception."""
    from logic.encoding_helper import _detect_with_chardet

    f = tmp_path / "test.txt"
    f.write_bytes("Hello".encode("utf-8"))

    with patch.dict("sys.modules", {"chardet": MagicMock(detect=MagicMock(side_effect=Exception("error")))}):
        result = _detect_with_chardet(str(f))
        assert result is None


def test_detect_encoding_utf8_bom(utf8_bom_file):
    """detect_encoding should detect UTF-8 BOM."""
    from logic.encoding_helper import detect_encoding

    assert detect_encoding(str(utf8_bom_file)) == "utf-8-sig"


def test_detect_encoding_utf16_le(utf16_le_file):
    """detect_encoding should detect UTF-16 LE BOM."""
    from logic.encoding_helper import detect_encoding

    assert detect_encoding(str(utf16_le_file)) == "utf-16-le"


def test_detect_encoding_utf8(utf8_file):
    """detect_encoding should detect UTF-8."""
    from logic.encoding_helper import detect_encoding

    assert detect_encoding(str(utf8_file)) == "utf-8"


def test_detect_encoding_gbk(gbk_file):
    """detect_encoding should detect GBK."""
    from logic.encoding_helper import detect_encoding

    assert detect_encoding(str(gbk_file)) == "gbk"


def test_detect_encoding_fallback_utf8(tmp_path):
    """detect_encoding should fallback to utf-8 if all else fails."""
    from logic.encoding_helper import detect_encoding

    f = tmp_path / "test.txt"
    f.write_bytes(b"\x00\x01\x02\x03")  # Binary data

    assert detect_encoding(str(f)) == "utf-8"


def test_detect_encoding_with_chardet(tmp_path):
    """detect_encoding should use chardet if BOM not found."""
    from logic.encoding_helper import detect_encoding

    f = tmp_path / "test.txt"
    f.write_bytes("Hello".encode("utf-8"))

    mock_result = {"encoding": "ascii", "confidence": 0.9}
    with patch.dict("sys.modules", {"chardet": MagicMock(detect=MagicMock(return_value=mock_result))}):
        result = detect_encoding(str(f))
        assert result == "ascii"


def test_read_with_encoding_utf8(utf8_file):
    """read_with_encoding should read UTF-8 file."""
    from logic.encoding_helper import read_with_encoding

    content = read_with_encoding(str(utf8_file))
    assert content == "Hello, World!"


def test_read_with_encoding_gbk(gbk_file):
    """read_with_encoding should read GBK file."""
    from logic.encoding_helper import read_with_encoding

    content = read_with_encoding(str(gbk_file))
    assert "你好" in content


def test_read_with_encoding_hint_success(tmp_path):
    """read_with_encoding should try hint first."""
    from logic.encoding_helper import read_with_encoding

    f = tmp_path / "test.txt"
    f.write_text("Hello", encoding="latin-1")

    content = read_with_encoding(str(f), encoding_hint="latin-1")
    assert content == "Hello"


def test_read_with_encoding_hint_failure(tmp_path):
    """read_with_encoding should fallback if hint fails."""
    from logic.encoding_helper import read_with_encoding

    f = tmp_path / "test.txt"
    f.write_text("Hello", encoding="utf-8")

    # Hint is wrong, should fallback
    content = read_with_encoding(str(f), encoding_hint="ascii")
    assert "Hello" in content


def test_read_with_encoding_errors_replace(tmp_path):
    """read_with_encoding should use errors='replace' for final read."""
    from logic.encoding_helper import read_with_encoding

    f = tmp_path / "test.txt"
    f.write_bytes(b"Hello \xff\xfe World")

    # Should not raise, will use replacement character
    content = read_with_encoding(str(f))
    assert "Hello" in content


def test_read_with_encoding_nonexistent():
    """read_with_encoding should raise for nonexistent files."""
    from logic.encoding_helper import read_with_encoding

    with pytest.raises(FileNotFoundError):
        read_with_encoding("/nonexistent/file.txt")


def test_common_encodings_list():
    """COMMON_ENCODINGS should be a list of encoding strings."""
    from logic.encoding_helper import COMMON_ENCODINGS

    assert isinstance(COMMON_ENCODINGS, list)
    assert len(COMMON_ENCODINGS) > 0
    assert all(isinstance(e, str) for e in COMMON_ENCODINGS)


def test_detect_encoding_chardet_priority(tmp_path):
    """detect_encoding should prefer BOM over chardet."""
    from logic.encoding_helper import detect_encoding

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfHello")

    mock_result = {"encoding": "ascii", "confidence": 0.9}
    with patch.dict("sys.modules", {"chardet": MagicMock(detect=MagicMock(return_value=mock_result))}):
        result = detect_encoding(str(f))
        # BOM should take priority
        assert result == "utf-8-sig"
