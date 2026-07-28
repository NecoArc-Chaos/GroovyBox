"""Playlist Detail Screen for GroovyBox.

This module displays the detail view for a specific playlist, showing
the playlist name, action buttons, and a list of tracks in the playlist.
Supports playing, queuing, and exporting playlists.
"""

import flet as ft
import os
from data import playlist_repository as prepo
from logic.localize import tr
from logic.logger import logger
from data import db
from ui.widgets.track_tile import TrackTile


class PlaylistDetailView(ft.Container):
    """Playlist detail view with track listing and management controls.
    
    Provides controls to play all tracks, add to queue, and export
    the playlist in various formats (M3U, ZIP).
    
    Attributes:
        playlist: The Playlist object being displayed.
    """

    def __init__(self, page: ft.Page, playlist):
        super().__init__(expand=True)
        self._page = page
        self.playlist = playlist
        self._tracks = []
        self._track_list = None
        self._sort_func = None
        self._reverse_sort = False
        self._selecting = False
        self._selected_ids = set()
        self._sel_bar_count = None
        # page.width can be None during early Android init; default to mobile.
        self._is_mobile = (page.width or 0) < 600
        self._build()

    def _get_app(self):
        """Get the application instance from the session store."""
        return self._page.session.store.get("app")

    def _build(self):
        """Build the playlist detail view layout.

        Creates a scrollable view with:
        - Back button
        - Play All, Add to Queue, and Export buttons
        - Sort menu
        - Numbered track list with drag-and-drop reorder
        """
        self._tracks = prepo.watch_playlist_tracks(self.playlist.id)
        if self._sort_func:
            self._tracks.sort(key=self._sort_func, reverse=self._reverse_sort)

        self._track_list = ft.ReorderableListView(
            spacing=4,
            on_reorder=self._on_reorder,
            controls=self._build_track_controls(self._tracks)
        )

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # Back navigation
                ft.Container(
                    padding=8,
                    content=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self._go_back()),
                ),
                # Action buttons
                ft.Container(
                    padding=ft.Padding(12 if self._is_mobile else 16, 0, 12 if self._is_mobile else 16, 0),
                    content=ft.Row(
                        tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        wrap=True,
                        controls=[
                            ft.FilledButton(
                                tr("playAll"),
                                icon=ft.Icons.PLAY_ARROW,
                                height=36 if self._is_mobile else None,
                                on_click=lambda e: self._play_all(),
                            ),
                            ft.Container(width=6),
                            ft.OutlinedButton(
                                tr("addToQueue"),
                                icon=ft.Icons.QUEUE_MUSIC,
                                height=36 if self._is_mobile else None,
                                on_click=lambda e: self._add_to_queue(self._tracks),
                            ),
                            ft.Container(width=6),
                            ft.OutlinedButton(
                                tr("export"),
                                icon=ft.Icons.FILE_DOWNLOAD,
                                height=36 if self._is_mobile else None,
                                on_click=lambda e: self._show_export_dialog(),
                            ),
                            ft.Container(width=6),
                            ft.IconButton(
                                icon=ft.Icons.CHECKLIST if not self._selecting else ft.Icons.CHECKLIST_RTL,
                                icon_size=20,
                                selected=self._selecting,
                                on_click=self._toggle_select_mode,
                            ),
                            ft.Container(width=4),
                            ft.PopupMenuButton(
                                icon=ft.Icons.SORT,
                                tooltip=tr("sort"),
                                items=self._build_sort_menu_items(),
                            ),
                        ],
                    ),
                ),
                # Track list
                ft.Container(
                    expand=True,
                    padding=ft.Padding(12 if self._is_mobile else 16, 0, 12 if self._is_mobile else 16, 0),
                    content=self._track_list,
                ),
            ],
        )
        # Insert selection bar when in selecting mode
        if self._selecting:
            self.content.controls.insert(1, self._build_selection_bar())

    def _build_selection_bar(self):
        sel_count = len(self._selected_ids)
        self._sel_bar_count = ft.Text(f"{sel_count}", size=14, weight=ft.FontWeight.BOLD)
        return ft.Container(
            padding=ft.Padding(8, 4, 8, 4),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            content=ft.Row(
                tight=True,
                controls=[
                    self._sel_bar_count,
                    ft.Container(width=8),
                    ft.Text(tr("selected").replace("{}", str(sel_count)), size=13),
                    ft.Container(expand=True),
                    ft.FilledButton(
                        tr("remove"),
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        bgcolor=ft.Colors.RED,
                        color=ft.Colors.WHITE,
                        on_click=self._remove_selected,
                    ),
                ],
            ),
        )

    def _build_track_controls(self, tracks):
        controls = []
        for i, t in enumerate(tracks):
            is_sel = t.id in self._selected_ids
            tile = TrackTile(
                track=t,
                leading=ft.Text(str(i + 1).zfill(2), color=ft.Colors.GREY, size=14),
                on_tap=lambda e, idx=i: self._play_at(tracks, idx),
                padding=4,
                is_missing=not os.path.isfile(t.path),
            )
            if self._selecting:
                tile = ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    padding=ft.Padding(16, 4, 16, 4),
                    content=ft.Checkbox(
                        value=is_sel,
                        label=t.title,
                        on_change=lambda e, tid=t.id: self._toggle_select(tid),
                    ),
                )
            elif db.is_mobile():
                tid = t.id
                tile = ft.Dismissible(
                    content=tile,
                    background=ft.Container(
                        bgcolor=ft.Colors.RED,
                        alignment=ft.Alignment(1, 0),
                        padding=ft.Padding(0, 0, 16, 0),
                        content=ft.Text(tr("delete"), color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    ),
                    dismiss_direction=ft.DismissDirection.END_TO_START,
                    on_dismiss=lambda e, _tid=tid: self._remove_single_track(_tid),
                )
            controls.append(tile)
        controls.append(ft.Container(height=80))
        return controls

    def _toggle_select_mode(self, e):
        self._selecting = not self._selecting
        if not self._selecting:
            self._selected_ids.clear()
        self._build()
        self.update()

    def _toggle_select(self, tid):
        if tid in self._selected_ids:
            self._selected_ids.remove(tid)
        else:
            self._selected_ids.add(tid)
        self._rebuild_track_list()
        if self._sel_bar_count:
            self._sel_bar_count.value = str(len(self._selected_ids))
            self._sel_bar_count.update()

    def _remove_selected(self, e):
        for tid in list(self._selected_ids):
            prepo.remove_from_playlist(self.playlist.id, tid)
        self._selected_ids.clear()
        self._selecting = False
        self._build()
        self.update()

    def _remove_single_track(self, tid):
        prepo.remove_from_playlist(self.playlist.id, tid)
        self._build()
        self.update()

    def _rebuild_track_list(self):
        """Rebuild the track list controls in-place."""
        if self._track_list:
            self._track_list.controls = self._build_track_controls(self._tracks)
            self._track_list.update()

    def _build_sort_menu_items(self):
        """Build the sort menu items.

        Returns:
            List of PopupMenuItem widgets.
        """
        from data import playlist_repository as prepo

        def make_sort(label, key_func, reverse=False):
            def handler(e):
                self._sort_func = key_func
                self._reverse_sort = reverse
                self._tracks.sort(key=key_func, reverse=reverse)
                prepo.set_playlist_track_order(self.playlist.id, [t.id for t in self._tracks])
                self._rebuild_track_list()
            return ft.PopupMenuItem(content=ft.Text(label), on_click=handler)

        def make_reset():
            def handler(e):
                self._sort_func = None
                self._reverse_sort = False
                self._tracks = prepo.watch_playlist_tracks(self.playlist.id)
                prepo.set_playlist_track_order(self.playlist.id, [t.id for t in self._tracks])
                self._rebuild_track_list()
            return ft.PopupMenuItem(content=ft.Text(tr("sortDefault")), on_click=handler)

        def make_reverse():
            def handler(e):
                self._reverse_sort = not self._reverse_sort
                self._tracks.reverse()
                prepo.set_playlist_track_order(self.playlist.id, [t.id for t in self._tracks])
                self._rebuild_track_list()
            return ft.PopupMenuItem(content=ft.Text(tr("reverseOrder")), on_click=handler)

        return [
            make_reset(),
            ft.PopupMenuItem(content=ft.Divider(height=1)),
            make_sort(tr("sortTitleAsc"), lambda t: (t.title or "").lower()),
            make_sort(tr("sortTitleDesc"), lambda t: (t.title or "").lower(), reverse=True),
            make_sort(tr("sortArtist"), lambda t: (t.artist or "").lower()),
            make_sort(tr("sortAlbum"), lambda t: (t.album or "").lower()),
            make_sort(tr("sortDurationAsc"), lambda t: t.duration or 0),
            make_sort(tr("sortDurationDesc"), lambda t: t.duration or 0, reverse=True),
            ft.PopupMenuItem(content=ft.Divider(height=1)),
            make_reverse(),
        ]

    def _on_reorder(self, e):
        tracks = list(self._tracks)
        if self._selecting and self._selected_ids:
            sel = [i for i, t in enumerate(tracks) if t.id in self._selected_ids]
            unsel = [i for i in range(len(tracks)) if i not in sel]
            sel_tracks = [tracks[i] for i in sel]
            unsel_tracks = [tracks[i] for i in unsel]
            insert_pos = min(e.new_index, len(unsel_tracks))
            unsel_tracks[insert_pos:insert_pos] = sel_tracks
            tracks = unsel_tracks
        else:
            track = tracks.pop(e.old_index)
            tracks.insert(e.new_index, track)
        self._tracks = tracks
        self._sort_func = None
        self._reverse_sort = False
        prepo.set_playlist_track_order(self.playlist.id, [t.id for t in tracks])
        self._rebuild_track_list()

    def _show_export_dialog(self):
        """Show the playlist export configuration dialog.
        
        Allows the user to choose export options then saves via
        FilePicker (works on all platforms including mobile/web).
        """
        use_relpath_cb = ft.Checkbox(label=tr("useRelativePaths"), value=False)
        include_lyrics_cb = ft.Checkbox(label=tr("includeLyricsAndCovers"), value=False)
        as_zip_cb = ft.Checkbox(label=tr("packageAsZip"), value=False)

        async def do_export(e):
            """Export to temp file, then save via file picker."""
            import tempfile
            from logic.file_dialog import save_file
            from logic.playlist_exporter import export_playlist

            self._page.pop_dialog()
            suffix = ".zip" if as_zip_cb.value else ".m3u"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp_path = tmp.name
            tmp.close()
            try:
                out = export_playlist(
                    self.playlist.id,
                    tmp_path,
                    use_relpath=use_relpath_cb.value,
                    include_lyrics=include_lyrics_cb.value,
                    include_covers=include_lyrics_cb.value,
                    as_zip=as_zip_cb.value,
                )
                with open(out, "rb") as f:
                    file_bytes = f.read()
                saved = await save_file(self._page,
                    title=tr("export"),
                    default_name=f"{self.playlist.name or 'playlist'}{suffix}",
                    extensions=["zip" if as_zip_cb.value else "m3u"],
                    src_bytes=file_bytes,
                )
                if saved:
                    self._page.show_dialog(ft.SnackBar(ft.Text(tr("exported").replace("{}", os.path.basename(saved)))))
            except Exception as ex:
                logger.error(f"Export failed: {ex}")
                self._page.show_dialog(ft.SnackBar(ft.Text(tr("error", str(ex)))))
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        dlg = ft.AlertDialog(
            title=ft.Text(tr("export")),
            content=ft.Column(
                tight=True, width=320,
                controls=[
                    use_relpath_cb,
                    include_lyrics_cb,
                    as_zip_cb,
                ],
            ),
            actions=[
                ft.TextButton(tr("cancel"), on_click=lambda e: self._page.pop_dialog()),
                ft.FilledButton(tr("export"), on_click=lambda e: self._page.run_task(do_export, e)),
            ],
        )
        self._page.show_dialog(dlg)

    def _go_back(self):
        """Navigate back to the previous screen."""
        self._page.views.pop()
        self._page.run_task(self._page.push_route, self._page.views[-1].route if self._page.views else "/library")

    def _play_all(self, tracks=None, initial_index=0):
        """Play all tracks in the playlist.
        
        Args:
            tracks: Optional pre-loaded track list. If None, fetches from DB.
            initial_index: Index to start playback from.
        """
        if tracks is None:
            tracks = prepo.watch_playlist_tracks(self.playlist.id)
        if tracks:
            app = self._get_app()
            if app:
                app.audio_player.play_tracks(tracks, initial_index)

    def _play_at(self, tracks, idx):
        """Play the playlist starting from a specific track index.
        
        Args:
            tracks: List of tracks in the playlist.
            idx: Index of the track to start from.
        """
        self._play_all(tracks, idx)

    def _add_to_queue(self, tracks):
        """Add all playlist tracks to the playback queue.
        
        Args:
            tracks: List of tracks to add.
        """
        app = self._get_app()
        if app and tracks:
            for t in tracks:
                app.audio_player.queue.append(t)
            if app.audio_player.on_queue_change:
                app.audio_player.on_queue_change()
