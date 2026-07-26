# Build Configuration Reference

This document describes the `build-config.json` file used by GroovyBox
for cross-platform builds.

## Top-Level Structure

```json
{
  "app": { ... },
  "android": { ... },
  "ios": { ... },
  "build": { ... }
}
```

## `app` Section

| Key | Type | Description |
|-----|------|-------------|
| `project` | string | Internal project identifier (lowercase, no spaces) |
| `product` | string | Human-readable application name |
| `description` | string | Short description shown in installers |
| `org` | string | Reverse-domain organization identifier (e.g., `io.qzz.luolingy`) |
| `bundle_id` | string | Full bundle/package identifier (e.g., `io.qzz.luolingy.groovybox`) |
| `company` | string | Optional company name for Windows/macOS builds |
| `copyright` | string | Optional copyright string |
| `build_version` | string | Semantic version string (e.g., `1.0.0`) |
| `build_number` | integer | Incremental build number |
| `module_name` | string | Python module name containing the entry point (`main` for `main.py`) |

## `android` Section

| Key | Type | Description |
|-----|------|-------------|
| `permissions` | array of strings | Android permissions to request (e.g., `READ_MEDIA_AUDIO`) |
| `target_sdk_version` | integer | Android target SDK version (e.g., `33`) |
| `adaptive_icon_background` | string | Hex color for adaptive icon background |

## `ios` Section

| Key | Type | Description |
|-----|------|-------------|
| `info_plist` | object | Key-value pairs merged into `Info.plist`. Supports nested arrays and booleans |

### Supported `info_plist` Keys

- `NSAppleMusicUsageDescription`: String explaining media library access
- `NSDocumentsFolderUsageDescription`: String explaining file import access
- `UIBackgroundModes`: Array of background mode identifiers (e.g., `["audio", "fetch"]`)
- `BGTaskSchedulerPermittedIdentifiers`: Array of background task identifiers

## `build` Section

| Key | Type | Description |
|-----|------|-------------|
| `flet_version` | string | Flet CLI version used for building |
| `python_version` | string | Python version constraint (e.g., `3.12`) |
| `timeout_minutes` | integer | Build timeout for CI workflows |
| `default_platforms` | array of strings | Default platforms for CI dispatch (e.g., `["windows", "linux", "macos", "android", "ios"]`) |

## Example

```json
{
  "app": {
    "project": "groovybox",
    "product": "GroovyBox",
    "description": "A modern music player built with Flet",
    "org": "io.qzz.luolingy",
    "bundle_id": "io.qzz.luolingy.groovybox",
    "build_version": "1.0.0",
    "build_number": 5,
    "module_name": "main"
  },
  "android": {
    "permissions": [
      "READ_MEDIA_AUDIO",
      "READ_EXTERNAL_STORAGE",
      "WRITE_EXTERNAL_STORAGE"
    ],
    "target_sdk_version": 33,
    "adaptive_icon_background": "#1e1e2e"
  },
  "ios": {
    "info_plist": {
      "NSAppleMusicUsageDescription": "GroovyBox needs access to your music library to play songs.",
      "NSDocumentsFolderUsageDescription": "GroovyBox needs access to import music files from your documents.",
      "UIBackgroundModes": ["audio", "fetch"],
      "BGTaskSchedulerPermittedIdentifiers": ["$(PRODUCT_BUNDLE_IDENTIFIER)"]
    }
  },
  "build": {
    "flet_version": "0.85.3",
    "python_version": "3.12",
    "timeout_minutes": 60,
    "default_platforms": ["windows", "linux", "macos", "android", "ios"]
  }
}
```
