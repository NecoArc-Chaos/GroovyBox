"""File Dialog Module for GroovyBox.

This module provides wrapper functions for Flet's FilePicker,
offering a simplified API for common file operations: picking files,
selecting directories, and saving files. Handles platform-specific
error cases gracefully.

Note: FilePicker is a Service (not a visual Control) in Flet 0.85+.
Service.init() auto-registers with page._services, so it must NOT
be added to page.overlay.
"""

import logging

from flet import FilePicker, FilePickerFileType

logger = logging.getLogger("flet")


def _get_picker(page) -> FilePicker:
    """Return the pre-created FilePicker instance, creating one as fallback."""
    picker = getattr(page, "_file_picker", None)
    if picker is None:
        picker = FilePicker()
        page._file_picker = picker
        page.update()
    return picker


async def pick_files(
    page,
    title: str = "Select files",
    extensions: list[str] | None = None,
    allow_multiple: bool = True,
) -> list[str] | None:
    """Open a file picker dialog for selecting files.

    Args:
        page: The Flet page instance.
        title: Dialog window title.
        extensions: List of allowed file extensions (e.g., ["mp3", "flac"]).
        allow_multiple: Whether multiple files can be selected.

    Returns:
        List of selected file paths, or None if cancelled.
    """
    try:
        picker = _get_picker(page)
        file_type = FilePickerFileType.CUSTOM if extensions else FilePickerFileType.ANY
        result = await picker.pick_files(
            dialog_title=title,
            allowed_extensions=extensions,
            allow_multiple=allow_multiple,
            file_type=file_type,
        )
        return [f.path for f in result if f.path] if result else None
    except Exception as e:
        logger.error("FilePicker.pick_files failed: %s", e)
        return None


async def pick_directory(
    page,
    title: str = "Select folder",
) -> str | None:
    """Open a directory picker dialog.

    Args:
        page: The Flet page instance.
        title: Dialog window title.

    Returns:
        Selected directory path, or None if cancelled.
    """
    try:
        picker = _get_picker(page)
        return await picker.get_directory_path(dialog_title=title)
    except Exception as e:
        logger.warning("FilePicker.get_directory_path failed: %s", e)
        return None


async def save_file(
    page,
    title: str = "Save file",
    default_name: str = "file",
    extensions: list[str] | None = None,
    src_bytes: bytes | None = None,
) -> str | None:
    """Open a save file dialog and optionally write content.

    On iOS/Android/Web, src_bytes is required. When provided, the
    file content is written on all platforms.

    Args:
        page: The Flet page instance.
        title: Dialog window title.
        default_name: Default filename suggestion.
        extensions: List of allowed file extensions.
        src_bytes: File content bytes (required on mobile/web).

    Returns:
        Selected save path, or None if cancelled.
    """
    try:
        picker = _get_picker(page)
        file_type = FilePickerFileType.CUSTOM if extensions else FilePickerFileType.ANY
        kwargs = dict(
            dialog_title=title,
            file_name=default_name,
            allowed_extensions=extensions,
            file_type=file_type,
        )
        if src_bytes is not None:
            kwargs["src_bytes"] = src_bytes
        return await picker.save_file(**kwargs)
    except ValueError as e:
        logger.warning("FilePicker.save_file not supported on this platform: %s", e)
        return None
    except Exception as e:
        logger.error("FilePicker.save_file failed: %s", e)
        return None
