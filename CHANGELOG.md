# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Background watch folder scanner using `watchdog` for automatic library sync
- Album art thumbnail caching (`art_thumb` BLOB) for faster list rendering
- Incremental missing-track checks using `last_checked` timestamps
- Thread-local SQLite connection reuse to reduce connect/close overhead
- `build-config-reference.md` documentation for build configuration

### Changed

- ZIP imports now copy files to internal storage on all platforms, enabling safe temp directory cleanup
- Missing-track detection runs in an executor to avoid blocking the UI on startup
- Audio player prefers cached `track.duration` over re-reading via mutagen
- Settings screen strings fully internationalized (no hardcoded English)

### Fixed

- Zip Slip path traversal vulnerability in `logic/zip_importer.py`
- Path traversal in playlist export (`logic/playlist_exporter.py`)
- Missing `chardet` and `pystray` declarations in `requirements.txt`
- Type annotation for `_do_import()` return value in `data/track_repository.py`

### Security

- Added path validation before `ZipFile.extract()` to prevent directory traversal
- Sanitized exported filenames with `os.path.basename()` to prevent write-outside-target-directory

## [1.0.0] - 2026-07-26

### Added

- Initial public release with core music player functionality
- Local music playback with flet-audio backend
- Music library management with watch folders
- Artist / album / playlist browsing
- Playlist creation, reordering, and export (M3U / ZIP)
- LRC / SRT / plain-text lyrics support with sync and offset adjustment
- Material 3 UI with light / dark / system theme modes
- Adaptive background blur from album art
- Chinese / English localization
- System tray integration (desktop)
- Customizable keyboard shortcuts
- Cross-platform builds (Windows, macOS, Linux, Android, iOS)

[unreleased]: https://github.com/NecoArc-Chaos/GroovyBox/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/NecoArc-Chaos/GroovyBox/releases/tag/v1.0.0
