"""Settings Screen for GroovyBox.

This module provides the application settings interface, including
music library management, player configuration, theme settings,
language selection, database management, and log export.
"""

import json
import os
import flet as ft
import threading
from data import db
from data import track_repository as trepo
from logic.localize import tr, load_locale, get_locale
from logic.logger import logger
from logic.key_bindings import DEFAULT_KEY_BINDINGS, ACTION_NAMES, ACTION_ORDER


def SettingsScreen(page: ft.Page) -> ft.Column:
    """Build the settings screen with all configuration sections.
    
    Sections include:
    - Auto Scan: Toggle automatic library scanning
    - Music Libraries: Manage watch folders
    - Player Settings: Default screen, lyrics mode, continue playing
    - App Settings: Language, theme mode
    - Database Management: Reset track database
    - Logs: Log level and export
    - About: Application information
    
    Args:
        page: The Flet page instance.
    
    Returns:
        A scrollable Column with all settings sections.
    """
    app = page.session.store.get("app")

    # Read build info
    _build_info_path = os.path.join(os.path.dirname(__file__), "..", "..", "build-config.json")
    _build_version = "1.0.0"
    _build_number = 0
    try:
        with open(_build_info_path, encoding="utf-8") as f:
            info = json.load(f)
            _build_version = info.get("app", {}).get("build_version", _build_version)
            _build_number = info.get("app", {}).get("build_number", 0)
    except Exception:
        pass

    def load_settings():
        """Load current settings from the database."""
        return {
            "auto_scan": db.get_setting("auto_scan", "true") == "true",
            "default_player_screen": db.get_setting("default_player_screen", "cover"),
            "lyrics_mode": db.get_setting("lyrics_mode", "auto"),
            "continue_plays": db.get_setting("continue_plays", "false") == "true",
            "theme_mode": db.get_setting("theme_mode", "system"),
        }

    settings = load_settings()

    def save_setting(key, value):
        """Save a setting and refresh the local cache."""
        db.set_setting(key, str(value).lower())
        nonlocal settings
        settings = load_settings()

    def refresh():
        """Refresh the page display."""
        page.update()

    def _build_global_bg_ui():
        """Build the global background image picker UI."""
        async def _pick_global_bg(_):
            from logic.file_dialog import pick_files
            paths = await pick_files(page, tr("selectImage"),
                ["jpg", "jpeg", "png", "webp", "bmp"], allow_multiple=False)
            if paths:
                db.set_setting("global_bg_path", paths[0])
                page.update()
                app = page.session.store.get("app")
                if app:
                    app._reload_ui()

        def _clear_global_bg(e):
            db.set_setting("global_bg_path", "")
            page.update()
            app = page.session.store.get("app")
            if app:
                app._reload_ui()

        return ft.Column(visible=True, spacing=8, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.FilledButton(tr("selectImage"), on_click=lambda e: page.run_task(_pick_global_bg, e)),
                ft.Container(width=12),
                ft.OutlinedButton(tr("clearImage"), on_click=_clear_global_bg),
            ]),
        ])

    def on_auto_scan_change(e):
        """Handle auto-scan toggle change."""
        save_setting("auto_scan", e.control.value)
        refresh()

    def on_continue_plays_change(e):
        """Handle continue-playing toggle change."""
        save_setting("continue_plays", e.control.value)
        refresh()

    def on_language_change(e):
        """Handle language selection change."""
        lang = e.control.value
        load_locale(lang)
        db.set_setting("language", lang)
        page.show_dialog(ft.SnackBar(ft.Text(tr("language") + ": " + lang)))
        if app:
            app._reload_ui()

    def on_default_screen_change(e):
        """Handle default player screen selection change."""
        save_setting("default_player_screen", e.control.value)
        refresh()

    def on_lyrics_mode_change(e):
        """Handle lyrics display mode change."""
        save_setting("lyrics_mode", e.control.value)
        refresh()

    def on_theme_mode_change(e):
        """Handle theme mode change (system/light/dark)."""
        val = e.control.value
        save_setting("theme_mode", val)
        mode_map = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}
        if app:
            app.theme_mode = mode_map.get(val, ft.ThemeMode.SYSTEM)
            app.page.theme_mode = app.theme_mode
            app._set_window_icon()
            app.page.update()

    async def add_library(e):
        from logic.file_dialog import pick_directory
        path = await pick_directory(page, title=tr("selectMusicLibraryFolder"))
        if path:
            import os
            name = os.path.basename(path)
            try:
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO watch_folders (path, name, recursive, is_active) VALUES (?, ?, 1, 1)",
                        (path, name),
                    )
                    conn.commit()
                trepo.scan_directory(path, recursive=True, callback=lambda: page.update())
            except Exception as ex:
                page.show_dialog(ft.SnackBar(ft.Text(f"Error: {ex}")))
            refresh()
            app = page.session.store.get("app")
            if app:
                app.refresh_watch_scanner()

    def scan_libraries(e):
        with db.get_connection() as conn:
            folders = conn.execute("SELECT * FROM watch_folders WHERE is_active=1").fetchall()
        if not folders:
            page.show_dialog(ft.SnackBar(ft.Text(tr("noActiveLibraries"))))
            page.update()
            return

        def do_scan():
            for f in folders:
                trepo.scan_directory(f["path"], recursive=True, callback=lambda: page.update())

        threading.Thread(target=do_scan, daemon=True).start()
        page.show_dialog(ft.SnackBar(ft.Text(tr("librariesScannedSuccessfully"))))
        page.update()

    def reset_database(e):
        """Show confirmation dialog for database reset."""
        def confirm_yes(e):
            trepo.clear_all_tracks()
            page.pop_dialog()
            page.show_dialog(ft.SnackBar(ft.Text(tr("trackDatabaseReset"))))
            refresh()

        def confirm_no(e):
            page.pop_dialog()
            refresh()

        dlg = ft.AlertDialog(
            title=ft.Text(tr("resetTrackDatabase")),
            content=ft.Text(tr("confirmResetTrackDatabase")),
            actions=[
                ft.TextButton(tr("cancel"), on_click=confirm_no),
                ft.FilledButton(tr("yes"), on_click=confirm_yes, bgcolor=ft.Colors.RED, color=ft.Colors.WHITE),
            ],
        )
        page.show_dialog(dlg)

    def repair_library(e):
        missing = trepo.get_missing_tracks()
        if not missing:
            page.show_dialog(ft.SnackBar(ft.Text(tr("noMissingTracks"))))
            page.update()
            return

        def confirm_yes(e):
            ids = [t.id for t in missing]
            trepo.delete_tracks(ids)
            page.pop_dialog()
            page.show_dialog(ft.SnackBar(ft.Text(tr("repairLibraryDone").format(len(ids)))))
            refresh()

        def confirm_no(e):
            page.pop_dialog()
            refresh()

        names = "\n".join(t.title or os.path.basename(t.path) for t in missing[:10])
        if len(missing) > 10:
            names += f"\n... (+{len(missing) - 10} more)"
        dlg = ft.AlertDialog(
            title=ft.Text(tr("repairLibrary")),
            content=ft.Text(tr("missingTracksFound").format(len(missing)) + "\n\n" + names),
            actions=[
                ft.TextButton(tr("cancel"), on_click=confirm_no),
                ft.FilledButton(tr("removeAllMissing"), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=confirm_yes),
            ],
        )
        page.show_dialog(dlg)

    with db.get_connection() as conn:
        folders = conn.execute("SELECT * FROM watch_folders ORDER BY added_at").fetchall()

    lib_tiles = []
    for f in folders:
        lib_tiles.append(
            ft.ListTile(
                title=ft.Text(f["name"]),
                subtitle=ft.Text(f["path"], size=11),
                trailing=ft.Row(
                    tight=True,
                    controls=[
                        ft.Switch(
                            value=bool(f["is_active"]),
                            on_change=lambda e, fid=f["id"]: _toggle_folder(fid, e.control.value),
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE,
                            on_click=lambda e, fid=f["id"]: _delete_folder(fid),
                        ),
                    ],
                ),
            )
        )

    def _toggle_folder(fid, active):
        with db.get_connection() as conn:
            conn.execute("UPDATE watch_folders SET is_active=? WHERE id=?", (int(active), fid))
            conn.commit()
        refresh()
        app = page.session.store.get("app")
        if app:
            app.refresh_watch_scanner()

    def _delete_folder(fid):
        with db.get_connection() as conn:
            conn.execute("DELETE FROM watch_folders WHERE id=?", (fid,))
            conn.commit()
        refresh()
        app = page.session.store.get("app")
        if app:
            app.refresh_watch_scanner()

    def _set_log_level(e):
        """Change the application log level."""
        lvl = e.control.value
        db.set_setting("log_level", lvl)
        from logic.logger import set_log_level
        set_log_level(lvl)
        refresh()

    async def export_logs(e):
        from logic.file_dialog import save_file
        from logic.logger import export_logs as _export_logs
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp_path = tmp.name
        tmp.close()
        try:
            _export_logs(tmp_path)
            with open(tmp_path, "rb") as f:
                log_bytes = f.read()
            saved = await save_file(page, title=tr("exportLogs"), default_name="groovybox_logs.txt",
                                   extensions=["txt"], src_bytes=log_bytes)
            if saved:
                page.show_dialog(ft.SnackBar(ft.Text(tr("logsExported", saved))))
                logger.info(f"Logs exported to {saved}")
        except Exception as ex:
            page.show_dialog(ft.SnackBar(ft.Text(tr("errorExportingLogs", str(ex)))))
            logger.error(f"Failed to export logs: {ex}")
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass

    # Build interactive hotkey rows for keyboard shortcuts section
    kd_widgets = {}

    def _build_hotkey_row(ak):
        kd = ft.Text(
            bindings.get(ak, DEFAULT_KEY_BINDINGS.get(ak, "?")),
            size=13, weight=ft.FontWeight.BOLD,
        )
        kd_widgets[ak] = kd

        def _on_click(e):
            if cap[0] is not None:
                return
            cap[0] = ak
            kd.value = "..."
            kd.update()

            def _on_capture(key):
                if cap[0] != ak:
                    return
                cap[0] = None
                page.session.store.set("__key_capture_callback", None)
                if key == "Escape":
                    kd.value = bindings.get(ak, DEFAULT_KEY_BINDINGS.get(ak, "?"))
                    kd.update()
                    return
                bindings[ak] = key
                db.set_setting("key_bindings", json.dumps(bindings, ensure_ascii=False))
                kd.value = key
                kd.update()
            page.session.store.set("__key_capture_callback", _on_capture)
        return ft.Container(
            content=ft.Row(
                tight=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(tr(ACTION_NAMES.get(ak, ak)), size=13, expand=True),
                    ft.Container(
                        on_click=_on_click,
                        padding=ft.Padding(12, 4, 12, 4),
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                        border_radius=6,
                        content=kd,
                    ),
                ],
            ),
            padding=ft.Padding(0, 3, 0, 3),
        )

    def _reset_key_bindings(e):
        bindings.clear()
        bindings.update(DEFAULT_KEY_BINDINGS)
        db.set_setting("key_bindings", json.dumps(bindings, ensure_ascii=False))
        for ak, kd in kd_widgets.items():
            kd.value = bindings[ak]
        page.update()

    bindings = dict(DEFAULT_KEY_BINDINGS)
    raw = db.get_setting("key_bindings", "")
    if raw:
        try:
            bindings.update(json.loads(raw))
        except:
            pass
    cap = [None]
    hotkey_rows = [_build_hotkey_row(ak) for ak in ACTION_ORDER]

    # Build the settings content
    content = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=8,
        controls=[
            # Auto Scan Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(tr("autoScan"), size=18, weight=ft.FontWeight.BOLD),
                        ft.Switch(
                            label=tr("autoScanMusicLibraries"),
                            value=settings["auto_scan"],
                            on_change=on_auto_scan_change,
                        ),
                    ],
                ),
            ),

            # Music Libraries Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            tight=True,
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(tr("musicLibraries"), size=18, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    tight=True,
                                    controls=[
                                        ft.IconButton(ft.Icons.REFRESH, tooltip=tr("scanLibraries"), on_click=scan_libraries),
                                        ft.IconButton(ft.Icons.ADD, tooltip=tr("addMusicLibrary"), on_click=add_library),
                                    ],
                                ),
                            ],
                        ),
                        ft.Text(tr("addMusicLibraryDescription"), size=12, color=ft.Colors.GREY),
                        *(lib_tiles if lib_tiles else [ft.Text(tr("noMusicLibrariesAdded"), color=ft.Colors.GREY)]),
                    ],
                ),
            ),

            # Player Settings Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(tr("playerSettings"), size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(tr("playerSettingsDescription"), size=12, color=ft.Colors.GREY),
                        ft.ListTile(
                            title=ft.Text(tr("defaultPlayerScreen")),
                            trailing=ft.Dropdown(
                                value=settings["default_player_screen"],
                                options=[
                                    ft.dropdown.Option("cover", tr("showCover")),
                                    ft.dropdown.Option("lyrics", tr("showLyrics")),
                                    ft.dropdown.Option("queue", tr("showQueue")),
                                ],
                                on_select=on_default_screen_change,
                            ),
                        ),
                        ft.ListTile(
                        title=ft.Text(tr("lyricsMode")),
                        trailing=ft.Dropdown(
                            value=settings["lyrics_mode"],
                            options=[
                                ft.dropdown.Option("auto", tr("lyricsModeAuto")),
                                ft.dropdown.Option("curved", tr("lyricsModeCurved")),
                                ft.dropdown.Option("flat", tr("lyricsModeFlat")),
                            ],
                            on_select=on_lyrics_mode_change,
                            ),
                        ),
                        ft.Switch(
                            label=tr("continuePlaying"),
                            value=settings["continue_plays"],
                            on_change=on_continue_plays_change,
                        ),
                        ft.Divider(height=1),
                        ft.Text(tr("blurBackground"), size=14, weight=ft.FontWeight.BOLD),
                        ft.Switch(
                            label=tr("blurBackground"),
                            value=db.get_setting("blur_background", "true") == "true",
                            on_change=lambda e: save_setting("blur_background", e.control.value),
                        ),
                        ft.Row(
                            tight=True,
                            controls=[
                                ft.Text(tr("blurIntensity"), size=13),
                                ft.Container(expand=True),
                                ft.Slider(
                                    value=int(db.get_setting("blur_intensity", "30")),
                                    min=1, max=100, divisions=99,
                                    expand=True,
                                    on_change=lambda e: save_setting("blur_intensity", str(int(e.control.value))),
                                ),
                            ],
                        ),
                    ],
                ),
            ),

            # App Settings Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(tr("appSettings"), size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(tr("appSettingsDescription"), size=12, color=ft.Colors.GREY),
                        ft.ListTile(
                            title=ft.Text(tr("language")),
                            trailing=ft.Dropdown(
                                value=get_locale(),
                                options=[
                                    ft.dropdown.Option("en", tr("english")),
                                    ft.dropdown.Option("zh", tr("chinese")),
                                ],
                                on_select=on_language_change,
                            ),
                        ),
                        ft.ListTile(
                            title=ft.Text(tr("themeMode")),
                            trailing=ft.Dropdown(
                                value=settings["theme_mode"],
                                options=[
                                    ft.dropdown.Option("system", tr("themeSystem")),
                                    ft.dropdown.Option("light", tr("themeLight")),
                                    ft.dropdown.Option("dark", tr("themeDark")),
                                ],
                                on_select=on_theme_mode_change,
                            ),
                        ),
                        ft.Divider(height=1),
                        ft.Text(tr("globalBackground"), size=14, weight=ft.FontWeight.BOLD),
                        ft.Switch(
                            label=tr("hideGlobalBg"),
                            value=db.get_setting("global_bg_hidden", "false") == "true",
                            on_change=lambda e: (save_setting("global_bg_hidden", e.control.value), page.session.store.get("app") and page.session.store.get("app")._reload_ui()),
                        ),
                        _build_global_bg_ui(),
                        ft.Column(
                            visible=page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX, ft.PagePlatform.MACOS),
                            controls=[
                                ft.Divider(height=1),
                                ft.Text(tr("closeBehavior"), size=14, weight=ft.FontWeight.BOLD),
                                ft.RadioGroup(
                                    content=ft.Column([
                                        ft.Radio(value="hide", label=tr("closeBehaviorHide")),
                                        ft.Radio(value="exit", label=tr("closeBehaviorExit")),
                                    ]),
                                    value="hide" if db.get_setting("close_behavior", "hide") not in ("hide", "exit") else db.get_setting("close_behavior", "hide"),
                                    on_change=lambda e: save_setting("close_behavior", e.control.value),
                                ),
                            ],
                        ),
                    ],
                ),
            ),

            # Database Management Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(tr("databaseManagement"), size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(tr("databaseManagementDescription"), size=12, color=ft.Colors.GREY),
                        ft.ListTile(
                            title=ft.Text(tr("repairLibrary")),
                            subtitle=ft.Text(tr("repairLibraryDescription"), size=11, color=ft.Colors.GREY),
                            trailing=ft.FilledButton(
                                tr("repairLibrary"),
                                on_click=repair_library,
                            ),
                        ),
                        ft.ListTile(
                            title=ft.Text(tr("resetTrackDatabase")),
                            trailing=ft.FilledButton(
                                tr("reset"),
                                color=ft.Colors.RED,
                                on_click=reset_database,
                            ),
                        ),
                    ],
                ),
            ),
            # Logs Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(tr("logs"), size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(tr("logsDescription"), size=12, color=ft.Colors.GREY),
                        ft.ListTile(
                            title=ft.Text(tr("logLevel")),
                            subtitle=ft.Text(tr("logLevelDescription"), size=11, color=ft.Colors.GREY),
                            trailing=ft.Dropdown(
                                value=db.get_setting("log_level", "normal"),
                                options=[
                                    ft.dropdown.Option("normal", tr("logLevelNormal")),
                                    ft.dropdown.Option("errors_only", tr("logLevelErrorsOnly")),
                                    ft.dropdown.Option("errors_warnings", tr("logLevelErrorsWarnings")),
                                    ft.dropdown.Option("verbose", tr("logLevelVerbose")),
                                ],
                                on_select=lambda e: _set_log_level(e),
                            ),
                        ),
                        ft.ListTile(
                            title=ft.Text(tr("exportLogs")),
                            trailing=ft.FilledButton(
                                tr("exportLogs"),
                                on_click=export_logs,
                            ),
                        ),
                    ],
                ),
            ),
            # Keyboard Shortcuts Section (desktop layout only)
            ft.Container(
                visible=page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX, ft.PagePlatform.MACOS),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            tight=True,
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(tr("keyboardShortcuts"), size=18, weight=ft.FontWeight.BOLD),
                                ft.IconButton(ft.Icons.RESTART_ALT, tooltip=tr("reset"), on_click=_reset_key_bindings),
                            ],
                        ),
                        ft.Container(height=4),
                        *hotkey_rows,
                        ft.Container(height=4),
                        ft.Text(tr("keyboardShortcutsNote"),
                            size=11, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                    ],
                ),
            ),
            # About Section
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=12,
                padding=16,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(tr("appName"), size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"v{_build_version}", size=14, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                        ft.Text(f"Build {_build_number}", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                        ft.Container(height=8),
                        ft.Text("GNU General Public License v3.0", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                        ft.Text("Copyright \u00A9 2026 luolingy", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                        ft.Container(height=8),
                        ft.Divider(height=1),
                        ft.Container(height=4),
                        ft.TextButton(
                            icon=ft.Icons.DESCRIPTION,
                            content=ft.Text(tr("useagreement"), size=13, weight=ft.FontWeight.W_500),
                            url="https://agreement.luolingy.qzz.io/agreement/os-app-use-agreement",
                        ),
                        ft.TextButton(
                            icon=ft.Icons.CODE,
                            content=ft.Text(tr("openSourceRepo"), size=13, weight=ft.FontWeight.W_500),
                            url="https://github.com/luolingy/groovybox",
                        ),
                        ft.TextButton(
                            icon=ft.Icons.BUG_REPORT,
                            content=ft.Text(tr("feedback"), size=13, weight=ft.FontWeight.W_500),
                            url="https://github.com/luolingy/groovybox/issues",
                        ),
                        ft.Container(height=4),
                        ft.Divider(height=1),
                        ft.Container(height=8),
                        ft.Row(
                            tight=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Text("Contributors: ", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                                ft.TextButton("luolingy", url="https://github.com/luolingy"),
								ft.TextButton("ZhiH", url="https://github.com/ZhiH2333"),
								ft.TextButton("符跃 万界(logo)", url="https://qm.qq.com/q/vMovFQlrj2"),
                            ],
                        ),
                    ],
                ),
            ),
            ft.Container(height=80),
        ],
    )

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[ft.Container(
            expand=True,
            padding=16,
            alignment=ft.Alignment(0, -1),
            content=ft.Container(
                width=min(640, page.width - 32) if page.width else 640,
                content=content,
            ),
        )],
    )
