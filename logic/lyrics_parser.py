"""Lyrics Parser for GroovyBox.

This module handles parsing, serialization, and deserialization of lyrics
in multiple formats:
- LRC: Synchronized lyrics with timestamps (e.g., [01:23.45] lyrics text)
- SRT: Subtitle format with time ranges
- Plaintext: Unsynchronized plain text lyrics

Supports automatic format detection and JSON serialization for database storage.
"""

import re
import json
from data.models import LyricsLine, LyricsData


def parse_lrc(content: str) -> LyricsData:
    """Parse LRC format synchronized lyrics.

    Expected format: [MM:SS.xx] lyrics text

    Args:
        content: Raw LRC file content string.

    Returns:
        LyricsData with type="timed" and parsed lines.
    """
    lines = []
    regex = re.compile(r'\[(\d+):(\d+)\.?(\d+)?\](.*)')
    for line in content.split('\n'):
        m = regex.match(line.strip())
        if m:
            minutes = int(m.group(1))
            seconds = int(m.group(2))
            centiseconds = int(m.group(3) or '0')
            text = m.group(4).strip()
            # Convert to milliseconds
            time_ms = minutes * 60 * 1000 + seconds * 1000 + centiseconds * 10
            if text:
                lines.append(LyricsLine(time_ms=time_ms, text=text))
    lines.sort(key=lambda x: x.time_ms or 0)
    return LyricsData(type="timed", lines=lines)


def parse_srt(content: str) -> LyricsData:
    """Parse SRT format subtitle/lyrics.

    Expected format:
        1
        00:00:20,000 --> 00:00:24,400
        Lyrics text line 1
        Lyrics text line 2

    Args:
        content: Raw SRT file content string.

    Returns:
        LyricsData with type="timed" and parsed lines.
    """
    lines = []
    blocks = re.split(r'\n\s*\n', content)
    time_regex = re.compile(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*\d+:\d+:\d+[,.]?\d*')
    for block in blocks:
        block_lines = block.strip().split('\n')
        for i, bl in enumerate(block_lines):
            m = time_regex.match(bl)
            if m:
                hours = int(m.group(1))
                minutes = int(m.group(2))
                seconds = int(m.group(3))
                millis = int(m.group(4).ljust(3, '0'))
                time_ms = hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + millis
                text = ' '.join(block_lines[i + 1:]).strip()
                if text:
                    lines.append(LyricsLine(time_ms=time_ms, text=text))
                break
    lines.sort(key=lambda x: x.time_ms or 0)
    return LyricsData(type="timed", lines=lines)


def parse_plaintext(content: str) -> LyricsData:
    """Parse plain text lyrics (unsynchronized).

    Each non-empty line becomes a lyrics line without timestamps.

    Args:
        content: Raw text content string.

    Returns:
        LyricsData with type="plain" and parsed lines.
    """
    lines = [
        LyricsLine(text=line.strip())
        for line in content.split('\n')
        if line.strip()
    ]
    return LyricsData(type="plain", lines=lines)


def parse(content: str, filename: str) -> LyricsData:
    """Parse lyrics content with automatic format detection.

    Uses the file extension to determine format, falling back to
    content-based detection if the extension is unrecognized.

    Args:
        content: Raw lyrics file content.
        filename: Original filename (used for extension detection).

    Returns:
        LyricsData with parsed lines and detected type.
    """
    lower = filename.lower()
    if lower.endswith('.lrc'):
        return parse_lrc(content)
    elif lower.endswith('.srt'):
        return parse_srt(content)
    else:
        # Content-based format detection
        if re.search(r'\[\d+:\d+', content):
            return parse_lrc(content)
        if re.search(r'\d+:\d+:\d+[,.]', content):
            return parse_srt(content)
        return parse_plaintext(content)


def lyrics_to_json(data: LyricsData) -> str:
    """Serialize LyricsData to a JSON string for database storage.

    Args:
        data: The LyricsData instance to serialize.

    Returns:
        JSON string representation of the lyrics.
    """
    return json.dumps({
        "type": data.type,
        "lines": [{"time": line.time_ms, "text": line.text} for line in data.lines],
    }, ensure_ascii=False)


def lyrics_from_json(s: str) -> LyricsData:
    """Deserialize LyricsData from a JSON string.

    Args:
        s: JSON string from the database.

    Returns:
        LyricsData instance reconstructed from the JSON.
    """
    d = json.loads(s)
    return LyricsData(
        type=d.get("type", "plain"),
        lines=[LyricsLine(time_ms=item.get("time"), text=item["text"]) for item in d.get("lines", [])],
    )
