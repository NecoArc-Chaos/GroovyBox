"""Tests for watch_scanner.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_trepo():
    trepo = MagicMock()
    trepo.AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav"}
    trepo.get_track_by_path.return_value = None
    trepo.import_files_async = AsyncMock(return_value=1)
    trepo.scan_directory_async = AsyncMock(return_value=5)
    return trepo


@pytest.fixture
def mock_metadata():
    meta = MagicMock()
    meta.title = "Test Song"
    meta.artist = "Test Artist"
    meta.album = "Test Album"
    meta.art_bytes = None
    return meta


def test_watch_scanner_initialization():
    """WatchScanner should initialize with empty watched paths."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    assert scanner._watched_paths == {}
    assert scanner._observer is None
    assert scanner._handler is None


def test_watch_scanner_set_loop():
    """WatchScanner.set_loop should store loop and pass to handler."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    loop = asyncio.new_event_loop()
    scanner.set_loop(loop)
    assert scanner._loop is loop
    loop.close()


def test_watch_scanner_set_loop_after_handler():
    """WatchScanner.set_loop should update handler loop if handler exists."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    scanner._handler = MagicMock()
    loop = asyncio.new_event_loop()
    scanner.set_loop(loop)
    scanner._handler.set_loop.assert_called_once_with(loop)
    loop.close()


def test_watch_scanner_start_no_watchdog():
    """WatchScanner.start should warn if watchdog is not installed."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", False):
        scanner = WatchScanner()
        scanner.start()
        # Should not raise, just log warning


def test_watch_scanner_start_already_running():
    """WatchScanner.start should not start if observer is already alive."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        mock_observer.is_alive.return_value = True
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner.start()
        scanner.start()  # Second call should be no-op

        mock_observer.start.assert_called_once()


def test_watch_scanner_start_with_paths(mock_trepo):
    """WatchScanner.start should schedule watches for all paths."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner._watched_paths = {"/music": {"1"}, "/other": {"2"}}
        scanner.start()

        assert mock_observer.schedule.call_count == 2
        mock_observer.start.assert_called_once()


def test_watch_scanner_stop():
    """WatchScanner.stop should stop and join observer."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner.start()
        scanner.stop()

        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once_with(timeout=2)
        assert scanner._observer is None


def test_watch_scanner_stop_no_observer():
    """WatchScanner.stop should handle missing observer gracefully."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    scanner.stop()  # Should not raise


def test_watch_scanner_add_watch(mock_trepo):
    """WatchScanner.add_watch should add path and schedule if running."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner.start()
        scanner.add_watch("/new_music", 3)

        assert "/new_music" in scanner._watched_paths
        assert scanner._watched_paths["/new_music"] == {"3"}
        mock_observer.schedule.assert_called()


def test_watch_scanner_remove_watch(mock_trepo):
    """WatchScanner.remove_watch should remove path and restart observer."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner._watched_paths = {"/music": {"1"}}
        scanner.start()
        scanner.remove_watch("/music")

        assert "/music" not in scanner._watched_paths
        # Should restart observer
        mock_observer.stop.assert_called()


def test_watch_scanner_refresh(mock_trepo):
    """WatchScanner.refresh should restart observer."""
    from logic.watch_scanner import WatchScanner

    with patch("logic.watch_scanner._HAS_WATCHDOG", True), \
         patch("logic.watch_scanner.Observer") as MockObserver:
        mock_observer = MagicMock()
        MockObserver.return_value = mock_observer

        scanner = WatchScanner()
        scanner.start()
        scanner.refresh()

        # stop and start should have been called again
        assert mock_observer.stop.call_count >= 1


def test_watch_scanner_scan_all(mock_trepo):
    """WatchScanner.scan_all should scan all watched folders."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    scanner._watched_paths = {"/music": {"1"}, "/other": {"2"}}

    with patch("logic.watch_scanner.trepo", mock_trepo):
        result = asyncio.run(scanner.scan_all())

    assert result == 10  # 5 + 5
    assert mock_trepo.scan_directory_async.call_count == 2


def test_on_file_added_existing_file(mock_trepo):
    """_on_file_added should import existing audio file."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()

    with patch("logic.watch_scanner.trepo", mock_trepo), \
         patch("os.path.isfile", return_value=True):
        asyncio.run(scanner._on_file_added("/music/song.mp3"))

    mock_trepo.import_files_async.assert_called_once_with(["/music/song.mp3"], copy=False)


def test_on_file_added_missing_file(mock_trepo):
    """_on_file_added should skip if file doesn't exist."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()

    with patch("logic.watch_scanner.trepo", mock_trepo), \
         patch("os.path.isfile", return_value=False):
        asyncio.run(scanner._on_file_added("/music/song.mp3"))

    mock_trepo.import_files_async.assert_not_called()


def test_on_file_added_non_audio(mock_trepo):
    """_on_file_added should skip non-audio files."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()

    with patch("logic.watch_scanner.trepo", mock_trepo):
        asyncio.run(scanner._on_file_added("/music/readme.txt"))

    mock_trepo.import_files_async.assert_not_called()


def test_on_file_modified_existing_track(mock_trepo, mock_metadata):
    """_on_file_modified should update metadata for existing track."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    mock_trepo.get_track_by_path.return_value = MagicMock(id=1)
    mock_trepo.get_app_dir.return_value = "/tmp/groovybox"

    with patch("logic.watch_scanner.trepo", mock_trepo), \
         patch("logic.watch_scanner.get_metadata", return_value=mock_metadata), \
         patch("os.path.isfile", return_value=True), \
         patch("os.makedirs"), \
         patch("builtins.open", MagicMock()):
        asyncio.run(scanner._on_file_modified("/music/song.mp3"))

    mock_trepo.update_metadata.assert_called_once()
    mock_trepo.update_art_uri.assert_not_called()  # No art_bytes


def test_on_file_modified_with_art(mock_trepo, mock_metadata):
    """_on_file_modified should save art if metadata has art_bytes."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    mock_trepo.get_track_by_path.return_value = MagicMock(id=1)
    mock_trepo.get_app_dir.return_value = "/tmp/groovybox"
    mock_metadata.art_bytes = b"fake_image_data"

    with patch("logic.watch_scanner.trepo", mock_trepo), \
         patch("logic.watch_scanner.get_metadata", return_value=mock_metadata), \
         patch("os.path.isfile", return_value=True), \
         patch("os.makedirs"), \
         patch("builtins.open", MagicMock()):
        asyncio.run(scanner._on_file_modified("/music/song.mp3"))

    mock_trepo.update_metadata.assert_called_once()
    mock_trepo.update_art_uri.assert_called_once()


def test_on_file_modified_missing_file(mock_trepo):
    """_on_file_modified should skip if file doesn't exist."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()

    with patch("logic.watch_scanner.trepo", mock_trepo), \
         patch("os.path.isfile", return_value=False):
        asyncio.run(scanner._on_file_modified("/music/song.mp3"))

    mock_trepo.get_track_by_path.assert_not_called()


def test_on_file_deleted_existing_track(mock_trepo):
    """_on_file_deleted should remove track from database."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    mock_trepo.get_track_by_path.return_value = MagicMock(id=1)

    with patch("logic.watch_scanner.trepo", mock_trepo):
        asyncio.run(scanner._on_file_deleted("/music/song.mp3"))

    mock_trepo.delete_track.assert_called_once_with(1)


def test_on_file_deleted_missing_track(mock_trepo):
    """_on_file_deleted should do nothing if track not in database."""
    from logic.watch_scanner import WatchScanner

    scanner = WatchScanner()
    mock_trepo.get_track_by_path.return_value = None

    with patch("logic.watch_scanner.trepo", mock_trepo):
        asyncio.run(scanner._on_file_deleted("/music/song.mp3"))

    mock_trepo.delete_track.assert_not_called()


def test_track_change_handler_on_created_audio():
    """_TrackChangeHandler should schedule import for audio files."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)
    handler.set_loop(asyncio.new_event_loop())

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/music/song.mp3"

    with patch.object(handler, "_schedule") as mock_schedule:
        handler.on_created(event)
        mock_schedule.assert_called_once()


def test_track_change_handler_on_created_directory():
    """_TrackChangeHandler should ignore directory creation."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)

    event = MagicMock()
    event.is_directory = True
    event.src_path = "/music/folder"

    with patch.object(handler, "_schedule") as mock_schedule:
        handler.on_created(event)
        mock_schedule.assert_not_called()


def test_track_change_handler_on_modified_non_audio():
    """_TrackChangeHandler should ignore non-audio file modifications."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/music/readme.txt"

    with patch.object(handler, "_schedule") as mock_schedule:
        handler.on_modified(event)
        mock_schedule.assert_not_called()


def test_track_change_handler_on_deleted_audio():
    """_TrackChangeHandler should schedule deletion for audio files."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/music/song.mp3"

    with patch.object(handler, "_schedule") as mock_schedule:
        handler.on_deleted(event)
        mock_schedule.assert_called_once()


def test_track_change_handler_on_moved_audio():
    """_TrackChangeHandler should schedule add and delete for moved audio files."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/music/song.mp3"
    event.dest_path = "/new/song.mp3"

    with patch.object(handler, "_schedule") as mock_schedule:
        handler.on_moved(event)
        assert mock_schedule.call_count == 2


def test_track_change_handler_schedule_no_loop():
    """_TrackChangeHandler._schedule should do nothing if loop is None."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)
    handler._loop = None

    # Should not raise
    handler._schedule(MagicMock())


def test_track_change_handler_schedule_loop_not_running():
    """_TrackChangeHandler._schedule should do nothing if loop is not running."""
    from logic.watch_scanner import WatchScanner, _TrackChangeHandler

    scanner = WatchScanner()
    handler = _TrackChangeHandler(scanner)
    handler._loop = MagicMock()
    handler._loop.is_running.return_value = False

    # Should not raise
    handler._schedule(MagicMock())
