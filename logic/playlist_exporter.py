"""Playlist Exporter for GroovyBox.

This module handles exporting playlists to M3U format files,
with optional ZIP packaging that includes audio files, lyrics,
and album art. Supports both relative and absolute path references.
"""

import os
import shutil
import tempfile
import zipfile

from data import playlist_repository as prepo
from data.models import Playlist, Track


def export_playlist(
    playlist_id: int,
    output_path: str,
    use_relpath: bool = False,
    include_lyrics: bool = False,
    include_covers: bool = False,
    as_zip: bool = False,
) -> str:
    """Export a playlist to an M3U file or ZIP archive.

    Args:
        playlist_id: Database ID of the playlist to export.
        output_path: Destination file path.
        use_relpath: Whether to use relative paths in the M3U file.
        include_lyrics: Whether to export lyrics files alongside the M3U.
        include_covers: Whether to export album art files.
        as_zip: Whether to package everything into a ZIP archive.

    Returns:
        The output file path.

    Raises:
        ValueError: If the playlist ID doesn't exist.
    """
    # Find the playlist
    playlist = None
    for p in prepo.watch_all_playlists():
        if p.id == playlist_id:
            playlist = p
            break
    if not playlist:
        raise ValueError(f"Playlist {playlist_id} not found")

    tracks = prepo.watch_playlist_tracks(playlist_id)
    out_dir = os.path.dirname(output_path) or "."
    base_name = os.path.splitext(os.path.basename(output_path))[0]

    if as_zip:
        return _export_as_zip(
            playlist, tracks, output_path, out_dir, base_name, use_relpath, include_lyrics, include_covers
        )
    else:
        return _export_m3u(playlist, tracks, output_path, out_dir, use_relpath, include_lyrics, include_covers)


def _export_m3u(
    playlist: Playlist,
    tracks: list[Track],
    output_path: str,
    out_dir: str,
    use_relpath: bool,
    include_lyrics: bool,
    include_covers: bool,
) -> str:
    """Export tracks as an M3U playlist file.

    Creates a standard M3U file with #EXTINF metadata lines.
    Optionally copies lyrics and cover art files to the output directory.

    Args:
        playlist: The playlist object.
        tracks: List of tracks in the playlist.
        output_path: Path for the output M3U file.
        out_dir: Base directory for relative path calculation.
        use_relpath: Whether to use relative paths.
        include_lyrics: Whether to export lyrics files.
        include_covers: Whether to export cover art files.

    Returns:
        The output file path.
    """
    lines = ["#EXTM3U"]
    for t in tracks:
        if not t.path or not os.path.isfile(t.path):
            continue
        duration_sec = (t.duration or 0) // 1000
        lines.append(f"#EXTINF:{duration_sec},{t.artist or 'Unknown'} - {t.title}")
        ref = _make_path(t.path, out_dir, use_relpath)
        lines.append(ref)

        # Export lyrics file if requested
        if include_lyrics and t.lyrics:
            safe_title = os.path.basename(t.title or "lyrics")
            lyrics_path = os.path.join(out_dir, f"{safe_title}.lrc")
            _write_lyrics_file(lyrics_path, t.lyrics)

        # Export cover art if requested
        if include_covers and t.art_uri and os.path.isfile(t.art_uri):
            safe_title = os.path.basename(t.title or "cover")
            ext = os.path.splitext(t.art_uri)[1] or ".jpg"
            cover_dst = os.path.join(out_dir, f"{safe_title}{ext}")
            shutil.copy2(t.art_uri, cover_dst)

    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return output_path


def _export_as_zip(
    playlist: Playlist,
    tracks: list[Track],
    output_path: str,
    out_dir: str,
    base_name: str,
    use_relpath: bool,
    include_lyrics: bool,
    include_covers: bool,
) -> str:
    """Export playlist as a ZIP archive containing M3U and audio files.

    Creates a temporary directory, generates the M3U file, copies all
    audio files, then compresses everything into a ZIP archive.

    Args:
        playlist: The playlist object.
        tracks: List of tracks in the playlist.
        output_path: Path for the output ZIP file.
        out_dir: Base directory.
        base_name: Base filename without extension.
        use_relpath: Whether to use relative paths in M3U.
        include_lyrics: Whether to include lyrics files.
        include_covers: Whether to include cover art.

    Returns:
        The output ZIP file path.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        inner_dir = os.path.join(tmpdir, base_name)
        os.makedirs(inner_dir, exist_ok=True)

        # Generate M3U inside the temp directory
        m3u_path = os.path.join(inner_dir, f"{base_name}.m3u")
        _export_m3u(
            playlist,
            tracks,
            m3u_path,
            inner_dir,
            use_relpath=False,
            include_lyrics=include_lyrics,
            include_covers=include_covers,
        )

        # Copy audio files to the temp directory
        for t in tracks:
            if not t.path or not os.path.isfile(t.path):
                continue
            dst = os.path.join(inner_dir, os.path.basename(t.path))
            if not os.path.exists(dst):
                try:
                    shutil.copy2(t.path, dst)
                except Exception:
                    pass

        # Create ZIP archive
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmpdir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    arcname = os.path.relpath(fp, tmpdir)
                    zf.write(fp, arcname)
    return output_path


def _make_path(file_path: str, base_dir: str, use_relpath: bool) -> str:
    """Convert a file path to either absolute or relative form.

    Args:
        file_path: The original file path.
        base_dir: Base directory for relative path calculation.
        use_relpath: Whether to return a relative path.

    Returns:
        The converted path string.
    """
    if use_relpath:
        try:
            return os.path.relpath(file_path, base_dir)
        except ValueError:
            return file_path
    return os.path.abspath(file_path)


def _write_lyrics_file(path: str, lyrics_json: str):
    """Write lyrics data to an LRC file.

    Converts JSON lyrics back to LRC format for timed lyrics,
    or plain text for unsynchronized lyrics.

    Args:
        path: Output file path.
        lyrics_json: JSON string containing lyrics data.
    """
    try:
        from logic.lyrics_parser import lyrics_from_json

        data = lyrics_from_json(lyrics_json)
        if data and data.lines:
            if data.type == "timed":
                # Convert to LRC format
                lines_out = []
                for ln in data.lines:
                    if ln.time_ms is not None:
                        mins = (ln.time_ms // 60000) % 100
                        secs = (ln.time_ms // 1000) % 60
                        cs = (ln.time_ms % 1000) // 10
                        lines_out.append(f"[{mins:02d}:{secs:02d}.{cs:02d}]{ln.text}")
                    else:
                        lines_out.append(ln.text or "")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines_out))
            else:
                # Write as plain text
                with open(path, "w", encoding="utf-8") as f:
                    for ln in data.lines:
                        f.write((ln.text or "") + "\n")
    except Exception:
        pass
