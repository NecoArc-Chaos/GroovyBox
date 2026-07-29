"""Metadata Service for GroovyBox.

This module handles extraction of audio file metadata including
title, artist, album, duration, and embedded album art. Uses the
mutagen library for cross-format metadata support.
"""

import os
from typing import Optional
from mutagen import File as MutagenFile
from data.models import TrackMetadata
from logic.logger import logger

# Supported audio file extensions for metadata extraction
SUPPORTED_EXTENSIONS = {
    '.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.opus', '.aiff',
}


def get_metadata(file_path: str) -> TrackMetadata:
    """Extract metadata from an audio file.

    Reads title, artist, album, duration, and embedded album art
    from the audio file using mutagen. Returns empty metadata if
    the file cannot be read.

    Args:
        file_path: Absolute path to the audio file.

    Returns:
        A TrackMetadata instance with extracted information.
    """
    meta = TrackMetadata()
    if not os.path.isfile(file_path):
        return meta

    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return meta

        # Extract basic tags
        meta.title = _safe_tag(audio, "title")
        meta.artist = _safe_tag(audio, "artist")
        meta.album = _safe_tag(audio, "album")

        # Duration: convert seconds to milliseconds
        if hasattr(audio.info, "length") and audio.info.length:
            meta.duration = int(audio.info.length * 1000)

        # Extract embedded album art
        meta.art_bytes = _extract_art(audio)

    except Exception as ex:
        logger.warning(f"Failed to extract metadata from {file_path}: {ex}")

    return meta


def _safe_tag(audio, key: str) -> Optional[str]:
    """Safely extract a tag value from an audio file.

    Handles various tag formats (single value, list) and
    returns None if the tag doesn't exist or can't be read.

    Args:
        audio: The mutagen audio file object.
        key: The tag key to extract (e.g., "title", "artist").

    Returns:
        The tag value as a string, or None if not found.
    """
    try:
        if key in audio:
            val = audio[key]
            if isinstance(val, list) and len(val) > 0:
                return str(val[0])
            return str(val)
    except Exception as ex:
        logger.debug(f"Failed to read tag {key}: {ex}")
    return None


def _extract_art(audio) -> Optional[bytes]:
    """Extract embedded album art from an audio file.

    Supports multiple formats:
    - MP3/ID3: Checks for data or picture attributes
    - FLAC: Checks the pictures list
    - MP4: Checks for 'covr' tag

    Args:
        audio: The mutagen audio file object.

    Returns:
        Raw image bytes if found, None otherwise.
    """
    try:
        # MP3 / ID3 tags
        if hasattr(audio, "tags") and audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, "data"):
                    return tag.data
                if hasattr(tag, "picture"):
                    return tag.picture.data

        # FLAC pictures
        if hasattr(audio, "pictures") and audio.pictures:
            return audio.pictures[0].data

        # MP4 covr tag
        if hasattr(audio, "tags") and "covr" in audio.tags:
            covr = audio.tags["covr"]
            if covr and len(covr) > 0:
                return covr[0]

    except Exception as ex:
        logger.debug(f"Failed to extract album art: {ex}")
    return None


def format_duration(duration_ms: Optional[int]) -> str:
    """Format a duration in milliseconds to a human-readable string.

    Args:
        duration_ms: Duration in milliseconds, or None.

    Returns:
        Formatted string like "3:45" or "--:--" if duration is None.
    """
    if duration_ms is None:
        return "--:--"
    total_sec = duration_ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    return f"{minutes}:{seconds:02d}"
