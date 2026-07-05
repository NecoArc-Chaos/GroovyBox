import flet as ft
from data import playlist_repository as prepo
from data.models import Playlist
from logic.localize import tr


def build_playlists_list(page: ft.Page, on_open: callable) -> ft.Control:
    playlists = prepo.watch_all_playlists()

    def create_new(e):
        name_f = ft.TextField(
            label=tr("playlistName"),
            autofocus=True,
            border_radius=12,
        )

        def do_create(e):
            name = name_f.value
            page.pop_dialog()
            if name and name.strip():
                if prepo.find_by_name(name.strip()):
                    page.show_dialog(ft.SnackBar(ft.Text(tr("playlistExists").replace("{}", name.strip()))))
                    return
                prepo.create_playlist(name.strip())
                page.update()

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

    tiles = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.ADD),
            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
            title=ft.Text(tr("createOne")),
            subtitle=ft.Text(tr("addNewPlaylist")),
            on_click=create_new,
        ),
        ft.Divider(height=1),
    ]

    if not playlists:
        tiles.append(
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(tr("noPlaylistsYet"), color=ft.Colors.GREY),
            )
        )
    else:
        def delete_pl(pid):
            prepo.delete_playlist(pid)
            page.update()

        for pl in playlists:
            tiles.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.QUEUE_MUSIC),
                    title=ft.Text(pl.name),
                    subtitle=ft.Text(f"{tr('createdAt')} {pl.created_at[:10]}" if pl.created_at else ""),
                    trailing=ft.IconButton(ft.Icons.DELETE, on_click=lambda e, pid=pl.id: delete_pl(pid)),
                    on_click=lambda e, p=pl: on_open(p),
                )
            )

    return ft.Column(tight=True, controls=tiles)
