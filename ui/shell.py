"""Shell View for GroovyBox.

This module defines the main application shell layout that wraps
all screens except the full-screen player. Provides a toolbar with
navigation and import actions, a content area for screen switching,
and a persistent mini player at the bottom.
"""

import os
import flet as ft
from logic.localize import tr
from logic.logger import logger
from data import db
from data.track_repository import AUDIO_EXTENSIONS, LYRICS_EXTENSIONS
from ui.widgets.mini_player import MiniPlayerWidget


class ShellView(ft.View):
    """Main application shell that provides the common layout structure.
    
    Contains three main sections:
    - Toolbar: Navigation buttons (Home, Settings) and import action
    - Content view: Swappable area for different screens
    - Mini player: Persistent playback controls at the bottom
    
    Attributes:
        content_view: Column container for the active screen content.
        mini_player: The MiniPlayerWidget instance at the bottom.
    """

    def __init__(self, page: ft.Page):
        super().__init__(route="/", padding=0, spacing=0)
        self._page = page
        self.app = page.session.store.get("app")
        # page.width can be None during early Android initialization.
        # Default to mobile layout (True) when size is unknown; it will
        # self-correct on the first resize event once the Flutter client
        # reports the real viewport size.
        # Use platform detection as a secondary guard: SafeArea and
        # navigation_bar should only be applied on actual mobile platforms,
        # not on desktop windows that happen to be narrow.
        self._is_mobile = self._detect_mobile(page)

        # Main content area and mini player
        self.content_view = ft.Column(expand=True, spacing=0)
        self.mini_player = MiniPlayerWidget(page)

        # Build navigation bar for mobile (MD3 style)
        self.navigation_bar = None
        if self._is_mobile:
            self.navigation_bar = self._build_navigation_bar()

        # Assemble the shell layout with optional global background
        body = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                self._build_toolbar(),
                self.content_view,
                ft.Container(content=self.mini_player),
            ],
        )

        # On mobile, wrap in a Stack with left-edge swipe-back detector
        if self._is_mobile:
            body = ft.Stack(
                expand=True,
                controls=[
                    body,
                    ft.GestureDetector(
                        left=0, top=0, bottom=0, width=40,
                        on_horizontal_drag_start=self._on_back_drag_start,
                        on_horizontal_drag_update=self._on_back_drag_update,
                        on_horizontal_drag_end=self._on_back_drag_end,
                    ),
                ],
            )

        # On mobile devices, use SafeArea and set navigation bar
        if self._is_mobile:
            self._page.navigation_bar = self.navigation_bar
            body = ft.SafeArea(
                content=body,
                avoid_intrusions_top=True,
                avoid_intrusions_bottom=False,
            )

        bg_wrapper = self._build_global_bg_wrapper(body)
        self.controls = [bg_wrapper] if bg_wrapper else [body]

    @staticmethod
    def _detect_mobile(page: ft.Page) -> bool:
        """Detect whether the current platform is a mobile device.

        Uses page.width as primary signal, falling back to platform
        detection when width is None (early init) or when the window
        is intentionally narrow on desktop.
        """
        try:
            w = page.width
            if w is not None and w >= 600:
                return False
            if w is not None and w < 600:
                # Narrow window — could be mobile or resized desktop.
                # Use platform string as tie-breaker.
                return ShellView._platform_is_mobile(page)
            # width is None: early init. Guess from platform.
            return ShellView._platform_is_mobile(page)
        except Exception:
            return False

    @staticmethod
    def _platform_is_mobile(page: ft.Page) -> bool:
        """Return True if the page platform indicates a mobile device."""
        try:
            platform = getattr(page, "platform", None) or getattr(page, "platform_type", None)
            if platform is None:
                return False
            p = str(platform).lower()
            mobile_platforms = ("android", "ios", "iphone", "ipad")
            return any(m in p for m in mobile_platforms)
        except Exception:
            return False

    @property
    def page(self):
        """Access the Flet page instance."""
        return self._page

    def _build_global_bg_wrapper(self, body):
        """Wrap body in a container with global background if configured."""
        path = db.get_setting("global_bg_path", "")
        hidden = db.get_setting("global_bg_hidden", "false") == "true"
        if hidden or not path or not os.path.isfile(path):
            return None
        return ft.Container(
            expand=True,
            image=ft.DecorationImage(src=path, fit=ft.BoxFit.COVER),
            content=ft.Container(
                expand=True,
                bgcolor=ft.Colors.with_opacity(0.65, ft.Colors.SURFACE),
                content=body,
            ),
        )

    def _go_back(self):
        route = self._page.route
        if route in ("/playlist", "/album", "/artist"):
            self._page.run_task(self._page.push_route, "/library")

    def _on_back_drag_start(self, e):
        self._swipe_back_started = True

    def _on_back_drag_update(self, e):
        if self._swipe_back_started and e.delta_x > 100:
            self._swipe_back_started = False
            self._go_back()

    def _on_back_drag_end(self, e):
        self._swipe_back_started = False

    def refresh_mini_player(self):
        """Force a refresh of the mini player widget."""
        self.mini_player.refresh()

    def on_window_size_changed(self):
        """Handle window resize by refreshing the mini player layout."""
        # Re-detect mobile/desktop and rebuild shell if the category changed
        new_is_mobile = self._detect_mobile(self._page)
        if new_is_mobile != self._is_mobile:
            self._is_mobile = new_is_mobile
            # Rebuild the entire shell layout
            if self.app:
                self.app._reload_ui()
            return
        if hasattr(self.mini_player, 'on_window_size_changed'):
            self.mini_player.on_window_size_changed()

    def _build_toolbar(self):
        """Build the top toolbar with navigation and import buttons.
        
        Returns:
            A Container with the toolbar layout including Home, Settings,
            and Import buttons.
        """
        return ft.Container(
            height=44,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            padding=ft.Padding(4, 0, 8, 0),
            content=ft.Row(
                tight=True,
                controls=[
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.HOME_OUTLINED,
                        icon_size=20,
                        tooltip=tr("home"),
                        on_click=lambda e: self._page.run_task(self._page.push_route, "/library"),
                    ),
                    ft.IconButton(
                        ft.Icons.SETTINGS_OUTLINED,
                        icon_size=20,
                        tooltip=tr("settings"),
                        on_click=lambda e: self._page.run_task(self._page.push_route, "/settings"),
                    ),
                    ft.IconButton(
                        ft.Icons.ADD_CIRCLE_OUTLINE,
                        icon_size=20,
                        tooltip=tr("importFiles"),
                        on_click=self._show_import_menu,
                    ),
                ],
            ),
        )

    def _build_navigation_bar(self):
        """Build MD3-style bottom navigation bar for mobile.
        
        Returns:
            A NavigationBar with Library, Playlists, and Settings destinations.
        """
        def on_nav_change(e):
            selected_index = e.control.selected_index
            if selected_index == 0:
                self._page.run_task(self._page.push_route, "/library")
            elif selected_index == 1:
                self._page.run_task(self._page.push_route, "/playlists")
            elif selected_index == 2:
                self._page.run_task(self._page.push_route, "/settings")

        return ft.NavigationBar(
            selected_index=0,
            on_change=on_nav_change,
            label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.LIBRARY_MUSIC_OUTLINED,
                    selected_icon=ft.Icons.LIBRARY_MUSIC,
                    label=tr("library"),
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.PLAYLIST_PLAY_OUTLINED,
                    selected_icon=ft.Icons.PLAYLIST_PLAY,
                    label=tr("playlists"),
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label=tr("settings"),
                ),
            ],
        )

    def _show_import_menu(self, e):
        """Show the import options bottom sheet menu.
        
        Offers multiple import methods:
        - Audio files: Individual file selection
        - Folder: Scan an entire directory
        - Playlist: Import from M3U/PLS files
        - ZIP: Extract and import from ZIP archives
        - Path: Manual path entry
        """
        def do_files(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_files)

        def do_folder(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_folder)

        def do_playlist(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_playlist_file)

        def do_zip(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_zip)

        def do_path(e):
            self._page.pop_dialog()
            self._page.run_task(self._import_from_path)

        bs = ft.BottomSheet(
            content=ft.Column(
                tight=True,
                controls=[
                    ft.ListTile(leading=ft.Icon(ft.Icons.AUDIOTRACK), title=ft.Text(tr("importAudioFiles")), on_click=do_files),
                    ft.ListTile(leading=ft.Icon(ft.Icons.FOLDER_OPEN), title=ft.Text(tr("importFolder")), on_click=do_folder),
                    ft.ListTile(leading=ft.Icon(ft.Icons.QUEUE_MUSIC), title=ft.Text(tr("importPlaylist")), on_click=do_playlist),
                    ft.ListTile(leading=ft.Icon(ft.Icons.FOLDER_ZIP), title=ft.Text(tr("importZip")), on_click=do_zip),
                    ft.Divider(),
                    ft.ListTile(leading=ft.Icon(ft.Icons.KEYBOARD), title=ft.Text(tr("importFromPath")), on_click=do_path),
                ],
            ),
        )
        self._page.show_dialog(bs)

    async def _import_files(self, paths=None):
        """Import audio and lyrics files from file picker or provided paths.
        
        Separates audio files from lyrics files, imports audio into the
        database, and attempts to match lyrics to existing tracks.
        
        Args:
            paths: Optional list of file paths. If None, opens file picker.
        """
        from logic.file_dialog import pick_files
        all_ext = list(AUDIO_EXTENSIONS | LYRICS_EXTENSIONS)
        if paths is None:
            paths = await pick_files(self._page, title="Select files to import", extensions=all_ext)
        if not paths:
            logger.debug("_import_files: no files selected")
            return
        logger.info(f"_import_files: selected {len(paths)} files")
        from data import track_repository as trepo
        import os

        # Separate audio and lyrics files
        audio_paths = [p for p in paths if p.split(".")[-1].lower() in AUDIO_EXTENSIONS]
        lyrics_paths = [p for p in paths if p.split(".")[-1].lower() in LYRICS_EXTENSIONS]
        logger.debug(f"_import_files: audio={len(audio_paths)} lyrics={len(lyrics_paths)}")

        if audio_paths:
            n = await trepo.import_files_async(audio_paths)
            logger.info(f"Imported {n} audio files")

        if lyrics_paths:
            await self._import_lyrics_files(lyrics_paths)

        await self._reload_after_import()

    async def _import_folder(self):
        """Import all audio files from a selected folder."""
        from logic.file_dialog import pick_directory
        folder = await pick_directory(self._page, title=tr("importFolder"))
        if not folder:
            return
        logger.info(f"_import_folder: {folder}")
        from data import track_repository as trepo
        n = await trepo.scan_directory_async(folder)
        logger.info(f"Imported {n} files from folder")
        await self._reload_after_import()

    async def _import_playlist_file(self):
        """Import audio files referenced in M3U/PLS playlist files."""
        from logic.file_dialog import pick_files
        paths = await pick_files(self._page, title=tr("importPlaylist"), extensions=["m3u", "m3u8", "pls"])
        if not paths:
            return
        from logic.playlist_parser import parse_playlist
        from data import track_repository as trepo
        all_audio = []
        for pp in paths:
            all_audio.extend(parse_playlist(pp))
        if all_audio:
            n = await trepo.import_files_async(all_audio)
            logger.info(f"Imported {n} files from playlist")
            await self._reload_after_import()

    async def _import_zip(self):
        """Import audio files from ZIP archives."""
        from logic.file_dialog import pick_files
        paths = await pick_files(self._page, title=tr("importZip"), extensions=["zip"])
        if not paths:
            return
        from logic.zip_importer import extract_zip
        from data import track_repository as trepo
        import tempfile
        import shutil
        all_audio = []
        all_lyrics = []
        temp_dirs = []
        for zp in paths:
            dest = tempfile.mkdtemp(prefix="groovybox_zip_")
            temp_dirs.append(dest)
            audio_files, lyrics_files, playlist_files = extract_zip(zp, dest)
            all_audio.extend(audio_files)
            all_lyrics.extend(lyrics_files)
            # Parse any playlist files found in the ZIP
            for pp in playlist_files:
                from logic.playlist_parser import parse_playlist
                all_audio.extend(parse_playlist(pp))
        if all_audio:
            n = await trepo.import_files_async(all_audio, copy=True)
            logger.info(f"Imported {n} audio files from zip")
        if all_lyrics:
            await self._import_lyrics_files(all_lyrics)
        # Clean up temporary extraction directories
        # (files have been copied to internal storage when copy=True)
        for d in temp_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        await self._reload_after_import()

    async def _import_from_path(self):
        """Show dialog for manual path entry and import."""
        path_field = ft.TextField(
            hint_text=tr("pathPlaceholder"),
            expand=True,
            autofocus=True,
        )

        async def do_import(e):
            path = path_field.value.strip()
            if not path:
                return
            self._page.pop_dialog()
            await self._handle_path_import(path)

        dialog = ft.AlertDialog(
            title=ft.Text(tr("importFromPath")),
            content=ft.Column(
                tight=True,
                width=400,
                controls=[
                    ft.Text(tr("enterPath")),
                    path_field,
                ],
            ),
            actions=[
                ft.TextButton(tr("cancel"), on_click=lambda e: self._page.pop_dialog()),
                ft.FilledButton(tr("importAction"), on_click=do_import),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dialog)

    async def _handle_path_import(self, path):
        """Handle import from a manually entered path.
        
        Detects whether the path is a directory, audio file,
        playlist file, or ZIP archive and imports accordingly.
        
        Args:
            path: The file or directory path to import.
        """
        import os
        from data import track_repository as trepo

        if not os.path.exists(path):
            self._page.show_dialog(ft.SnackBar(ft.Text(tr("pathNotFound", path))))
            return

        # Directory: scan for audio files
        if os.path.isdir(path):
            n = await trepo.scan_directory_async(path)
            if n:
                msg = tr("imported") + f" {n} " + tr("tracks")
                self._page.show_dialog(ft.SnackBar(ft.Text(msg)))
            await self._reload_after_import()
            return

        ext = os.path.splitext(path)[1].lower().lstrip(".")

        # Audio file: import directly
        if ext in AUDIO_EXTENSIONS:
            await self._import_files([path])

        # Playlist file: parse and import referenced files
        elif ext in ("m3u", "m3u8", "pls"):
            from logic.playlist_parser import parse_playlist
            audio_paths = parse_playlist(path)
            if audio_paths:
                n = await trepo.import_files_async(audio_paths)
                msg = tr("imported") + f" {n} " + tr("tracks")
                self._page.show_dialog(ft.SnackBar(ft.Text(msg)))
            await self._reload_after_import()

        # ZIP archive: extract and import contents
        elif ext == "zip":
            from logic.zip_importer import extract_zip
            import tempfile
            import shutil
            dest = tempfile.mkdtemp(prefix="groovybox_zip_")
            audio_files, lyrics_files, playlist_files = extract_zip(path, dest)
            for pp in playlist_files:
                from logic.playlist_parser import parse_playlist
                audio_files.extend(parse_playlist(pp))
            n_audio = 0
            if audio_files:
                n_audio = await trepo.import_files_async(audio_files, copy=True)
            if lyrics_files:
                await self._import_lyrics_files(lyrics_files)
            # Clean up temporary extraction directory
            # (files have been copied to internal storage)
            try:
                shutil.rmtree(dest, ignore_errors=True)
            except Exception:
                pass
            msg = tr("imported") + f" {n_audio} " + tr("tracks")
            if lyrics_files:
                msg += f", {len(lyrics_files)} " + tr("lyricsLines")
            self._page.show_dialog(ft.SnackBar(ft.Text(msg)))
            await self._reload_after_import()

        else:
            self._page.show_dialog(ft.SnackBar(ft.Text(tr("unsupportedFileType", ext))))

    async def _import_lyrics_files(self, lyrics_paths):
        """Batch import lyrics files by matching filenames to track titles.
        
        Attempts to match each lyrics file to an existing track by
        comparing the filename (without extension) to track titles.
        
        Args:
            lyrics_paths: List of absolute paths to lyrics files.
        """
        from logic.encoding_helper import read_with_encoding
        from data import track_repository as trepo
        import os
        all_tracks = trepo.watch_all_tracks()
        matched = 0
        not_matched = 0
        for lp in lyrics_paths:
            base = os.path.splitext(os.path.basename(lp))[0].lower()
            match = None
            # Try to find a matching track by title
            for t in all_tracks:
                if t.title.lower() == base or base in t.title.lower() or t.title.lower() in base:
                    match = t
                    break
            if match:
                content = read_with_encoding(lp)
                from logic.lyrics_parser import parse, lyrics_to_json
                ldata = parse(content, os.path.basename(lp))
                trepo.update_lyrics(match.id, lyrics_to_json(ldata))
                matched += 1
            else:
                not_matched += 1
        msg = f"Batch import: {matched} matched, {not_matched} not matched"
        logger.info(msg)
        self._page.show_dialog(ft.SnackBar(ft.Text(msg)))

    async def _reload_after_import(self):
        """Reload the UI after completing an import operation.
        
        Refreshes the page and triggers a full UI rebuild to reflect
        the newly imported tracks.
        """
        from data import track_repository as trepo
        n = len(trepo.watch_all_tracks())
        logger.info("_reload_after_import: %d tracks in DB, reloading UI", n)
        self._page.update()
        if self.app:
            self.app._reload_ui()
