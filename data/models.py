"""Data Models for GroovyBox.

This module defines all data classes used throughout the application.
These models represent tracks, playlists, albums, artists, settings,
and various intermediate data structures for lyrics and metadata.
"""

from dataclasses import dataclass, field


@dataclass
class Track:
    """Represents a music track stored in the database.

    Attributes:
        id: Unique database identifier.
        title: Track title (defaults to filename if not available).
        artist: Artist name (optional).
        album: Album name (optional).
        duration: Track duration in milliseconds (optional).
        path: Absolute file path to the audio file.
        art_uri: Path to the album art image file (optional).
        art_thumb: Raw bytes of album art thumbnail (optional).
        lyrics: JSON string containing lyrics data (optional).
        lyrics_offset: Milliseconds offset for lyrics synchronization.
        added_at: Timestamp when the track was added to the library.
        last_checked: ISO timestamp of last missing-file check (optional).
    """

    id: int = 0
    title: str = ""
    artist: str | None = None
    album: str | None = None
    duration: int | None = None
    path: str = ""
    art_uri: str | None = None
    art_thumb: bytes | None = None
    lyrics: str | None = None
    lyrics_offset: int = 0
    added_at: str = ""
    last_checked: str | None = None


@dataclass
class Playlist:
    """Represents a user-created playlist.

    Attributes:
        id: Unique database identifier.
        name: Display name of the playlist.
        created_at: Timestamp when the playlist was created.
    """

    id: int = 0
    name: str = ""
    created_at: str = ""


@dataclass
class AlbumData:
    """Represents an album grouping for display in the UI.

    Attributes:
        album: Album name.
        artist: Primary artist name.
        art_uri: Path to the album cover image (optional).
    """

    album: str = ""
    artist: str = ""
    art_uri: str | None = None


@dataclass
class ArtistAlbums:
    """Represents an artist with their associated albums.

    Attributes:
        artist: Artist display name.
        albums: List of AlbumData objects belonging to this artist.
        track_count: Total number of tracks by this artist with albums.
    """

    artist: str = ""
    albums: list = field(default_factory=list)
    track_count: int = 0


@dataclass
class WatchFolder:
    """Represents a monitored music library folder.

    Attributes:
        id: Unique database identifier.
        path: Absolute path to the folder.
        name: Display name for the folder.
        is_active: Whether this folder is currently being monitored.
        recursive: Whether to scan subfolders recursively.
        added_at: Timestamp when the folder was added.
        last_scanned: Timestamp of the last scan operation.
    """

    id: int = 0
    path: str = ""
    name: str = ""
    is_active: bool = True
    recursive: bool = True
    added_at: str = ""
    last_scanned: str | None = None


@dataclass
class SettingsState:
    """Represents application settings snapshot.

    Attributes:
        auto_scan: Whether to automatically scan watch folders on startup.
        default_player_screen: Default view mode for the player (cover/lyrics/queue).
        lyrics_mode: Lyrics display mode (auto/curved/flat).
        continue_plays: Whether to continue playing when the queue ends.
    """

    auto_scan: bool = True
    default_player_screen: str = "cover"
    lyrics_mode: str = "auto"
    continue_plays: bool = False


@dataclass
class CurrentTrackData:
    """Represents the currently playing track's runtime data.

    This is a lightweight version of Track used for passing current
    playback information between the audio handler and UI components.

    Attributes:
        id: Database ID of the track.
        title: Track title.
        artist: Artist name (optional).
        album: Album name (optional).
        path: File path to the audio file.
        art_uri: Path to album art (optional).
        lyrics: JSON lyrics data (optional).
        lyrics_offset: Lyrics sync offset in milliseconds.
    """

    id: int = 0
    title: str = ""
    artist: str | None = None
    album: str | None = None
    path: str = ""
    art_uri: str | None = None
    lyrics: str | None = None
    lyrics_offset: int = 0


@dataclass
class TrackMetadata:
    """Represents metadata extracted from an audio file.

    Attributes:
        title: Track title from metadata tags.
        artist: Artist name from metadata tags.
        album: Album name from metadata tags.
        duration: Track duration in milliseconds.
        art_bytes: Raw bytes of the embedded album art image.
    """

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    duration: int | None = None
    art_bytes: bytes | None = None


@dataclass
class LyricsLine:
    """Represents a single line of lyrics.

    Attributes:
        time_ms: Timestamp in milliseconds (None for unsynchronized lyrics).
        text: The lyrics text content.
    """

    time_ms: int | None = None
    text: str = ""


@dataclass
class LyricsData:
    """Represents a complete lyrics document.

    Attributes:
        type: Lyrics format type - "timed" for synchronized, "plain" for static.
        lines: List of LyricsLine objects containing the lyrics content.
    """

    type: str = "plain"
    lines: list = field(default_factory=list)
