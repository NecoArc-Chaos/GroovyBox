"""Playlist Parser for GroovyBox.

This module handles parsing of playlist files (M3U and PLS formats)
to extract audio file paths. Supports multiple text encodings and
resolves relative paths against the playlist file's directory.
"""

import os
import re


def parse_m3u(path: str) -> list[str]:
    """Parse an M3U/M3U8 playlist file and return audio file paths.

    Reads the playlist file, skips comments (lines starting with #),
    and resolves relative paths against the playlist's directory.

    Args:
        path: Absolute path to the M3U file.

    Returns:
        List of absolute paths to audio files that exist on disk.
    """
    if not os.path.isfile(path):
        return []
    # Try multiple encodings to read the file
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin-1"]:
        try:
            with open(path, encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        lines = []

    result = []
    base_dir = os.path.dirname(path)
    for line in lines:
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Resolve relative paths
        if not os.path.isabs(line):
            candidate = os.path.normpath(os.path.join(base_dir, line))
        else:
            candidate = line
        if os.path.isfile(candidate):
            result.append(candidate)
    return result


def parse_pls(path: str) -> list[str]:
    """Parse a PLS playlist file and return audio file paths.

    Reads the playlist file using format: FileN=path/to/audio.mp3

    Args:
        path: Absolute path to the PLS file.

    Returns:
        List of absolute paths to audio files that exist on disk.
    """
    if not os.path.isfile(path):
        return []
    # Try multiple encodings
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin-1"]:
        try:
            with open(path, encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        return []

    result = []
    base_dir = os.path.dirname(path)
    # Extract FileN= entries using regex
    for match in re.finditer(r"^File\d+=(.+)$", content, re.MULTILINE):
        file_path = match.group(1).strip()
        if not os.path.isabs(file_path):
            candidate = os.path.normpath(os.path.join(base_dir, file_path))
        else:
            candidate = file_path
        if os.path.isfile(candidate):
            result.append(candidate)
    return result


def parse_playlist(path: str) -> list[str]:
    """Parse a playlist file and return audio file paths.

    Automatically detects the format based on file extension:
    - .pls: PLS format
    - .m3u/.m3u8 or other: M3U format

    Args:
        path: Absolute path to the playlist file.

    Returns:
        List of absolute paths to audio files that exist on disk.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pls":
        return parse_pls(path)
    else:
        return parse_m3u(path)
