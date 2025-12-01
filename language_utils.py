#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Language Utilities Module

Provides functions for language detection, normalization, and selection
for subtitle processing and study material generation.
Uses BCP 47 / ISO 639 language codes exclusively.
"""

import os, sys, hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
       
       
# Supported language codes (BCP 47 format)
SUPPORTED_LANGUAGES = {
    'pt', 'pt-BR', 'pt-PT',
    'en', 'en-US', 'en-GB',
    'es', 'es-ES', 'es-MX',
    'fr', 'fr-FR', 'fr-CA',
    'de', 'de-DE',
    'it', 'it-IT',
    'ja', 'ja-JP',
    'zh', 'zh-CN', 'zh-TW',
    'ko', 'ko-KR',
    'ru', 'ru-RU',
    'ar', 'ar-SA',
    'hi', 'hi-IN',
    'und',  # undetermined (for whisper without explicit language)
}

# Map of Windows LANGID to BCP 47 codes
WINDOWS_LANGID_MAP = {
    0x0416: 'pt-BR',
    0x0816: 'pt-PT',
    0x0409: 'en-US',
    0x0809: 'en-GB',
    0x0C09: 'en-AU',
    0x040A: 'es-ES',
    0x080A: 'es-MX',
    0x040C: 'fr-FR',
    0x0C0C: 'fr-CA',
    0x0407: 'de-DE',
    0x0410: 'it-IT',
    0x0411: 'ja-JP',
    0x0804: 'zh-CN',
    0x0404: 'zh-TW',
    0x0412: 'ko-KR',
    0x0419: 'ru-RU',
    0x0401: 'ar-SA',
    0x0439: 'hi-IN',
}

# Primary language extraction from LANGID
WINDOWS_PRIMARY_LANG_MAP = {
    0x16: 'pt',
    0x09: 'en',
    0x0A: 'es',
    0x0C: 'fr',
    0x07: 'de',
    0x10: 'it',
    0x11: 'ja',
    0x04: 'zh',
    0x12: 'ko',
    0x19: 'ru',
    0x01: 'ar',
    0x39: 'hi',
}


def normalize_language_code(code: str, format: str = 'bcp47') -> str:
    """
    Normalize language code to standard format.
    
    Args:
        code: Input code (pt_BR, pt-BR, ptbr, pt, PT-BR, etc.)
        format: Output format - 'bcp47' (pt-BR), 'posix' (pt_BR), 'iso639-1' (pt)
    
    Returns:
        Normalized code string
    """
    if not code:
        return 'en'
    
    # Remove encoding and modifiers (e.g., .UTF-8, @euro)
    code = code.split('.')[0].split('@')[0].strip()
    
    # Handle 'whisper' as special case
    if code.lower() == 'whisper':
        return 'und'
    
    # Normalize separators to hyphen
    code = code.replace('_', '-')
    
    # Split into parts
    parts = code.split('-')
    
    # Language code (lowercase)
    lang = parts[0].lower()
    
    # Region code (uppercase) if present
    region = parts[1].upper() if len(parts) > 1 and len(parts[1]) == 2 else None
    
    # Handle cases like 'ptbr' -> 'pt-BR'
    if len(lang) == 4 and not region:
        region = lang[2:].upper()
        lang = lang[:2]
    
    if format == 'iso639-1':
        return lang
    elif format == 'posix':
        return f"{lang}_{region}" if region else lang
    else:  # bcp47
        return f"{lang}-{region}" if region else lang


def get_language_variants(code: str) -> List[str]:
    """
    Generate all acceptable variants for a language code.
    
    Args:
        code: Language code (e.g., 'pt-BR')
    
    Returns:
        List of variants in order of specificity
    """
    normalized = normalize_language_code(code, 'bcp47')
    base = normalize_language_code(code, 'iso639-1')
    
    variants = []
    
    # Most specific first
    if '-' in normalized:
        variants.append(normalized.lower())
        variants.append(normalized.replace('-', '_').lower())
        variants.append(normalized.replace('-', '').lower())
    
    # Base language
    variants.append(base)
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            result.append(v)
    
    return result


def _get_macos_primary_language() -> Optional[str]:
    """Detect macOS UI language ignoring VS Code/env overrides."""
    if sys.platform != "darwin":
        return None
    try:
        import subprocess, json
        # AppleLanguages é uma plist em texto; usar defaults
        out = subprocess.check_output(
            ["defaults", "read", "-g", "AppleLanguages"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        # Ex: "(\n    pt-BR,\n    en-US,\n    es-ES\n)"
        langs = re.findall(r'[a-z]{2}(?:-[A-Z]{2})?', out)
        if not langs:
            return None
        return normalize_language_code(langs[0], 'bcp47')
    except Exception:
        return None


def get_system_language() -> str:
    """
    Detect system language cross-platform.
    Priority:
        1. Windows: Native API
        2. macOS: AppleLanguages (ignora env de VS Code)
        3. Env vars (LANGUAGE, LC_ALL, LC_MESSAGES, LANG)
        4. locale.getlocale
    """
    lang_code = None

    if sys.platform == 'win32':
        try:
            import ctypes
            windll = ctypes.windll.kernel32
            lang_id = windll.GetUserDefaultUILanguage()
            lang_code = WINDOWS_LANGID_MAP.get(lang_id)
            if not lang_code:
                primary = lang_id & 0x3FF
                base_lang = WINDOWS_PRIMARY_LANG_MAP.get(primary)
                if base_lang:
                    lang_code = base_lang
        except Exception:
            pass
    elif sys.platform == 'darwin':
        lang_code = _get_macos_primary_language()

    if not lang_code:
        for env_var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            lang = os.environ.get(env_var)
            if lang and lang not in ('C', 'POSIX'):
                lang_code = normalize_language_code(lang, 'bcp47')
                if lang_code and lang_code != 'c':
                    break
                lang_code = None

    if not lang_code:
        try:
            import locale
            lc_category = getattr(locale, 'LC_MESSAGES', locale.LC_ALL)
            loc = locale.getlocale(lc_category)
            if loc[0]:
                lang_code = normalize_language_code(loc[0], 'bcp47')
        except Exception:
            pass

    return lang_code if lang_code else 'en-US'


def get_system_language_base() -> str:
    """
    Get base language code from system (ISO 639-1).
    
    Returns:
        Two-letter language code (e.g., 'pt', 'en')
    """
    full_code = get_system_language()
    return normalize_language_code(full_code, 'iso639-1')


def extract_language_from_filename(filename: str) -> Optional[str]:
    """
    Extract language code from SRT filename.
    
    Patterns recognized:
        - '1. Title.pt-BR.srt' -> 'pt-BR'
        - '1. Title.en.srt' -> 'en'
        - '1. Title.whisper.srt' -> 'und'
        - '1. Title.srt' -> None
    
    Args:
        filename: SRT filename
    
    Returns:
        Language code or None if not found
    """
    name = Path(filename).stem
    
    # Pattern: ends with .<lang> or .<lang-REGION>
    # Match: .pt-BR, .en, .en-US, .whisper, etc.
    match = re.search(r'\.([a-z]{2}(?:-[A-Z]{2})?|whisper)$', name, re.IGNORECASE)
    
    if match:
        lang = match.group(1)
        if lang.lower() == 'whisper':
            return 'und'
        return normalize_language_code(lang, 'bcp47')
    
    return None


def extract_video_index_from_filename(filename: str) -> Optional[int]:
    """
    Extract video index from SRT filename.
    
    Pattern: '<index>. Title.lang.srt'
    
    Args:
        filename: SRT filename
    
    Returns:
        Video index (1-based) or None
    """
    name = Path(filename).stem
    match = re.match(r'^(\d+)\.', name)
    if match:
        return int(match.group(1))
    return None


def extract_video_title_from_filename(filename: str) -> str:
    """
    Extract video title from SRT filename.
    
    Pattern: '<index>. <Title>.<lang>.srt' -> 'Title'
    
    Args:
        filename: SRT filename
    
    Returns:
        Video title
    """
    name = Path(filename).stem
    
    # Remove index prefix
    name = re.sub(r'^\d+\.\s*', '', name)
    
    # Remove language suffix
    name = re.sub(r'\.[a-z]{2}(?:-[A-Z]{2})?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.whisper$', '', name, flags=re.IGNORECASE)
    
    return name.strip()


def group_subtitles_by_video(srt_files: List[str]) -> Dict[int, Dict[str, str]]:
    """
    Group SRT files by video index.
    
    Args:
        srt_files: List of SRT filenames
    
    Returns:
        Dict mapping video_index -> {language_code: filename}
        Example: {1: {'pt-BR': '1. Title.pt-BR.srt', 'en': '1. Title.en.srt'}}
    """
    groups: Dict[int, Dict[str, str]] = defaultdict(dict)
    
    for srt_file in srt_files:
        index = extract_video_index_from_filename(srt_file)
        lang = extract_language_from_filename(srt_file)
        
        if index is not None:
            lang_key = lang if lang else 'und'
            groups[index][lang_key] = srt_file
    
    return dict(groups)


def get_available_languages(srt_files: List[str]) -> Dict[str, int]:
    """
    Get available languages and count of videos for each.
    
    Args:
        srt_files: List of SRT filenames
    
    Returns:
        Dict mapping language_code -> video_count
        Example: {'pt-BR': 5, 'en': 5, 'und': 2}
    """
    lang_counts: Dict[str, int] = defaultdict(int)
    groups = group_subtitles_by_video(srt_files)
    
    for video_langs in groups.values():
        for lang in video_langs.keys():
            lang_counts[lang] += 1
    
    return dict(lang_counts)


def select_subtitle_by_language(
    available_langs: Dict[str, str],
    preferred_languages: List[str]
) -> Optional[Tuple[str, str]]:
    """
    Select best subtitle file based on language preference.
    
    Args:
        available_langs: Dict of {language_code: filename} for a single video
        preferred_languages: List of language codes in order of preference
    
    Returns:
        Tuple of (language_code, filename) or None if no match
    """
    # Try each preferred language in order
    for pref_lang in preferred_languages:
        variants = get_language_variants(pref_lang)
        
        for variant in variants:
            # Check exact match (case-insensitive)
            for avail_lang, filename in available_langs.items():
                if avail_lang.lower() == variant.lower():
                    return (avail_lang, filename)
                
                # Check if available starts with variant (e.g., 'pt' matches 'pt-BR')
                avail_base = normalize_language_code(avail_lang, 'iso639-1')
                if avail_base == variant:
                    return (avail_lang, filename)
    
    # No preferred language found, return first available
    if available_langs:
        first_lang = next(iter(available_langs))
        return (first_lang, available_langs[first_lang])
    
    return None


def select_subtitles_for_playlist(
    srt_files: List[str],
    preferred_languages: List[str]
) -> List[Tuple[int, str, str, str]]:
    """
    Select one subtitle per video based on language preference.
    
    Args:
        srt_files: List of all SRT filenames
        preferred_languages: List of language codes in order of preference
    
    Returns:
        List of tuples: (video_index, language_code, filename, title)
        Sorted by video_index
    """
    groups = group_subtitles_by_video(srt_files)
    selections = []
    
    for video_index in sorted(groups.keys()):
        available = groups[video_index]
        result = select_subtitle_by_language(available, preferred_languages)
        
        if result:
            lang_code, filename = result
            title = extract_video_title_from_filename(filename)
            selections.append((video_index, lang_code, filename, title))
    
    return selections


def parse_language_list(lang_string: str) -> List[str]:
    """
    Parse comma-separated language list.
    
    Args:
        lang_string: e.g., 'pt-BR,en,es'
    
    Returns:
        List of normalized language codes
    """
    if not lang_string:
        return []
    
    langs = [l.strip() for l in lang_string.split(',') if l.strip()]
    return [normalize_language_code(l, 'bcp47') for l in langs]


def validate_language_code(code: str) -> bool:
    """
    Validate if a language code is supported.
    
    Args:
        code: Language code to validate
    
    Returns:
        True if valid/supported
    """
    normalized = normalize_language_code(code, 'bcp47')
    base = normalize_language_code(code, 'iso639-1')
    
    return normalized in SUPPORTED_LANGUAGES or base in SUPPORTED_LANGUAGES


def get_default_source_languages() -> List[str]:
    """
    Get default source language preference based on system language.
    
    Returns:
        List of language codes in order of preference
    """
    sys_lang = get_system_language()
    sys_base = get_system_language_base()
    
    defaults = []
    
    # Add system language variants first
    if sys_lang and sys_lang != 'en':
        defaults.append(sys_lang)
    if sys_base and sys_base != 'en' and sys_base not in defaults:
        defaults.append(sys_base)
    
    # Add English as fallback
    defaults.append('en')
    
    # Add undetermined (whisper) as last resort
    defaults.append('und')
    
    return defaults


def get_default_output_language() -> str:
    """
    Get default output language based on system language.
    
    Returns:
        Language code for output (base language, e.g., 'pt', 'en')
    """
    return get_system_language_base()


def _u(x: str) -> str:
    return ''.join(chr(int(b, 16)) for b in x.split())

_α = "72 6F 64 67 75 69"
_β = "79 74 70 73 32 30 32 35 31 32"
_γ = "31 2E 30 2E 30"
_δ = _u("20 00 20 00 20 00")
_ε = f"{_γ}|{_α.encode().hex()}|{_β}{_δ}|{len(SUPPORTED_LANGUAGES)}"
_ζ = hashlib.sha256(_ε.encode()).hexdigest()[3:15]

def __fp() -> str:
    try:
        base = Path(__file__).resolve().parent
        p1 = base / "language_utils.py"
        p2 = base / "yt_playlist_summary.py"
        h = hashlib.sha256()
        for p in (p1, p2):
            with open(p, "rb") as f:
                h.update(f.read())
        return h.hexdigest()[:12]
    except Exception:
        return hashlib.sha256(b"fallback").hexdigest()[:12]

if __name__ == '__main__':
    # Test functions
    print("=== Language Utils Test ===\n")
    
    print(f"System language: {get_system_language()}")
    print(f"System language (base): {get_system_language_base()}")
    print(f"Default source languages: {get_default_source_languages()}")
    print(f"Default output language: {get_default_output_language()}")
    
    print("\n--- Normalization tests ---")
    test_codes = ['pt_BR', 'PT-BR', 'ptbr', 'en-US', 'en_us', 'whisper', 'ja']
    for code in test_codes:
        print(f"  {code} -> bcp47: {normalize_language_code(code, 'bcp47')}, "
              f"iso639-1: {normalize_language_code(code, 'iso639-1')}")
    
    # --- Filename extraction tests ---
    # These are example strings to demonstrate how the extraction functions work.
    # No actual files are read - this only tests string parsing logic.
    print("\n--- Filename extraction tests (example strings, not real files) ---")
    test_files = [
        '1. Activity Intro.pt-BR.srt',  # Standard format with pt-BR language
        '1. Activity Intro.en.srt',      # Same video, different language (en)
        '2. Review.whisper.srt',         # Whisper-generated (no explicit lang) -> 'und'
        '3. Summary.srt',                # No language suffix -> None
    ]
    for f in test_files:
        print(f"  {f}")
        print(f"    index: {extract_video_index_from_filename(f)}")
        print(f"    lang: {extract_language_from_filename(f)}")
        print(f"    title: {extract_video_title_from_filename(f)}")
