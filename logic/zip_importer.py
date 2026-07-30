"""ZIP Importer for GroovyBox.

This module handles extraction of ZIP archives containing music files,
lyrics, and playlist files. Used for importing bundled music collections.
"""

import os
import tempfile
import zipfile

from data.track_repository import AUDIO_EXTENSIONS, LYRICS_EXTENSIONS

# Supported playlist file extensions within ZIP archives
PLAYLIST_EXTENSIONS = {"m3u", "m3u8", "pls"}


def extract_zip(zip_path: str, dest_dir: str = None) -> tuple[list[str], list[str], list[str]]:
    """Extract a ZIP archive and categorize the contained files.

    Extracts all files from the ZIP archive and categorizes them into
    audio files, lyrics files, and playlist files based on their extensions.

    Args:
        zip_path: Absolute path to the ZIP file.
        dest_dir: Destination directory for extraction. If None, a temporary
                  directory is created with the prefix "groovybox_zip_".

    Returns:
        A tuple of three lists:
        - audio_files: Paths to extracted audio files
        - lyrics_files: Paths to extracted lyrics files
        - playlist_files: Paths to extracted playlist files
    """
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="groovybox_zip_")

    audio_files = []
    lyrics_files = []
    playlist_files = []

    real_dest = os.path.realpath(dest_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # Skip directory entries
            if info.is_dir():
                continue

            fn = info.filename
            ext = os.path.splitext(fn)[1].lower().lstrip(".")

            # Prevent path traversal (Zip Slip)
            target_path = os.path.realpath(os.path.join(dest_dir, fn))
            if not target_path.startswith(real_dest + os.sep) and target_path != real_dest:
                continue

            # Create subdirectories as needed
            out_path = os.path.join(dest_dir, fn)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            try:
                zf.extract(info, dest_dir)
            except Exception:
                continue

            # Categorize by file extension
            if ext in AUDIO_EXTENSIONS:
                audio_files.append(out_path)
            elif ext in LYRICS_EXTENSIONS:
                lyrics_files.append(out_path)
            elif ext in PLAYLIST_EXTENSIONS:
                playlist_files.append(out_path)

    return audio_files, lyrics_files, playlist_files
