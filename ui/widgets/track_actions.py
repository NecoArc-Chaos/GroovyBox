"""Shared track action dialogs for GroovyBox."""

import os
import shutil

import flet as ft

from data import playlist_repository as prepo
from data import track_repository as trepo
from data.db import get_app_dir
from logic.localize import tr
from logic.metadata_service import format_duration


def show_track_details(page, track):
    file_size = "Unknown"
    try:
        if os.path.isfile(track.path):
            sz = os.path.getsize(track.path) / (1024 * 1024)
            file_size = f"{sz:.2f} MB"
    except Exception:
        pass

    rows = [
        _detail_row(tr("title"), track.title),
        _detail_row(tr("artist"), track.artist or "Unknown"),
        _detail_row(tr("album"), track.album or "Unknown"),
        _detail_row(tr("duration"), format_duration(track.duration)),
        _detail_row(tr("fileSize"), file_size),
        _detail_row(tr("filePath"), track.path),
    ]

    dlg = ft.AlertDialog(
        title=ft.Text(tr("trackDetails")),
        content=ft.Column(tight=True, controls=rows),
        actions=[ft.TextButton(tr("close"), on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)


def show_edit_dialog(page, track, on_saved=None):
    tf = ft.TextField(label=tr("title"), value=track.title)
    af = ft.TextField(label=tr("artist"), value=track.artist or "")
    alf = ft.TextField(label=tr("album"), value=track.album or "")

    new_art_path = [track.art_uri]

    def _build_cover_content(src):
        if src:
            return ft.Image(
                src=src, fit=ft.BoxFit.COVER, error_content=ft.Icon(ft.Icons.ALBUM, size=48, color=ft.Colors.WHITE54)
            )
        return ft.Icon(ft.Icons.ALBUM, size=48, color=ft.Colors.WHITE54)

    cover_img = ft.Container(
        width=120,
        height=120,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=_build_cover_content(track.art_uri),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
    )

    async def pick_cover(_):
        from logic.file_dialog import pick_files

        paths = await pick_files(page, tr("importCover"), ["jpg", "jpeg", "png", "webp", "bmp"], allow_multiple=False)
        if not paths:
            return
        src = paths[0]
        art_dir = os.path.join(get_app_dir(), "art")
        os.makedirs(art_dir, exist_ok=True)
        ext = os.path.splitext(src)[1] or ".jpg"
        dst = os.path.join(art_dir, f"cover_{track.id}{ext}")
        shutil.copy2(src, dst)
        new_art_path[0] = dst
        cover_img.content = _build_cover_content(dst)
        page.update()

    def remove_cover(e):
        new_art_path[0] = None
        cover_img.content = _build_cover_content(None)
        page.update()

    def save(e):
        trepo.update_metadata(track.id, tf.value, af.value or None, alf.value or None)
        trepo.update_art_uri(track.id, new_art_path[0])
        page.pop_dialog()
        if on_saved:
            on_saved()

    dlg = ft.AlertDialog(
        title=ft.Text(tr("editMetadata")),
        content=ft.Column(
            tight=True,
            width=320,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[cover_img]),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.TextButton(tr("changeCover"), on_click=lambda e: page.run_task(pick_cover, e)),
                        ft.TextButton(tr("removeCover"), on_click=remove_cover),
                    ],
                ),
                tf,
                af,
                alf,
            ],
        ),
        actions=[
            ft.TextButton(tr("cancel"), on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(tr("save"), on_click=save),
        ],
    )
    page.show_dialog(dlg)


def show_add_to_playlist(page, track):
    playlists = prepo.watch_all_playlists()
    if not playlists:
        page.show_dialog(ft.SnackBar(ft.Text(tr("noPlaylistsAvailable"))))
        return

    def pick_pl(e, pl):
        prepo.add_to_playlist(pl.id, track.id)
        page.pop_dialog()
        page.show_dialog(ft.SnackBar(ft.Text(tr("addedToPlaylist").replace("{}", pl.name))))

    dlg = ft.BottomSheet(
        content=ft.Column(
            tight=True,
            controls=[
                ft.Text(tr("addToPlaylist"), size=18, weight=ft.FontWeight.BOLD),
                *[ft.ListTile(title=ft.Text(p.name), on_click=lambda e, pl=p: pick_pl(e, pl)) for p in playlists],
            ],
        ),
    )
    page.show_dialog(dlg)


def _detail_row(label, value):
    return ft.Row(
        tight=True,
        controls=[
            ft.Container(width=100, content=ft.Text(label + ":", weight=ft.FontWeight.BOLD)),
            ft.Container(
                expand=True, content=ft.Text(str(value), color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE))
            ),
        ],
    )
