"""Library Screen for GroovyBox.

This module implements the main library view with three tabs:
- Tracks: All audio tracks with search and selection
- Albums: Albums grouped by artist
- Playlists: User-created playlists

Supports both desktop (navigation rail) and mobile (tab buttons) layouts.
Includes batch operations for selected tracks (delete, add to playlist/queue).
"""

import os
import flet as ft
from data import track_repository as trepo
from data import playlist_repository as prepo
from data.models import Track
from logic.localize import tr
from logic.metadata_service import format_duration
from ui.widgets.track_tile import TrackTile
from ui.widgets.universal_image import UniversalImage
from ui.widgets.track_actions import show_track_details, show_edit_dialog
from logic.logger import logger
from data.db import is_mobile


class LibraryScreen(ft.Column):
    """Main library screen with tabbed navigation.
    
    Provides access to tracks, albums, and playlists. Supports
    multi-select mode for batch operations and real-time search filtering.
    
    Attributes:
        selected_ids: Set of track IDs selected in multi-select mode.
        search_query: Current search filter text.
        selected_tab: Active tab index (0=tracks, 1=albums, 2=playlists).
    """

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0)
        self._page = page
        self.selected_ids = set()
        self.search_query = ""
        self.selected_tab = 0
        self._sel_tile_refs = {}
        self._sel_count_text = None
        self._search_timer = None
        self._build()

    def _get_app(self):
        """Get the application instance from the session store."""
        return self._page.session.store.get("app")

    def on_window_size_changed(self):
        """Handle window resize by rebuilding the layout."""
        self._build()
        self.update()

    def _search_debounce(self):
        """Debounce search input to avoid rebuilding on every keystroke."""
        if self._search_timer:
            self._search_timer.cancel()
        self._search_timer = self._page.run_task(self._do_search)

    async def _do_search(self):
        """Execute search after debounce delay."""
        self._build()
        self.update()

    def _build(self):
        """Build the library screen layout.
        Chooses between large (rail) and mobile (tabs) layout based on width.
        """
        try:
            width = self._page.width or 0
            is_large = width > 600
            self.controls = [self._build_large_layout() if is_large else self._build_mobile_layout()]
        except Exception as ex:
            logger.exception("LibraryScreen._build failed")
            # Show a visible error state instead of a black screen
            self.controls = [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    padding=40,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER, size=48, color=ft.Colors.ERROR),
                            ft.Text(tr("appName"), size=20, weight=ft.FontWeight.BOLD),
                            ft.Text(str(ex), size=12, color=ft.Colors.ERROR),
                            ft.ElevatedButton(
                                tr("retry"),
                                on_click=lambda e: (self._build(), self.update()),
                            ),
                        ],
                    ),
                )
            ]

    def _build_large_layout(self):
        """Build desktop layout with NavigationRail sidebar.
        
        Returns:
            A Row with NavigationRail on the left and content on the right.
        """
        width = self._page.width or 0
        nav = ft.NavigationRail(
            selected_index=self.selected_tab,
            on_change=self._on_nav_change,
            bgcolor=ft.Colors.TRANSPARENT,
            extended=width > 800,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.AUDIOTRACK, label=ft.Text(tr("tracks"))),
                ft.NavigationRailDestination(icon=ft.Icons.ALBUM, label=ft.Text(tr("albums"))),
                ft.NavigationRailDestination(icon=ft.Icons.QUEUE_MUSIC, label=ft.Text(tr("playlists"))),
            ],
        )

        content = self._build_tab_content()

        return ft.Row(
            expand=True,
            spacing=0,
            controls=[
                nav,
                ft.Container(
                    expand=True,
                    border_radius=ft.border_radius.BorderRadius(16, 0, 0, 0),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=content,
                ),
            ],
        )

    def _build_mobile_layout(self):
        """Build mobile layout with horizontal tab buttons.
        
        Returns:
            A Column with tab buttons at top and content below.
        """
        def _make_tab(idx, icon, label):
            """Create a styled tab button."""
            is_sel = self.selected_tab == idx
            return ft.TextButton(
                content=ft.Row(
                    tight=True,
                    controls=[
                        ft.Icon(icon, size=18, color=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                        ft.Text(label, size=13, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL,
                                color=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                    ],
                ),
                on_click=lambda e, i=idx: self._on_mobile_tab_change(i),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(12, 8, 12, 8),
                ),
            )

        tab_row = ft.Container(
            padding=ft.Padding(8, 8, 8, 4),
            content=ft.Row(
                tight=True,
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                controls=[
                    _make_tab(0, ft.Icons.AUDIOTRACK, tr("tracks")),
                    _make_tab(1, ft.Icons.ALBUM, tr("albums")),
                    _make_tab(2, ft.Icons.QUEUE_MUSIC, tr("playlists")),
                ],
            ),
        )
        content = self._build_tab_content()
        return ft.Column(
            expand=True,
            spacing=0,
            controls=[tab_row, ft.Container(expand=True, content=content)],
        )

    def _on_mobile_tab_change(self, idx):
        """Handle tab selection on mobile layout."""
        self.selected_tab = idx
        self.selected_ids.clear()
        self._build()
        self.update()

    def _on_nav_change(self, e):
        """Handle NavigationRail selection on desktop layout."""
        self.selected_tab = int(e.control.selected_index)
        self.selected_ids.clear()
        self._build()
        self.update()

    def _on_tab_change(self, e):
        """Handle tab change event."""
        self.selected_tab = e.control.selected_index
        self.selected_ids.clear()
        self._build()
        self.update()

    def _build_tab_content(self):
        """Build the content for the currently selected tab.
        
        Returns:
            The appropriate screen widget for the active tab.
        """
        if self.selected_tab == 1:
            from ui.screens.albums_by_artist_screen import AlbumsByArtistScreen
            return AlbumsByArtistScreen(self._page)
        elif self.selected_tab == 2:
            from ui.screens.playlists_screen import PlaylistsScreen
            return PlaylistsScreen(self._page, on_refresh=lambda: (self._build(), self.update()))
        else:
            return self._build_tracks_content()

    def _build_tracks_content(self):
        """Build the tracks tab content with search and track list.
        
        Returns:
            A Stack with search bar overlay and scrollable track list.
        """
        all_tracks = trepo.watch_all_tracks()
        tracks = self._filter_tracks(all_tracks)

        is_sel_mode = bool(self.selected_ids)

        missing_tracks = [t for t in all_tracks if not os.path.isfile(t.path)]
        missing_set = {t.id for t in missing_tracks}
        missing_count = len(missing_tracks)

        # Build search hint text with track counts
        search_hint = tr("searchTracks")
        if all_tracks:
            if self.search_query:
                q = self.search_query.lower()
                filtered = sum(1 for t in all_tracks if q in t.title.lower() or (t.artist and q in t.artist.lower()) or (t.album and q in t.album.lower()))
                search_hint = tr("searchTracksFiltered", filtered, len(all_tracks))
            else:
                search_hint = tr("searchTracksWithCount", len(all_tracks))

        def on_search(e):
            """Handle search field submission."""
            self.search_query = e.control.value
            self._build()
            self.update()

        # Build top bar (search or selection)
        if is_sel_mode:
            top_bar = self._build_selection_bar()
        else:
            top_bar = ft.Container(
                padding=ft.Padding(16, 8, 16, 8),
                content=ft.TextField(
                    hint_text=search_hint,
                    prefix_icon=ft.Icons.SEARCH,
                    border=ft.InputBorder.OUTLINE,
                    border_radius=24,
                    dense=True,
                    value=self.search_query,
                    on_submit=on_search,
                    on_change=on_search_change,
                    filled=True,
                    fill_color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ),
            )

        # Build missing tracks banner
        missing_banner = None
        if missing_count > 0 and not is_sel_mode:
            def do_remove_missing(e):
                ids = [t.id for t in missing_tracks]
                trepo.delete_tracks(ids)
                self._build()
                self.update()

            missing_banner = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ERROR),
                padding=ft.Padding(12, 6, 12, 6),
                content=ft.Row(
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER, size=18, color=ft.Colors.ERROR),
                        ft.Container(width=8),
                        ft.Text(
                            tr("missingTracksBanner").format(str(missing_count)),
                            size=12, color=ft.Colors.ERROR, expand=True,
                        ),
                        ft.FilledButton(
                            tr("removeAllMissing"),
                            on_click=do_remove_missing,
                            height=28,
                            bgcolor=ft.Colors.RED,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                ),
            )

        # Build track list or empty state
        if not tracks:
            main = ft.ListView(
                spacing=2,
                padding=ft.Padding(0, 120 if missing_banner else 72, 0, 16),
                controls=[ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(tr("noTracksYet"), color=ft.Colors.GREY),
                )],
            )
        elif is_sel_mode:
            main = ft.ListView(
                spacing=2,
                padding=ft.Padding(0, 72, 0, 16),
                controls=self._build_selection_tiles(tracks, missing_set),
            )
        else:
            main = ft.ListView(
                spacing=2,
                padding=ft.Padding(0, 100 if missing_banner else 72, 0, 16),
                controls=self._build_track_tiles(tracks, missing_set),
            )

        overlay_controls = [ft.Container(top=0, left=0, right=0, content=top_bar)]
        if missing_banner:
            overlay_controls.append(ft.Container(top=44, left=0, right=0, content=missing_banner))

        return ft.Stack(
            expand=True,
            controls=[main, *overlay_controls],
        )

    def _build_selection_bar(self):
        """Build the multi-select action bar.
        
        Shows selected count and action buttons for batch operations:
        select all, deselect all, invert selection, and batch menu.
        
        Returns:
            A Container with the selection bar layout.
        """
        all_tracks = trepo.watch_all_tracks()
        total = len(all_tracks)
        sel_count = len(self.selected_ids)
        all_selected = sel_count == total

        def do_select_all(e):
            self.selected_ids = {t.id for t in all_tracks}
            self._build()
            self.update()

        def do_deselect_all(e):
            self.selected_ids.clear()
            self._build()
            self.update()

        def do_invert(e):
            current = set(self.selected_ids)
            self.selected_ids = {t.id for t in all_tracks if t.id not in current}
            self._build()
            self.update()

        def do_batch_delete(e):
            self._page.pop_dialog()
            def confirm_yes(e):
                self._page.pop_dialog()
                for tid in list(self.selected_ids):
                    trepo.delete_track(tid)
                self.selected_ids.clear()
                self._build()
                self.update()
            def confirm_no(e):
                self._page.pop_dialog()
            dlg = ft.AlertDialog(
                title=ft.Text(tr("deleteTracks")),
                content=ft.Text(tr("confirmBatchDelete").replace("{}", str(len(self.selected_ids)))),
                actions=[
                    ft.TextButton(tr("cancel"), on_click=confirm_no),
                    ft.FilledButton(tr("delete"), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=confirm_yes),
                ],
            )
            self._page.show_dialog(dlg)

        def do_batch_add_playlist(e):
            self._page.pop_dialog()
            self._show_batch_add_to_playlist()

        def do_batch_add_queue(e):
            self._page.pop_dialog()
            app = self._get_app()
            if not app or not app.audio_player:
                return
            all_tracks = trepo.watch_all_tracks()
            selected = [t for t in all_tracks if t.id in self.selected_ids]
            if not selected:
                return
            valid = [t for t in selected if os.path.exists(t.path)]
            missing = [t for t in selected if not os.path.exists(t.path)]
            if missing:
                names = [t.title or os.path.basename(t.path) for t in missing]
                if len(names) == 1:
                    msg = f"File not found: {names[0]}"
                else:
                    preview = ", ".join(names[:3])
                    extra = f"... (Total {len(names)})" if len(names) > 3 else ""
                    msg = f"Files not found: {preview}{extra}"
                dlg = ft.AlertDialog(
                    title=ft.Text("Error"),
                    content=ft.Text(msg),
                    actions=[ft.TextButton("OK", on_click=lambda e: self._page.pop_dialog())],
                )
                self._page.show_dialog(dlg)
            if not valid:
                return
            start_idx = len(app.audio_player.queue)
            app.audio_player.queue.extend(valid)
            if not app.audio_player.is_playing:
                app.audio_player.current_index = start_idx
                app.audio_player._load_current()
            if app.audio_player.on_queue_change:
                app.audio_player.on_queue_change()
            self.selected_ids.clear()
            self._build()
            self.update()

        def do_batch_menu(e):
            bs = ft.BottomSheet(
                content=ft.Column(
                    tight=True,
                    controls=[
                        ft.ListTile(leading=ft.Icon(ft.Icons.QUEUE_MUSIC), title=ft.Text(tr("addToQueue")), on_click=do_batch_add_queue),
                        ft.ListTile(leading=ft.Icon(ft.Icons.PLAYLIST_ADD), title=ft.Text(tr("addToPlaylist")), on_click=do_batch_add_playlist),
                        ft.ListTile(leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED), title=ft.Text(tr("delete"), color=ft.Colors.RED), on_click=do_batch_delete),
                    ],
                ),
            )
            self._page.show_dialog(bs)

        self._sel_count_text = ft.Text(f"{sel_count}", size=14, weight=ft.FontWeight.BOLD)
        return ft.Container(
            padding=ft.Padding(8, 4, 8, 4),
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            content=ft.Row(
                tight=True,
                controls=[
                    ft.IconButton(ft.Icons.CLOSE, icon_size=18, on_click=lambda e: self._exit_selection_mode()),
                    self._sel_count_text,
                    ft.Container(expand=True),
                    ft.TextButton(tr("selectAll"), on_click=do_select_all),
                    ft.TextButton(tr("deselectAll"), on_click=do_deselect_all) if all_selected else ft.Container(),
                    ft.TextButton(tr("invertSelection"), on_click=do_invert),
                    ft.IconButton(ft.Icons.MORE_VERT, icon_size=18, on_click=do_batch_menu),
                ],
            ),
        )

    def _exit_selection_mode(self):
        """Exit multi-select mode and clear selections."""
        self.selected_ids.clear()
        self._build()
        self.update()

    def _filter_tracks(self, tracks):
        """Filter tracks based on the current search query.
        
        Matches against title, artist, and album fields.
        
        Args:
            tracks: List of all tracks.
        
        Returns:
            Filtered list of tracks matching the search query.
        """
        q = self.search_query.lower().strip()
        if not q:
            return tracks
        result = []
        for t in tracks:
            if q in t.title.lower():
                result.append(t)
                continue
            if t.artist and q in t.artist.lower():
                result.append(t)
                continue
            if t.album and q in t.album.lower():
                result.append(t)
                continue
        return result

    def _build_track_tiles(self, tracks):
        """Build track tile widgets for the normal view.
        
        Args:
            tracks: List of tracks to display.
        
        Returns:
            List of TrackTile widgets.
        """
        tiles = []
        for t in tracks:
            tile = TrackTile(
                track=t,
                show_trailing=True,
                is_missing=not os.path.isfile(t.path),
                on_tap=lambda e, trk=t: self._play_track(trk),
                on_long_press=lambda e, trk=t: self._toggle_select(trk.id),
                on_trailing_pressed=lambda e, trk=t: self._show_track_options(trk),
                padding=4,
            )
            tiles.append(tile)
        return tiles

    def _build_selection_tiles(self, tracks, missing_set=None):
        """Build track tiles with checkboxes for multi-select mode.

        Args:
            tracks: List of tracks to display.
            missing_set: Pre-computed set of missing track IDs.

        Returns:
            List of Container widgets with checkboxes.
        """
        if missing_set is None:
            missing_set = set()
        tiles = []
        self._sel_tile_refs.clear()
        for t in tracks:
            is_sel = t.id in self.selected_ids
            is_missing = t.id in missing_set
            checkbox = ft.Checkbox(
                value=is_sel,
                label=t.title,
                on_change=lambda e, tid=t.id: self._toggle_select(tid),
            )
            container = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ERROR) if is_missing else (
                    ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT
                ),
                border_radius=8,
                content=checkbox,
                padding=ft.Padding(16, 4, 16, 4),
            )
            self._sel_tile_refs[t.id] = (container, checkbox)
            tiles.append(container)
        return tiles

    def _toggle_select(self, tid):
        """Toggle selection state for a track.

        Args:
            tid: The track ID to toggle.
        """
        was_empty = not self.selected_ids
        was_sel = tid in self.selected_ids

        if was_sel:
            self.selected_ids.remove(tid)
        else:
            self.selected_ids.add(tid)

        now_empty = not self.selected_ids

        if was_empty or now_empty:
            # Entering or exiting selection mode → full rebuild
            self._build()
            self.update()
        else:
            # Stayed in selection mode → update checkbox in-place
            container, checkbox = self._sel_tile_refs.get(tid, (None, None))
            if container and checkbox:
                is_sel = tid in self.selected_ids
                checkbox.value = is_sel
                container.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT
                container.update()
            if self._sel_count_text:
                self._sel_count_text.value = str(len(self.selected_ids))
                self._sel_count_text.update()

    def _play_track(self, track):
        """Play a single track from the library.
        
        Args:
            track: The Track object to play.
        """
        app = self._get_app()
        if app:
            logger.info(f"LibraryScreen._play_track: {track.title}")
            app.audio_player.play_track(track)
        else:
            logger.error("LibraryScreen._play_track: app is None")

    def _show_track_options(self, track):
        """Show context menu for a track.
        
        Options: Add to Playlist, View Details, Edit Metadata, Delete
        
        Args:
            track: The Track object to show options for.
        """
        def do_add_to_pl(e):
            self._page.pop_dialog()
            self._show_add_to_playlist(track)
        def do_view_details(e):
            self._page.pop_dialog()
            self._show_track_details(track)
        def do_edit(e):
            self._page.pop_dialog()
            self._show_edit_dialog(track)
        def do_delete(e):
            self._page.pop_dialog()
            def confirm_yes(e):
                self._page.pop_dialog()
                trepo.delete_track(track.id)
                self._build()
                self.update()
            def confirm_no(e):
                self._page.pop_dialog()
            dlg = ft.AlertDialog(
                title=ft.Text(tr("deleteTrack")),
                content=ft.Text(tr("confirmDeleteTrack").replace("{}", track.title or "")),
                actions=[
                    ft.TextButton(tr("cancel"), on_click=confirm_no),
                    ft.FilledButton(tr("delete"), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=confirm_yes),
                ],
            )
            self._page.show_dialog(dlg)

        bs = ft.BottomSheet(
            content=ft.Column(
                tight=True,
                controls=[
                    ft.ListTile(leading=ft.Icon(ft.Icons.PLAYLIST_ADD), title=ft.Text(tr("addToPlaylist")), on_click=do_add_to_pl),
                    ft.ListTile(leading=ft.Icon(ft.Icons.INFO), title=ft.Text(tr("viewDetails")), on_click=do_view_details),
                    ft.ListTile(leading=ft.Icon(ft.Icons.EDIT), title=ft.Text(tr("editMetadata")), on_click=do_edit),
                    ft.ListTile(leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED), title=ft.Text(tr("delete"), color=ft.Colors.RED), on_click=do_delete),
                ],
            ),
        )
        self._page.show_dialog(bs)

    def _show_batch_add_to_playlist(self):
        """Show playlist selection for batch adding selected tracks."""
        playlists = prepo.watch_all_playlists()
        if not playlists:
            self._page.show_dialog(ft.SnackBar(ft.Text(tr("noPlaylistsAvailable"))))
            return

        def pick_pl(e, pl):
            try:
                for tid in self.selected_ids:
                    prepo.add_to_playlist(pl.id, tid)
                self.selected_ids.clear()
                self._page.pop_dialog()
                self._build()
                self.update()
            except Exception as ex:
                logger.exception("_show_batch_add_to_playlist.pick_pl failed")

        dlg = ft.BottomSheet(
            content=ft.Column(
                tight=True,
                controls=[
                    ft.Text(tr("addToPlaylist"), size=18, weight=ft.FontWeight.BOLD),
                    *[ft.ListTile(title=ft.Text(p.name), on_click=lambda e, pl=p: pick_pl(e, pl)) for p in playlists],
                ],
            ),
        )
        self._page.show_dialog(dlg)

    def _show_add_to_playlist(self, track):
        from ui.widgets.track_actions import show_add_to_playlist
        show_add_to_playlist(self._page, track)

    def _show_track_details(self, track):
        show_track_details(self._page, track)

    def _show_edit_dialog(self, track):
        show_edit_dialog(self._page, track, on_saved=lambda: (self._build(), self.update()))


