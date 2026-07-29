import flet as ft
from data import playlist_repository as prepo
from logic.localize import tr


def build_albums_grid(page: ft.Page, on_open: callable) -> ft.Control:
    albums = prepo.watch_all_albums()

    if not albums:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(tr("noAlbumsFound"), color=ft.Colors.GREY),
        )

    return ft.Container(
        expand=True,
        content=ft.GridView(
            expand=True,
            runs_count=0,
            max_extent=200,
            child_aspect_ratio=0.85,
            spacing=16,
            run_spacing=16,
            padding=16,
            controls=[_album_card(page, a, on_open) for a in albums],
        ),
    )


def _album_card(page: ft.Page, album, on_open):
    return ft.Container(
        content=ft.Column(
            tight=True,
            controls=[
                ft.Container(
                    expand=True,
                    content=ft.Image(
                        src=album.art_uri,
                        fit=ft.BoxFit.COVER,
                        error_content=ft.Icon(ft.Icons.ALBUM, size=48, color=ft.Colors.WHITE54),
                    ),
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                ),
                ft.Container(
                    padding=8,
                    content=ft.Column(
                        tight=True,
                        spacing=2,
                        controls=[
                            ft.Text(album.album, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, size=13, weight=ft.FontWeight.W_500),
                            ft.Text(album.artist, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, size=11, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                        ],
                    ),
                ),
            ],
        ),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.15, ft.Colors.SHADOW)),
        on_click=lambda e: on_open(album),
        ink=True,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
