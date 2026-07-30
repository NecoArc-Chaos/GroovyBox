"""Universal Image Widget for GroovyBox.

This module provides a UniversalImage container that handles displaying
images from various sources (local files, network URLs) with automatic
fallback to an icon when the image cannot be loaded.
"""

import os

import flet as ft


class UniversalImage(ft.Container):
    """An image container that supports local files and network URLs.

    Automatically displays a fallback icon when:
    - The URI is None or empty
    - The file doesn't exist on disk
    - The image fails to load

    Attributes:
        _uri: The image source URI (local path or URL).
        _fit: How the image should fit within its bounds.
        _fallback_icon: Icon to display when image is unavailable.
        _fallback_icon_size: Size of the fallback icon.
    """

    def __init__(
        self,
        uri: str | None = None,
        width: float | None = None,
        height: float | None = None,
        border_radius: float | None = None,
        fit: ft.BoxFit = ft.BoxFit.COVER,
        fallback_icon: str = ft.Icons.IMAGE,
        fallback_icon_size: float = 48,
    ):
        self._uri = uri
        self._fit = fit
        self._fallback_icon = fallback_icon
        self._fallback_icon_size = fallback_icon_size
        self._border_radius_val = border_radius

        content = self._build_content()

        super().__init__(
            content=content,
            width=width,
            height=height,
            border_radius=border_radius,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        )

    def _is_network(self, uri: str) -> bool:
        """Check if a URI points to a network resource.

        Args:
            uri: The URI string to check.

        Returns:
            True if the URI starts with http:// or https://.
        """
        return uri.startswith("http://") or uri.startswith("https://")

    def _build_content(self):
        if not self._uri or not os.path.isfile(self._uri):
            return ft.Icon(
                icon=self._fallback_icon,
                size=self._fallback_icon_size,
                color=ft.Colors.WHITE54,
            )

        return ft.Image(
            src=self._uri,
            fit=self._fit,
            error_content=ft.Icon(
                icon=self._fallback_icon,
                size=self._fallback_icon_size,
                color=ft.Colors.WHITE54,
            ),
        )
