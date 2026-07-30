"""Playlists Screen for GroovyBox.

This module displays the list of user-created playlists with options
to create new playlists, open existing ones, and delete playlists.
"""

import flet as ft

from data import playlist_repository as prepo
from logic.localize import tr


def PlaylistsScreen(page: ft.Page, on_refresh=None) -> ft.Control:
    """Build the playlists management screen.

    Shows a list of all playlists with create and delete options.
    Tapping a playlist navigates to its detail view.

    Args:
        page: The Flet page instance.

    Returns:
        A scrollable Column with playlist list items.
    """
    playlists = prepo.watch_all_playlists()
    is_mobile = (page.width or 0) < 600

    def create_new(e):
        """Show dialog for creating a new playlist."""
        name_f = ft.TextField(
            label=tr("playlistName"),
            autofocus=True,
            border_radius=12,
        )

        def do_create(e):
            """Handle playlist creation."""
            name = name_f.value
            page.pop_dialog()
            if name and name.strip():
                if prepo.find_by_name(name.strip()):
                    page.show_dialog(ft.SnackBar(ft.Text(tr("playlistExists").replace("{}", name.strip()))))
                    return
                prepo.create_playlist(name.strip())
                if on_refresh:
                    on_refresh()

        bs = ft.BottomSheet(
            content=ft.Container(
                padding=24,
                content=ft.Column(
                    tight=True,
                    controls=[
                        ft.Text(tr("newPlaylist"), size=18, weight=ft.FontWeight.BOLD),
                        name_f,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                ft.TextButton(tr("cancel"), on_click=lambda e: page.pop_dialog()),
                                ft.FilledButton(tr("create"), on_click=do_create),
                            ],
                        ),
                    ],
                ),
            ),
        )
        page.show_dialog(bs)

    def open_playlist(pl):
        """Navigate to a playlist's detail view."""
        page.session.store.set("playlist_data", pl)
        page.run_task(page.push_route, "/playlist")

    # Build playlist tiles
    tiles = []
    tile_pad = ft.Padding(16, 4, 16, 4) if not is_mobile else ft.Padding(12, 8, 12, 8)
    trailing_size = 20 if not is_mobile else 24
    tiles.append(
        ft.ListTile(
            leading=ft.Icon(ft.Icons.ADD),
            title=ft.Text(tr("createOne")),
            subtitle=ft.Text(tr("addNewPlaylist")),
            on_click=create_new,
        ),
    )
    tiles.append(ft.Divider(height=1))

    if not playlists:
        tiles.append(
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(tr("noPlaylistsYet"), color=ft.Colors.GREY),
            )
        )
    else:
        for pl in playlists:
            tiles.append(
                ft.Container(
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.QUEUE_MUSIC),
                        title=ft.Text(pl.name),
                        subtitle=ft.Text(f"{tr('createdAt')} {pl.created_at[:10]}" if pl.created_at else ""),
                        trailing=ft.IconButton(
                            ft.Icons.DELETE,
                            icon_size=trailing_size,
                            on_click=lambda e, pid=pl.id, pname=pl.name: _delete_pl(pid, pname),
                        ),
                        on_click=lambda e, p=pl: open_playlist(p),
                        min_height=48 if is_mobile else 56,
                    ),
                    padding=tile_pad,
                )
            )

    def _delete_pl(pid, pname=""):
        """Show confirmation dialog for playlist deletion."""

        def confirm_yes(e):
            prepo.delete_playlist(pid)
            page.pop_dialog()
            if on_refresh:
                on_refresh()

        def confirm_no(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(tr("delete")),
            content=ft.Text(tr("confirmDeletePlaylist").replace("{}", pname)),
            actions=[
                ft.TextButton(tr("cancel"), on_click=confirm_no),
                ft.FilledButton(tr("delete"), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=confirm_yes),
            ],
        )
        page.show_dialog(dlg)

    return ft.Column(controls=tiles, scroll=ft.ScrollMode.AUTO)
