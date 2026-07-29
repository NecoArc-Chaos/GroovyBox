"""Localization Module for GroovyBox.

This module handles internationalization (i18n) by loading locale-specific
string translations from JSON files. Supports dynamic language switching
and string interpolation with placeholder arguments.
"""

import json
import os

# Current locale code (e.g., "en", "zh")
_locale = "en"

# Loaded translation strings dictionary
_strings: dict = {}


def load_locale(lang: str):
    """Load translation strings for the specified language.

    Reads the JSON locale file from the assets/locales directory.
    Falls back to an empty dictionary if the file doesn't exist.

    Args:
        lang: Language code (e.g., "en", "zh").
    """
    global _locale, _strings
    _locale = lang
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "locales", f"{lang}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _strings = json.load(f)
    except FileNotFoundError:
        _strings = {}


def tr(key: str, *args) -> str:
    """Translate a string key to the current locale.

    Supports placeholder substitution using {} syntax. If the key
    is not found in the translations, the key itself is returned.

    Args:
        key: The translation key to look up.
        *args: Values to substitute into {} placeholders.

    Returns:
        The translated string with placeholders filled.

    Example:
        tr("importedTracks", 5) -> "Imported 5 tracks"
    """
    val = _strings.get(key, key)
    if args:
        for a in args:
            val = val.replace("{}", str(a), 1)
    return val


def get_locale() -> str:
    """Get the current locale code.

    Returns:
        The current language code string (e.g., "en").
    """
    return _locale
