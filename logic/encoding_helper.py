"""Encoding Helper Module for GroovyBox.

This module provides utilities for detecting and reading text files
with various character encodings. Essential for importing lyrics files
that may use different encodings (UTF-8, GBK, Shift-JIS, etc.).
"""

import os

# Common encodings to try during detection, ordered by likelihood
COMMON_ENCODINGS = ["utf-8", "gbk", "shift-jis", "euc-kr", "latin-1", "big5", "euc-jp", "utf-16"]


def _detect_with_chardet(path):
    """Detect file encoding using the chardet library.

    Reads up to 8KB of the file for analysis. Only returns a result
    if confidence exceeds 50%.

    Args:
        path: Path to the text file.

    Returns:
        Detected encoding name, or None if detection fails.
    """
    try:
        import chardet
        with open(path, "rb") as f:
            raw = f.read(min(8192, os.path.getsize(path)))
        result = chardet.detect(raw)
        if result and result["encoding"] and result["confidence"] > 0.5:
            return result["encoding"]
    except ImportError:
        pass
    except Exception:
        pass
    return None


def _detect_by_bom(path):
    """Detect file encoding by Byte Order Mark (BOM).

    Checks the first few bytes of the file for UTF-8, UTF-16 LE,
    or UTF-16 BE BOM signatures.

    Args:
        path: Path to the text file.

    Returns:
        Encoding name based on BOM, or None if no BOM found.
    """
    with open(path, "rb") as f:
        raw = f.read(4)
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw[:2] == b"\xff\xfe":
        return "utf-16-le"
    if raw[:2] == b"\xfe\xff":
        return "utf-16-be"
    return None


def detect_encoding(path):
    """Detect the encoding of a text file.

    Uses a multi-strategy approach:
    1. Check for BOM (Byte Order Mark)
    2. Try chardet library for statistical detection
    3. Try common encodings sequentially

    Args:
        path: Path to the text file.

    Returns:
        Detected encoding name, defaults to "utf-8" if all else fails.
    """
    # Strategy 1: BOM detection
    bom = _detect_by_bom(path)
    if bom:
        return bom

    # Strategy 2: chardet statistical detection
    chardet_enc = _detect_with_chardet(path)
    if chardet_enc:
        return chardet_enc

    # Strategy 3: Try common encodings
    for enc in COMMON_ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                f.read()
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    return "utf-8"


def read_with_encoding(path, encoding_hint=None):
    """Read a text file with automatic encoding detection.

    Tries the provided hint first, then falls back to auto-detection.
    Uses error replacement to handle any remaining encoding issues.

    Args:
        path: Path to the text file.
        encoding_hint: Optional encoding to try first.

    Returns:
        File content as a string.
    """
    if encoding_hint:
        try:
            with open(path, "r", encoding=encoding_hint) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            pass
    enc = detect_encoding(path)
    with open(path, "r", encoding=enc, errors="replace") as f:
        return f.read()
