"""Build Script for GroovyBox.

This module handles building the GroovyBox application for various
platforms (Windows, Android, iOS) using the Flet build system.
Reads configuration from build-config.json and handles platform-specific
options like Android signing and iOS provisioning.
"""

import json, subprocess, sys, os, shutil

DESKTOP_PLATFORMS = ("windows", "linux", "macos")
EXTRA_DESKTOP_DEPS = "# desktop-only dependencies\npystray>=0.19.0\n"
MOBILE_PLATFORMS = ("android", "ios", "apk", "aab", "ipa")


def ensure_desktop_deps(plat: str):
    """Inject desktop-only dependencies into requirements.txt for desktop builds."""
    if plat not in DESKTOP_PLATFORMS:
        return
    req = "requirements.txt"
    with open(req, encoding="utf-8") as f:
        content = f.read()
    if "pystray" not in content:
        with open(req, "a", encoding="utf-8") as f:
            f.write(f"\n{EXTRA_DESKTOP_DEPS}")
        print(f"Injected desktop dependencies into {req}")


def ensure_mobile_deps(plat: str):
    """Remove mobile-problematic dependencies for mobile builds.
    
    watchdog>=3.0.0 often has no prebuilt wheels for Android/iOS CI runners,
    causing pip install failures. Since watch_scanner.py already handles
    missing watchdog gracefully, we can safely skip it on mobile.
    
    pystray is a desktop-only system tray library that imports X11/AppKit
    backends at module load time, causing runtime crashes on Android/iOS.
    tray_manager.py already handles missing pystray gracefully.
    """
    if plat not in MOBILE_PLATFORMS:
        return
    req = "requirements.txt"
    with open(req, encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    removed = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("watchdog") or stripped.startswith("pystray"):
            removed.append(stripped)
            continue
        new_lines.append(line)
    
    if removed:
        with open(req, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Removed mobile-problematic dependencies from {req} for mobile build: {', '.join(removed)}")


def load_config():
    """Load the build configuration from build-config.json.
    
    Returns:
        Dictionary containing build configuration.
    """
    with open("build-config.json", encoding="utf-8") as f:
        return json.load(f)


def copy_icons():
    """Copy icon files to the assets root directory.
    
    Ensures icon.ico and icon.png are available at the assets root
    for the build system, copying from the images subdirectory if needed.
    """
    src_ico = os.path.join("assets", "images", "icon.ico")
    src_png = os.path.join("assets", "images", "icon.png")
    dst_ico = os.path.join("assets", "icon.ico")
    dst_png = os.path.join("assets", "icon.png")
    if os.path.exists(src_ico) and not os.path.exists(dst_ico):
        shutil.copy2(src_ico, dst_ico)
        print(f"Copied {src_ico} -> {dst_ico}")
    if os.path.exists(src_png) and not os.path.exists(dst_png):
        shutil.copy2(src_png, dst_png)
        print(f"Copied {src_png} -> {dst_png}")


def build_cmd(platform: str):
    """Build the Flet build command for the specified platform.
    
    Constructs the full command line with all necessary parameters
    from the build configuration, including platform-specific options
    for Android and iOS.
    
    Args:
        platform: Target platform (windows, linux, macos, android, ios, apk, aab, ipa, web, etc.)
    
    Returns:
        List of command arguments for subprocess.run.
    """
    # Map CI-friendly platform names to flet build targets
    PLATFORM_ALIASES = {
        "android": "apk",
        "ios": "ipa",
    }
    platform = PLATFORM_ALIASES.get(platform, platform)
    
    cfg = load_config()
    app = cfg["app"]
    android = cfg.get("android", {})

    # Base command with common options
    cmd = [
        "flet", "build", platform,
        "--yes", "--no-rich-output", "--skip-flutter-doctor",
        "--project", app["project"],
        "--product", app["product"],
        "--description", app["description"],
        "--org", app["org"],
        "--bundle-id", app["bundle_id"],
        "--build-version", app["build_version"],
        "--build-number", str(app["build_number"]),
        "--module-name", app["module_name"],
    ]
    if app.get("company"):
        cmd += ["--company", app["company"]]
    if app.get("copyright"):
        cmd += ["--copyright", app["copyright"]]

    # Android-specific options
    if platform in ("apk", "aab"):
        for perm in android.get("permissions", []):
            cmd += ["--android-permissions", f"{perm}=true"]
        bg = android.get("adaptive_icon_background")
        if bg:
            cmd += ["--android-adaptive-icon-background", bg]
        
        # Android signing configuration (from environment variables)
        ks = "keystore.jks"
        ks_pass = os.environ.get("ANDROID_KEYSTORE_PASSWORD", "")
        key_pass = os.environ.get("ANDROID_KEY_PASSWORD", "")
        key_alias = os.environ.get("ANDROID_KEY_ALIAS", "")
        if os.path.exists(ks) and os.path.getsize(ks) > 100 and ks_pass and key_alias:
            cmd += [
                "--android-signing-key-store", os.path.abspath(ks),
                "--android-signing-key-store-password", ks_pass,
                "--android-signing-key-password", key_pass or ks_pass,
                "--android-signing-key-alias", key_alias,
            ]

    # iOS-specific options
    if platform == "ipa":
        ios_cfg = cfg.get("ios", {})
        for key, val in ios_cfg.get("info_plist", {}).items():
            if isinstance(val, list):
                cmd += ["--info-plist", f"{key}={json.dumps(val)}"]
            elif isinstance(val, bool):
                cmd += ["--info-plist", f"{key}={ 'true' if val else 'false'}"]
            else:
                cmd += ["--info-plist", f"{key}={val}"]
        
        # iOS signing configuration (optional; only added when environment variables are present)
        # In the release workflow, signing is disabled by default. To enable, set:
        #   - IOS_TEAM_ID
        #   - IOS_SIGNING_CERTIFICATE (e.g. "Apple Distribution")
        #   - IOS_PROVISIONING_PROFILE_NAME
        # and uncomment the signing steps in .github/workflows/release.yml.
        team_id = os.environ.get("IOS_TEAM_ID", "")
        cert = os.environ.get("IOS_SIGNING_CERTIFICATE", "")
        profile = os.environ.get("IOS_PROVISIONING_PROFILE_NAME", "")
        if team_id:
            cmd += ["--ios-team-id", team_id]
        if cert:
            cmd += ["--ios-signing-certificate", cert]
        if profile:
            cmd += ["--ios-provisioning-profile", profile]

    return cmd


if __name__ == "__main__":
    # Determine target platform from arguments or environment
    platform = sys.argv[1] if len(sys.argv) > 1 else "windows"
    plat = os.environ.get("TARGET_PLATFORM", platform)
    copy_icons()
    ensure_desktop_deps(plat)
    ensure_mobile_deps(plat)
    cmd = build_cmd(plat)
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
