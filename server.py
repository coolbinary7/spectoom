#!/usr/bin/env python3
"""Spectoom - dependency-light local web application.

The app uses Python's standard library plus Pillow, Mutagen and FFmpeg. It provides:
- signed-in local user/admin accounts and autosaved projects
- playlist-entry, new-release and YouTube-spectrum video generators
- shared preview/render composition and background render tracking
- user fonts, branding assets and render history
- cover, audio and video-to-audio conversion, individually or in ZIP batches
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import struct
import subprocess
import threading
import time
import traceback
import urllib.parse
import uuid
import wave
import zipfile
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

try:
    import imageio_ffmpeg
except Exception:  # Optional fallback when a system FFmpeg is already installed.
    imageio_ffmpeg = None

try:
    from mutagen import File as MutagenFile
except Exception:  # Audio probing can still fall back to FFmpeg.
    MutagenFile = None

def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("SPECTOOM_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
RENDER_DIR = DATA_DIR / "renders"
CONVERSION_DIR = DATA_DIR / "conversions"
TMP_DIR = DATA_DIR / "tmp"
PREVIEW_DIR = TMP_DIR / "previews"
CONVERSION_TMP_DIR = TMP_DIR / "conversions"
STORE_PATH = DATA_DIR / "store.json"
APP_NAME = "Spectoom"
APP_VERSION = "2.2.2-cloud"
RENDERER_VERSION = "v2.2.0-shared-spectrum"
ENVIRONMENT = os.environ.get("SPECTOOM_ENV", "local").strip().lower() or "local"
IS_PRODUCTION = ENVIRONMENT in {"production", "prod", "cloud"}
COOKIE_NAME = os.environ.get("SPECTOOM_COOKIE_NAME", "spectoom_session").strip() or "spectoom_session"
SECURE_COOKIES = env_flag("SPECTOOM_SECURE_COOKIES", IS_PRODUCTION)

for folder in (STATIC_DIR, DATA_DIR, UPLOAD_DIR, RENDER_DIR, CONVERSION_DIR, TMP_DIR, PREVIEW_DIR, CONVERSION_TMP_DIR, STATIC_DIR / "demo", STATIC_DIR / "platforms", STATIC_DIR / "brand"):
    folder.mkdir(parents=True, exist_ok=True)

STORE_LOCK = threading.RLock()
PREVIEW_LOCK = threading.RLock()
SESSIONS: dict[str, dict[str, Any]] = {}
SESSION_LOCK = threading.RLock()
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_LOCK = threading.RLock()
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_MAX_FAILURES = 10

MAX_JSON_BODY = 4 * 1024 * 1024
MAX_UPLOAD_BODY = 260 * 1024 * 1024
MAX_CONVERSION_BODY = 520 * 1024 * 1024
SESSION_TTL_SECONDS = 12 * 60 * 60

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
LOGO_EXTS = {".svg", ".png", ".webp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
FONT_EXTS = {".ttf", ".otf"}
CONVERT_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
CONVERT_AUDIO_EXTS = {
    ".aa", ".aac", ".aax", ".ac3", ".adx", ".aif", ".aiff", ".alac",
    ".amr", ".ape", ".ast", ".at3", ".au", ".caf", ".dff", ".dsf",
    ".dts", ".eac3", ".flac", ".gsm", ".hca", ".m4a", ".m4b", ".mka",
    ".mp2", ".mp3", ".mpc", ".oga", ".ogg", ".oma", ".opus", ".ra",
    ".ram", ".snd", ".spx", ".tak", ".tta", ".voc", ".wav", ".wave",
    ".wma", ".wv", ".xa", ".xma",
}
CONVERT_VIDEO_EXTS = VIDEO_EXTS

PROJECT_TYPES = {"playlist_entry", "new_release", "youtube_spectrum"}


class MediaToolUnavailable(RuntimeError):
    """Raised when the local media engine cannot be located."""


_FFMPEG_CACHE: tuple[str | None, str] | None = None
_FFPROBE_CACHE: tuple[str | None, str] | None = None


def _resolve_executable(value: str | None) -> str | None:
    """Resolve either an absolute executable path or a command in PATH."""
    if not value:
        return None
    expanded = os.path.expandvars(os.path.expanduser(value.strip().strip('"')))
    if not expanded:
        return None
    candidate = Path(expanded)
    if candidate.exists() and candidate.is_file():
        return str(candidate.resolve())
    found = shutil.which(expanded)
    return str(Path(found).resolve()) if found else None


def resolve_ffmpeg_binary(refresh: bool = False) -> tuple[str | None, str]:
    """Find FFmpeg in the environment, project, PATH or imageio-ffmpeg package."""
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE is not None and not refresh:
        return _FFMPEG_CACHE

    configured = _resolve_executable(os.environ.get("FFMPEG_BINARY"))
    if configured:
        _FFMPEG_CACHE = (configured, "FFMPEG_BINARY")
        return _FFMPEG_CACHE

    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    for candidate in (
        BASE_DIR / "tools" / executable_name,
        BASE_DIR / "bin" / executable_name,
        BASE_DIR / executable_name,
    ):
        if candidate.exists() and candidate.is_file():
            _FFMPEG_CACHE = (str(candidate.resolve()), "local")
            return _FFMPEG_CACHE

    system_binary = _resolve_executable("ffmpeg")
    if system_binary:
        _FFMPEG_CACHE = (system_binary, "PATH")
        return _FFMPEG_CACHE

    if imageio_ffmpeg is not None:
        try:
            bundled = _resolve_executable(imageio_ffmpeg.get_ffmpeg_exe())
            if bundled:
                _FFMPEG_CACHE = (bundled, "imageio-ffmpeg")
                return _FFMPEG_CACHE
        except Exception:
            pass

    _FFMPEG_CACHE = (None, "indisponible")
    return _FFMPEG_CACHE


def require_ffmpeg() -> str:
    binary, _source = resolve_ffmpeg_binary()
    if binary:
        return binary
    raise MediaToolUnavailable(
        "Le moteur audio/vidéo FFmpeg est indisponible. Relancez run.bat afin d’installer "
        "automatiquement les dépendances, puis réessayez."
    )


def resolve_ffprobe_binary(refresh: bool = False) -> tuple[str | None, str]:
    """Find FFprobe when available. It is optional since V1.1."""
    global _FFPROBE_CACHE
    if _FFPROBE_CACHE is not None and not refresh:
        return _FFPROBE_CACHE

    configured = _resolve_executable(os.environ.get("FFPROBE_BINARY"))
    if configured:
        _FFPROBE_CACHE = (configured, "FFPROBE_BINARY")
        return _FFPROBE_CACHE

    executable_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    for candidate in (
        BASE_DIR / "tools" / executable_name,
        BASE_DIR / "bin" / executable_name,
        BASE_DIR / executable_name,
    ):
        if candidate.exists() and candidate.is_file():
            _FFPROBE_CACHE = (str(candidate.resolve()), "local")
            return _FFPROBE_CACHE

    system_binary = _resolve_executable("ffprobe")
    if system_binary:
        _FFPROBE_CACHE = (system_binary, "PATH")
        return _FFPROBE_CACHE

    # A manually configured FFmpeg installation often keeps ffprobe beside ffmpeg.
    ffmpeg_binary, ffmpeg_source = resolve_ffmpeg_binary()
    if ffmpeg_binary and ffmpeg_source != "imageio-ffmpeg":
        sibling = Path(ffmpeg_binary).with_name(executable_name)
        if sibling.exists() and sibling.is_file():
            _FFPROBE_CACHE = (str(sibling.resolve()), "FFmpeg directory")
            return _FFPROBE_CACHE

    _FFPROBE_CACHE = (None, "indisponible")
    return _FFPROBE_CACHE


def resolve_font(*candidates: str) -> Path:
    """Return the first available system font without bundling font files."""
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    expanded = [
        *[Path(item) for item in candidates],
        windir / "Fonts" / "arial.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for candidate in expanded:
        if candidate.exists():
            return candidate
    # Pillow/fontconfig can often resolve this family name even when the path differs.
    return Path("DejaVuSans.ttf")


def resolve_bold_font() -> Path:
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        windir / "Fonts" / "arialbd.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path("DejaVuSans-Bold.ttf")


FONT_REGULAR = resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)
FONT_MEDIUM = FONT_REGULAR
FONT_BOLD = resolve_bold_font()
FONT_SERIF_REGULAR = resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
    str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "georgia.ttf"),
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
)
FONT_SERIF_BOLD = resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
    str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "georgiab.ttf"),
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
)
FONT_DISPLAY = resolve_font(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "impact.ttf"),
    "/System/Library/Fonts/Supplemental/Impact.ttf",
)

FONTS_DEFAULT = [
    {
        "id": "spectoom-sans",
        "name": "Spectoom Sans",
        "builtIn": True,
        "cssFamily": "Arial, Helvetica, sans-serif",
        "url": "",
        "preview": "Aa",
    },
    {
        "id": "editorial-serif",
        "name": "Editorial Serif",
        "builtIn": True,
        "cssFamily": "Georgia, 'Times New Roman', serif",
        "url": "",
        "preview": "Aa",
    },
    {
        "id": "display-impact",
        "name": "Display Impact",
        "builtIn": True,
        "cssFamily": "Impact, 'Arial Black', sans-serif",
        "url": "",
        "preview": "Aa",
    },
]

BUILTIN_FONT_PATHS: dict[str, tuple[Path, Path]] = {
    "spectoom-sans": (FONT_REGULAR, FONT_BOLD),
    "editorial-serif": (FONT_SERIF_REGULAR, FONT_SERIF_BOLD),
    "display-impact": (FONT_DISPLAY, FONT_DISPLAY),
}

PLATFORMS_DEFAULT = [
    {
        "id": "spotify", "name": "Spotify", "short": "SP", "active": True, "order": 1,
        "iconBlackUrl": "/static/platforms/spotify-black.png",
        "iconWhiteUrl": "/static/platforms/spotify-white.png",
    },
    {
        "id": "apple-music", "name": "Apple Music", "short": "AM", "active": True, "order": 2,
        "iconBlackUrl": "/static/platforms/apple-music-black.png",
        "iconWhiteUrl": "/static/platforms/apple-music-white.png",
    },
    {
        "id": "deezer", "name": "Deezer", "short": "DZ", "active": True, "order": 3,
        "iconBlackUrl": "/static/platforms/deezer-black.png",
        "iconWhiteUrl": "/static/platforms/deezer-white.png",
    },
    {
        "id": "youtube-music", "name": "YouTube Music", "short": "YT", "active": True, "order": 4,
        "iconBlackUrl": "/static/platforms/youtube-music-black.png",
        "iconWhiteUrl": "/static/platforms/youtube-music-white.png",
    },
    {
        "id": "boomplay", "name": "Boomplay", "short": "BP", "active": True, "order": 5,
        "iconBlackUrl": "/static/platforms/boomplay-black.png",
        "iconWhiteUrl": "/static/platforms/boomplay-white.png",
    },
    {
        "id": "audiomack", "name": "Audiomack", "short": "AU", "active": True, "order": 6,
        "iconBlackUrl": "/static/platforms/audiomack-black.png",
        "iconWhiteUrl": "/static/platforms/audiomack-white.png",
    },
]

PRESETS_DEFAULT = [
    {
        "id": "studio-rouge",
        "name": "Studio Rouge",
        "accent": "#ef233c",
        "secondary": "#111318",
        "tagline": "Entrées en playlist.",
        "overlay": 0.48,
    },
    {
        "id": "bleu-nuit",
        "name": "Bleu Nuit",
        "accent": "#55a7ff",
        "secondary": "#07101e",
        "tagline": "Nouvelles sélections.",
        "overlay": 0.52,
    },
    {
        "id": "ivoire",
        "name": "Ivoire éditorial",
        "accent": "#ffcf70",
        "secondary": "#17140e",
        "tagline": "En playlist cette semaine.",
        "overlay": 0.44,
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "projet"


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 220_000)
    return base64.b64encode(salt + digest).decode("ascii")


def password_verify(password: str, encoded: str) -> bool:
    raw = base64.b64decode(encoded.encode("ascii"))
    salt, expected = raw[:16], raw[16:]
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 220_000)
    return hmac.compare_digest(actual, expected)


def default_project(owner_id: str, name: str = "Nouveau projet", project_type: str = "playlist_entry") -> dict[str, Any]:
    """Create a project for one of Spectoom's specialised generators."""
    stamp = now_iso()
    project_type = project_type if project_type in PROJECT_TYPES else "playlist_entry"
    type_defaults = {
        "playlist_entry": {
            "name": "Nouvelle entrée en playlist",
            "tagline": "Entrées en playlist.",
            "accent": "#111111",
        },
        "new_release": {
            "name": "Nouvelle sortie",
            "tagline": "new",
            "accent": "#ffffff",
        },
        "youtube_spectrum": {
            "name": "Nouveau spectrum YouTube",
            "tagline": "Ta musique en vidéo",
            "accent": "#8b5cf6",
        },
    }[project_type]
    clean_name = str(name or "").strip()
    if not clean_name or clean_name == "Nouveau projet":
        clean_name = type_defaults["name"]
    return {
        "id": str(uuid.uuid4()),
        "ownerId": owner_id,
        "type": project_type,
        "name": clean_name,
        "status": "Brouillon",
        "createdAt": stamp,
        "updatedAt": stamp,
        "templateVersion": "v2.2.0",
        "track": {
            "title": "",
            "artist": "",
            "guests": [],
            "coverUrl": "",
        },
        "background": {
            "url": "",
            "videoUrl": "",
            "x": 50,
            "y": 50,
            "zoom": 1.0,
            "veil": 0.46,
            "animation": "zoom",
        },
        "playlists": [],
        "branding": {
            "presetId": "spectoom-interne",
            "tagline": type_defaults["tagline"],
            "logoUrl": "/static/brand/spectoom-white.png",
            "showLogo": project_type != "youtube_spectrum",
            "accent": type_defaults["accent"],
            "logoTone": "white",
        },
        "typography": {
            "fontId": "spectoom-sans",
            "fontName": "Spectoom Sans",
            "fontUrl": "",
            "cssFamily": "Arial, Helvetica, sans-serif",
        },
        "newRelease": {
            "releaseType": "single",
            "template": "editorial",
            "eyebrow": "new",
            "availability": "Disponible maintenant",
            "virginLogoUrl": "/static/brand/virgin-music-red.png",
            "virginLogoTone": "red",
            "titleStyle": "compact",
        },
        "spectrum": {
            "style": "bars",
            "gradient": "aurora",
            "colorA": "#8b5cf6",
            "colorB": "#22d3ee",
            "colorC": "#f472b6",
            "backgroundAnimation": "static",
            "textPosition": "left",
            "titleColor": "#ffffff",
            "artistColor": "#d9d6e7",
            "shadow": True,
            "sensitivity": 1.0,
            "smoothing": 0.82,
        },
        "audio": {
            "url": "",
            "duration": 0.0,
            "start": 0.0,
        },
        "warnings": [],
    }


def project_completion(project: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Validate a project according to its specialised generator."""
    errors: list[dict[str, str]] = []
    project_type = project.get("type", "playlist_entry")
    track = project.get("track", {})
    bg = project.get("background", {})
    branding = project.get("branding", {})
    audio = project.get("audio", {})

    if not str(project.get("name", "")).strip():
        errors.append({"step": "Projet", "message": "Le nom du projet est requis."})
    if not str(track.get("title", "")).strip():
        errors.append({"step": "Morceau", "message": "Le titre est requis."})
    if not str(track.get("artist", "")).strip():
        errors.append({"step": "Morceau", "message": "Le nom de l’artiste est requis."})

    duration = float(audio.get("duration", 0) or 0)
    start = max(0.0, float(audio.get("start", 0) or 0))
    if not audio.get("url"):
        errors.append({"step": "Audio", "message": "Le fichier audio est requis."})
    elif project_type in {"playlist_entry", "new_release"}:
        if duration < 20.0:
            errors.append({"step": "Audio", "message": "Le fichier audio doit durer au moins 20 secondes."})
        elif start + 20.0 > duration + 0.001:
            errors.append({"step": "Audio", "message": "La fenêtre audio dépasse la durée disponible."})
    elif duration <= 0.1:
        errors.append({"step": "Audio", "message": "La durée du morceau n’a pas pu être déterminée."})

    if project_type == "playlist_entry":
        playlists = list(project.get("playlists", []))
        if not track.get("coverUrl"):
            errors.append({"step": "Morceau", "message": "La pochette du morceau est requise."})
        if not bg.get("url"):
            errors.append({"step": "Fond", "message": "L’image d’arrière-plan est requise."})
        if not 1 <= len(playlists) <= 6:
            errors.append({"step": "Playlists", "message": "Ajoutez entre une et six playlists."})
        for idx, item in enumerate(playlists, start=1):
            if not item.get("platformId"):
                errors.append({"step": "Playlists", "message": f"Playlist {idx} : choisissez une plateforme."})
            if not str(item.get("title", "")).strip():
                errors.append({"step": "Playlists", "message": f"Playlist {idx} : le titre est requis."})
            if not item.get("coverUrl"):
                errors.append({"step": "Playlists", "message": f"Playlist {idx} : la couverture est requise."})
        if not str(branding.get("tagline", "")).strip():
            errors.append({"step": "Branding", "message": "L’accroche est requise."})

    elif project_type == "new_release":
        release = project.get("newRelease", {})
        if not bg.get("url"):
            errors.append({"step": "Visuel", "message": "L’image principale de la sortie est requise."})
        if release.get("releaseType") not in {"single", "ep", "album"}:
            errors.append({"step": "Informations", "message": "Choisissez Single, EP ou Album."})
        if release.get("template") not in {"editorial", "artwork"}:
            errors.append({"step": "Template", "message": "Choisissez un template de sortie valide."})
        if not release.get("virginLogoUrl") and not branding.get("logoUrl"):
            errors.append({"step": "Branding", "message": "Le logo Virgin Music est requis."})

    elif project_type == "youtube_spectrum":
        spectrum = project.get("spectrum", {})
        if not bg.get("url") and not bg.get("videoUrl") and not track.get("coverUrl"):
            errors.append({"step": "Fond", "message": "Ajoutez une image, une vidéo de fond ou une cover."})
        if spectrum.get("style") not in {"bars", "mirror", "fluid", "hill", "led", "particles"}:
            errors.append({"step": "Spectrum", "message": "Choisissez un style de visualisation valide."})
    else:
        errors.append({"step": "Projet", "message": "Le type de projet n’est pas reconnu."})

    return ("Prêt" if not errors else "Brouillon", errors)


def migrate_store(store: dict[str, Any]) -> bool:
    """Upgrade former Playlist Video Studio/Spectoom projects without deleting data."""
    changed = False
    if "fonts" not in store:
        store["fonts"] = []
        changed = True
    if "conversions" not in store:
        store["conversions"] = []
        changed = True
    existing_platforms = {item.get("id"): item for item in store.get("platforms", []) if item.get("id")}
    merged_platforms: list[dict[str, Any]] = []
    for default in PLATFORMS_DEFAULT:
        current = existing_platforms.pop(default["id"], None)
        if current is None:
            merged_platforms.append(json.loads(json.dumps(default)))
            changed = True
            continue
        merged = {**default, **current}
        for key in ("iconBlackUrl", "iconWhiteUrl"):
            if merged.get(key) != default[key]:
                merged[key] = default[key]
                changed = True
        merged_platforms.append(merged)
    merged_platforms.extend(existing_platforms.values())
    if store.get("platforms") != merged_platforms:
        store["platforms"] = merged_platforms
        changed = True

    for project in store.get("projects", []):
        if project.get("type") not in PROJECT_TYPES:
            project["type"] = "playlist_entry"
            changed = True
        if project.get("templateVersion") != "v2.2.0":
            project["templateVersion"] = "v2.2.0"
            changed = True
        background = project.setdefault("background", {})
        for key, value in {"videoUrl": "", "animation": "zoom"}.items():
            if key not in background:
                background[key] = value
                changed = True
        branding = project.setdefault("branding", {})
        if project.get("type") == "youtube_spectrum":
            # Spectrum branding is opt-in. Existing projects no longer burn the
            # Spectoom logo unless the user explicitly enables it.
            if "showLogo" not in branding:
                branding["showLogo"] = False
                changed = True
            if branding.get("logoUrl") == "/demo/logo-studio.png":
                branding["logoUrl"] = "/static/brand/spectoom-white.png"
                changed = True
        else:
            if "showLogo" not in branding:
                branding["showLogo"] = True
                changed = True
            if branding.get("logoUrl") in {"", None, "/demo/logo-studio.png"}:
                branding["logoUrl"] = "/static/brand/spectoom-white.png"
                changed = True
        if "logoTone" not in branding:
            branding["logoTone"] = "white"
            changed = True
        typography_defaults = default_project(str(project.get("ownerId", "migration")), "", project.get("type", "playlist_entry"))["typography"]
        typography = project.setdefault("typography", {})
        for key, value in typography_defaults.items():
            if key not in typography:
                typography[key] = value
                changed = True
        release_defaults = default_project(str(project.get("ownerId", "migration")), "", "new_release")["newRelease"]
        release = project.setdefault("newRelease", {})
        for key, value in release_defaults.items():
            if key not in release:
                release[key] = value
                changed = True
        if project.get("type") == "new_release" and release.get("eyebrow") != "new":
            release["eyebrow"] = "new"
            changed = True
        spectrum_defaults = default_project(str(project.get("ownerId", "migration")), "", "youtube_spectrum")["spectrum"]
        spectrum = project.setdefault("spectrum", {})
        for key, value in spectrum_defaults.items():
            if key not in spectrum:
                spectrum[key] = value
                changed = True
        if spectrum.get("style") not in {"bars", "mirror", "fluid", "hill", "led", "particles"}:
            spectrum["style"] = "bars"
            changed = True
        for item in project.setdefault("playlists", []):
            if item.get("iconTone") not in {"auto", "white", "black"}:
                item["iconTone"] = "auto"
                changed = True
    return changed


def load_store() -> dict[str, Any]:
    with STORE_LOCK:
        if not STORE_PATH.exists():
            init_store()
        store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        if migrate_store(store):
            atomic_write_json(STORE_PATH, store)
        return store


def save_store(store: dict[str, Any]) -> None:
    with STORE_LOCK:
        atomic_write_json(STORE_PATH, store)


def asset_disk_path(url: str) -> Path | None:
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if path.startswith("/media/uploads/"):
        root = UPLOAD_DIR
        candidate = root / Path(path).name
    elif path.startswith("/media/renders/"):
        root = RENDER_DIR
        candidate = root / Path(path).name
    elif path.startswith("/demo/"):
        root = STATIC_DIR / "demo"
        candidate = root / Path(path).name
    elif path.startswith("/static/"):
        relative = Path(path.removeprefix("/static/"))
        root = STATIC_DIR
        candidate = root / relative
    else:
        return None
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def available_fonts_for_user(store: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    """Return built-in fonts plus the current user's uploaded font library."""
    custom = [
        json.loads(json.dumps(item))
        for item in store.get("fonts", [])
        if item.get("ownerId") == user_id and item.get("active", True)
    ]
    custom.sort(key=lambda item: str(item.get("name", "")).lower())
    return [json.loads(json.dumps(item)) for item in FONTS_DEFAULT] + custom


def project_font_paths(project: dict[str, Any]) -> tuple[Path, Path]:
    """Resolve the typeface selected for a project for Pillow rendering."""
    typography = project.get("typography", {}) or {}
    font_url = str(typography.get("fontUrl", "") or "")
    if font_url:
        custom = asset_disk_path(font_url)
        if custom and custom.suffix.lower() in FONT_EXTS:
            try:
                ImageFont.truetype(str(custom), 24)
                return custom, custom
            except Exception:
                pass
    font_id = str(typography.get("fontId", "spectoom-sans") or "spectoom-sans")
    return BUILTIN_FONT_PATHS.get(font_id, BUILTIN_FONT_PATHS["spectoom-sans"])


def parse_ffmpeg_duration(output: str) -> float:
    """Extract a HH:MM:SS.mmm duration from FFmpeg diagnostic output."""
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output or "")
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return duration if math.isfinite(duration) and duration > 0 else 0.0


def probe_audio_duration(path: Path) -> float:
    """Read audio duration without requiring ffprobe in the Windows PATH."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                if frame_rate > 0:
                    duration = wav_file.getnframes() / frame_rate
                    if math.isfinite(duration) and duration > 0:
                        return duration
        except (wave.Error, EOFError, OSError):
            pass

    if MutagenFile is not None:
        try:
            media = MutagenFile(str(path))
            duration = float(getattr(getattr(media, "info", None), "length", 0) or 0)
            if math.isfinite(duration) and duration > 0:
                return duration
        except Exception:
            pass

    ffprobe_binary, _source = resolve_ffprobe_binary()
    if ffprobe_binary:
        try:
            result = subprocess.run(
                [
                    ffprobe_binary, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode == 0:
                try:
                    duration = float(result.stdout.strip())
                    if math.isfinite(duration) and duration > 0:
                        return duration
                except ValueError:
                    pass
        except (OSError, subprocess.TimeoutExpired):
            pass

    ffmpeg_binary, _source = resolve_ffmpeg_binary()
    if ffmpeg_binary:
        # FFmpeg prints stream metadata (including duration) before it asks for an output.
        # This is fast and does not decode the whole audio file.
        try:
            result = subprocess.run(
                [ffmpeg_binary, "-hide_banner", "-nostdin", "-i", str(path)],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            duration = parse_ffmpeg_duration((result.stderr or "") + "\n" + (result.stdout or ""))
            if duration > 0:
                return duration
        except (OSError, subprocess.TimeoutExpired):
            pass

    if not ffmpeg_binary and MutagenFile is None:
        raise MediaToolUnavailable(
            "L’analyse audio n’est pas installée. Relancez run.bat afin d’installer "
            "imageio-ffmpeg et Mutagen automatiquement."
        )
    raise ValueError("Le fichier audio est illisible, corrompu ou ne contient aucune piste audio exploitable.")


def probe_video_metadata(path: Path) -> dict[str, Any]:
    """Probe a background video using ffprobe when available, otherwise FFmpeg diagnostics."""
    duration = 0.0
    width = None
    height = None
    ffprobe_binary, _source = resolve_ffprobe_binary()
    if ffprobe_binary:
        try:
            result = subprocess.run(
                [ffprobe_binary, "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height:format=duration", "-of", "json", str(path)],
                capture_output=True, text=True, timeout=25, check=False,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout or "{}")
                stream = (data.get("streams") or [{}])[0]
                width = int(stream.get("width")) if stream.get("width") else None
                height = int(stream.get("height")) if stream.get("height") else None
                duration = float((data.get("format") or {}).get("duration") or 0)
        except Exception:
            pass
    if not width or not height or duration <= 0:
        ffmpeg_binary, _source = resolve_ffmpeg_binary()
        if not ffmpeg_binary:
            raise MediaToolUnavailable("FFmpeg est requis pour analyser une vidéo de fond.")
        result = subprocess.run(
            [ffmpeg_binary, "-hide_banner", "-nostdin", "-i", str(path)],
            capture_output=True, text=True, timeout=25, check=False,
        )
        output = (result.stderr or "") + "\n" + (result.stdout or "")
        duration = duration or parse_ffmpeg_duration(output)
        match = re.search(r"Video:[^\n]*?\b(\d{2,5})x(\d{2,5})\b", output)
        if match:
            width = width or int(match.group(1))
            height = height or int(match.group(2))
    if not width or not height:
        raise ValueError("La vidéo de fond est illisible ou ne contient aucune piste vidéo.")
    return {"duration": round(duration, 3), "width": width, "height": height}


def media_metadata(path: Path, kind: str) -> dict[str, Any]:
    if kind == "font":
        try:
            ImageFont.truetype(str(path), 24)
        except Exception as exc:
            raise ValueError("La police est illisible ou non compatible.") from exc
        return {"fontName": path.stem}
    if kind == "audio":
        duration = probe_audio_duration(path)
        return {"duration": round(duration, 3)}
    if kind == "background-video":
        return probe_video_metadata(path)
    if path.suffix.lower() == ".svg":
        return {"width": None, "height": None}
    try:
        with Image.open(path) as im:
            return {"width": im.width, "height": im.height}
    except Exception:
        return {"width": None, "height": None}


def validate_upload(filename: str, payload: bytes, kind: str) -> tuple[bool, str]:
    ext = Path(filename).suffix.lower()
    if kind == "font":
        if ext not in FONT_EXTS:
            return False, "Format de police non supporté. Utilisez TTF ou OTF."
        if len(payload) > 25 * 1024 * 1024:
            return False, "La police dépasse la limite de 25 Mo."
        try:
            from io import BytesIO
            ImageFont.truetype(BytesIO(payload), 24)
        except Exception:
            return False, "Le fichier de police est invalide ou non compatible."
        return True, ""
    if kind == "audio":
        if ext not in AUDIO_EXTS:
            return False, "Format audio non supporté. Utilisez WAV, MP3, M4A ou AAC."
        if len(payload) > 250 * 1024 * 1024:
            return False, "Le fichier audio dépasse la limite de 250 Mo."
        return True, ""
    if kind == "background-video":
        if ext not in VIDEO_EXTS:
            return False, "Format vidéo non supporté. Utilisez MP4, MOV, M4V ou WebM."
        if len(payload) > 250 * 1024 * 1024:
            return False, "La vidéo de fond dépasse la limite de 250 Mo."
        return True, ""
    if kind == "logo":
        allowed = LOGO_EXTS
        max_bytes = 10 * 1024 * 1024
    elif kind == "track-cover":
        allowed = IMAGE_EXTS
        max_bytes = 15 * 1024 * 1024
    elif kind == "playlist-cover":
        allowed = IMAGE_EXTS
        max_bytes = 10 * 1024 * 1024
    else:
        allowed = IMAGE_EXTS
        max_bytes = 25 * 1024 * 1024
    if ext not in allowed:
        return False, "Format d’image non supporté. Utilisez JPG, PNG ou WebP."
    if len(payload) > max_bytes:
        return False, "Le fichier dépasse la taille maximale autorisée."
    if ext == ".svg":
        try:
            source = payload.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return False, "Le fichier SVG n’est pas un document UTF-8 valide."
        lowered = source.lower()
        if "<svg" not in lowered:
            return False, "Le fichier SVG est invalide."
        forbidden = ("<!doctype", "<!entity", "<script", "javascript:", "onload=", "onerror=", "xlink:href=\"http", "href=\"http")
        if any(marker in lowered for marker in forbidden):
            return False, "Le SVG contient des éléments externes ou exécutables non autorisés."
    else:
        try:
            from io import BytesIO
            with Image.open(BytesIO(payload)) as im:
                im.verify()
        except Exception:
            return False, "Le fichier image est invalide ou corrompu."
    return True, ""


def rasterize_svg(source_path: Path) -> Path:
    """Convert an uploaded SVG logo to a safe raster PNG for preview/rendering."""
    output_path = source_path.with_suffix(".png")
    ffmpeg_binary = require_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source_path), "-frames:v", "1", str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0 or not output_path.exists():
        output_path.unlink(missing_ok=True)
        raise ValueError("Le logo SVG n’a pas pu être converti. Vérifiez sa structure.")
    try:
        with Image.open(output_path) as image:
            if image.width > 4096 or image.height > 4096:
                converted = image.convert("RGBA")
                converted.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
                converted.save(output_path)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise ValueError("Le logo SVG converti est invalide.") from exc
    source_path.unlink(missing_ok=True)
    return output_path


def generate_demo_assets() -> None:
    demo = STATIC_DIR / "demo"
    bg_path = demo / "background.jpg"
    if not bg_path.exists():
        w, h = 1080, 1350
        im = Image.new("RGB", (w, h), "#171920")
        draw = ImageDraw.Draw(im)
        for y in range(h):
            r = int(20 + 35 * y / h)
            g = int(23 + 12 * y / h)
            b = int(31 + 14 * y / h)
            draw.line((0, y, w, y), fill=(r, g, b))
        draw.ellipse((390, 80, 1030, 720), fill=(52, 54, 66))
        draw.ellipse((495, 210, 865, 570), fill=(111, 76, 69))
        draw.rounded_rectangle((410, 500, 1000, 1320), 160, fill=(71, 40, 37))
        draw.polygon([(550, 210), (680, 90), (790, 220), (920, 105), (970, 370), (520, 370)], fill=(30, 25, 28))
        draw.ellipse((585, 350, 640, 405), fill=(33, 26, 28))
        draw.ellipse((735, 350, 790, 405), fill=(33, 26, 28))
        im = im.filter(ImageFilter.GaussianBlur(0.5))
        im.save(bg_path, quality=92)

    palette = [
        ("playlist-1.jpg", "RAP IVOIRE", "#c44832", "#121212"),
        ("playlist-2.jpg", "AFRO RAP", "#d8d4c6", "#2d2926"),
        ("playlist-3.jpg", "COUCHER DE SOLEIL", "#f4a43e", "#292019"),
        ("playlist-4.jpg", "AFRORAP BANGERS", "#7e302d", "#f5ddc6"),
        ("playlist-5.jpg", "LES PÉPITES", "#b79a45", "#151515"),
        ("playlist-6.jpg", "URBAN FOCUS", "#35536e", "#e6eef5"),
    ]
    for filename, title, c1, c2 in palette:
        path = demo / filename
        if path.exists():
            continue
        im = Image.new("RGB", (640, 640), c1)
        draw = ImageDraw.Draw(im)
        draw.ellipse((90, 70, 550, 530), fill=c2)
        draw.rectangle((0, 430, 640, 640), fill="#111111")
        font = ImageFont.truetype(str(FONT_BOLD), 52)
        lines = wrap_text(draw, title, font, 520, max_lines=3)
        y = 458
        for line in lines:
            draw.text((60, y), line, font=font, fill="white")
            y += 62
        im.save(path, quality=91)

    track_path = demo / "track-cover.jpg"
    if not track_path.exists():
        im = Image.new("RGB", (1000, 1000), "#1d2d79")
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 0, 1000, 360), fill="#17336f")
        draw.ellipse((150, 110, 850, 810), fill="#315fc2")
        draw.polygon([(80, 920), (430, 520), (710, 810), (940, 420), (1000, 1000), (0, 1000)], fill="#0d1745")
        draw.text((72, 70), "TIGRES", font=ImageFont.truetype(str(FONT_BOLD), 100), fill="#eef4ff")
        draw.text((76, 850), "CED × MAHLET", font=ImageFont.truetype(str(FONT_BOLD), 46), fill="#ffffff")
        im.save(track_path, quality=92)

    audio_path = demo / "demo-audio.wav"
    if not audio_path.exists():
        sample_rate = 48000
        duration = 28.0
        total = int(sample_rate * duration)
        with wave.open(str(audio_path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for i in range(total):
                t = i / sample_rate
                beat = 0.68 + 0.32 * max(0.0, math.sin(2 * math.pi * 2 * t)) ** 8
                freq = 110 + 55 * (int(t / 4) % 4)
                value = (
                    0.34 * math.sin(2 * math.pi * freq * t)
                    + 0.13 * math.sin(2 * math.pi * freq * 2 * t)
                    + 0.08 * math.sin(2 * math.pi * 440 * t)
                ) * beat
                sample = max(-32767, min(32767, int(value * 32767)))
                frames.extend(struct.pack("<hh", sample, sample))
            wav.writeframes(frames)


def bootstrap_accounts_from_env() -> list[dict[str, str]]:
    """Return the internal accounts configured for this deployment.

    Production never falls back to the public demo passwords. The Render Blueprint
    prompts for these values during the first deployment.
    """
    required = (
        "SPECTOOM_USER_NAME",
        "SPECTOOM_USER_EMAIL",
        "SPECTOOM_USER_PASSWORD",
        "SPECTOOM_ADMIN_NAME",
        "SPECTOOM_ADMIN_EMAIL",
        "SPECTOOM_ADMIN_PASSWORD",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Configuration cloud incomplète. Variables manquantes : " + ", ".join(missing)
        )
    for variable in ("SPECTOOM_USER_PASSWORD", "SPECTOOM_ADMIN_PASSWORD"):
        password = os.environ[variable]
        if len(password) < 12 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise RuntimeError(
                f"{variable} doit contenir au moins 12 caractères, une lettre et un chiffre."
            )
    return [
        {
            "name": os.environ["SPECTOOM_USER_NAME"].strip(),
            "email": os.environ["SPECTOOM_USER_EMAIL"].strip().lower(),
            "password": os.environ["SPECTOOM_USER_PASSWORD"],
            "role": "user",
        },
        {
            "name": os.environ["SPECTOOM_ADMIN_NAME"].strip(),
            "email": os.environ["SPECTOOM_ADMIN_EMAIL"].strip().lower(),
            "password": os.environ["SPECTOOM_ADMIN_PASSWORD"],
            "role": "admin",
        },
    ]


def sync_bootstrap_accounts() -> None:
    """Create or update deployment accounts from environment variables.

    Password rotation is done by changing the secret in the hosting dashboard and
    redeploying. Existing projects remain attached to the same account id.
    """
    if not IS_PRODUCTION:
        return
    accounts = bootstrap_accounts_from_env()
    emails = [item["email"] for item in accounts]
    if len(set(emails)) != len(emails):
        raise RuntimeError("Les comptes utilisateur et administrateur doivent utiliser deux e-mails distincts.")
    with STORE_LOCK:
        store = load_store()
        users = store.setdefault("users", [])
        changed = False
        configured_emails = {account["email"] for account in accounts}
        for existing in users:
            existing_email = str(existing.get("email", "")).lower()
            if existing_email in {"demo@playlist.studio", "admin@playlist.studio"} and existing_email not in configured_emails:
                if existing.get("status") != "disabled":
                    existing["status"] = "disabled"
                    changed = True
        for account in accounts:
            existing = next((u for u in users if str(u.get("email", "")).lower() == account["email"]), None)
            if existing is None:
                existing = {"id": str(uuid.uuid4()), "createdAt": now_iso()}
                users.append(existing)
                changed = True
            desired = {
                "name": account["name"],
                "email": account["email"],
                "passwordHash": password_hash(account["password"]),
                "role": account["role"],
                "status": "active",
            }
            for key, value in desired.items():
                if existing.get(key) != value:
                    existing[key] = value
                    changed = True
        if changed:
            save_store(store)


def init_store() -> None:
    generate_demo_assets()
    accounts = bootstrap_accounts_from_env()
    user_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())

    playlist_demo = default_project(user_id, "Tigres — Entrées en playlist", "playlist_entry")
    playlist_demo.update({
        "status": "Prêt",
        "track": {"title": "TIGRES", "artist": "CED × MAHLET", "guests": [], "coverUrl": "/demo/track-cover.jpg"},
        "background": {"url": "/demo/background.jpg", "videoUrl": "", "x": 58, "y": 44, "zoom": 1.05, "veil": 0.48, "animation": "zoom"},
        "playlists": [
            {"id": str(uuid.uuid4()), "platformId": "spotify", "title": "RAP IVOIRE", "coverUrl": "/demo/playlist-1.jpg", "iconTone": "auto"},
            {"id": str(uuid.uuid4()), "platformId": "spotify", "title": "AFRO RAP", "coverUrl": "/demo/playlist-2.jpg", "iconTone": "auto"},
            {"id": str(uuid.uuid4()), "platformId": "spotify", "title": "COUCHER DE SOLEIL", "coverUrl": "/demo/playlist-3.jpg", "iconTone": "auto"},
            {"id": str(uuid.uuid4()), "platformId": "spotify", "title": "AFRORAP BANGERS", "coverUrl": "/demo/playlist-4.jpg", "iconTone": "auto"},
            {"id": str(uuid.uuid4()), "platformId": "spotify", "title": "LES PÉPITES", "coverUrl": "/demo/playlist-5.jpg", "iconTone": "auto"},
        ],
        "branding": {"presetId": "spectoom-interne", "tagline": "Entrées\nen playlist.", "logoUrl": "/static/brand/spectoom-white.png", "accent": "#ef233c", "logoTone": "white"},
        "audio": {"url": "/demo/demo-audio.wav", "duration": 28.0, "start": 4.0},
    })

    release_demo = default_project(user_id, "Éclat — Nouvelle sortie", "new_release")
    release_demo.update({
        "status": "Prêt",
        "track": {"title": "ÉCLAT", "artist": "TIMA", "guests": [], "coverUrl": "/demo/track-cover.jpg"},
        "background": {"url": "/demo/new-release-background.jpg", "videoUrl": "", "x": 58, "y": 43, "zoom": 1.04, "veil": 0.28, "animation": "zoom"},
        "branding": {"presetId": "virgin-music", "tagline": "new", "logoUrl": "/static/brand/spectoom-white.png", "accent": "#ffffff", "logoTone": "white"},
        "newRelease": {"releaseType": "single", "template": "editorial", "eyebrow": "new", "availability": "Disponible maintenant", "virginLogoUrl": "/static/brand/virgin-music-red.png", "virginLogoTone": "red", "titleStyle": "compact"},
        "audio": {"url": "/demo/demo-audio.wav", "duration": 28.0, "start": 3.0},
    })

    spectrum_demo = default_project(user_id, "Midnight — Spectrum YouTube", "youtube_spectrum")
    spectrum_demo.update({
        "status": "Prêt",
        "track": {"title": "MIDNIGHT", "artist": "CED", "guests": [], "coverUrl": "/demo/spectrum-cover.jpg"},
        "background": {"url": "/demo/spectrum-background.jpg", "videoUrl": "", "x": 52, "y": 46, "zoom": 1.02, "veil": 0.52, "animation": "pulse"},
        "branding": {"presetId": "spectoom-interne", "tagline": "Ta musique en vidéo", "logoUrl": "/static/brand/spectoom-white.png", "showLogo": False, "accent": "#8b5cf6", "logoTone": "white"},
        "spectrum": {"style": "bars", "gradient": "aurora", "colorA": "#8b5cf6", "colorB": "#22d3ee", "colorC": "#f472b6", "backgroundAnimation": "static", "textPosition": "left", "titleColor": "#ffffff", "artistColor": "#d9d6e7", "shadow": True, "sensitivity": 1.0, "smoothing": 0.82},
        "audio": {"url": "/demo/demo-audio.wav", "duration": 28.0, "start": 0.0},
    })

    users = [
        {
            "id": user_id,
            "name": accounts[0]["name"],
            "email": accounts[0]["email"],
            "passwordHash": password_hash(accounts[0]["password"]),
            "role": accounts[0]["role"],
            "status": "active",
            "createdAt": now_iso(),
        },
        {
            "id": admin_id,
            "name": accounts[1]["name"],
            "email": accounts[1]["email"],
            "passwordHash": password_hash(accounts[1]["password"]),
            "role": accounts[1]["role"],
            "status": "active",
            "createdAt": now_iso(),
        },
    ]
    seed_demo = env_flag("SPECTOOM_SEED_DEMO", not IS_PRODUCTION)
    store = {
        "users": users,
        "projects": [playlist_demo, release_demo, spectrum_demo] if seed_demo else [],
        "renders": [],
        "conversions": [],
        "assets": [],
        "fonts": [],
        "platforms": PLATFORMS_DEFAULT,
        "presets": PRESETS_DEFAULT,
    }
    atomic_write_json(STORE_PATH, store)

def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2) -> list[str]:
    """Wrap text without silently adding ellipses.

    Explicit line breaks are respected. The caller can reduce the font size when
    the final line still exceeds max_width.
    """
    raw_lines = str(text or "").replace("\\n", "\n").splitlines() or [""]
    lines: list[str] = []
    for raw in raw_lines:
        words = re.split(r"\s+", raw.strip()) if raw.strip() else [""]
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if not current or bbox[2] - bbox[0] <= max_width:
                current = candidate
                continue
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                return lines[:max_lines]
        lines.append(current)
        if len(lines) >= max_lines:
            return lines[:max_lines]
    return lines[:max_lines] or [""]


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_size: int,
    min_size: int,
    max_width: int,
    max_lines: int = 2,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Find the largest font for which all wrapped lines fit."""
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap_text(draw, text, font, max_width, max_lines)
        if len(lines) <= max_lines and all(
            draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] <= max_width
            for line in lines
        ):
            return font, lines
    font = ImageFont.truetype(str(font_path), min_size)
    return font, wrap_text(draw, text, font, max_width, max_lines)


def crop_cover(
    image: Image.Image,
    size: tuple[int, int],
    x_pct: float = 50,
    y_pct: float = 50,
    zoom: float = 1.0,
) -> Image.Image:
    """Reproduce CSS object-fit:cover + object-position + centered transform zoom.

    The browser preview and the MP4 renderer both use this exact crop model in
    V1.3. The user crop is first resolved at zoom 1, then the resulting canvas is
    enlarged around its center, matching a CSS transform-origin:center.
    """
    target_w, target_h = size
    source = ImageOps.exif_transpose(image).convert("RGB")
    base_scale = max(target_w / source.width, target_h / source.height)
    render_w = max(target_w, int(round(source.width * base_scale)))
    render_h = max(target_h, int(round(source.height * base_scale)))
    source = source.resize((render_w, render_h), Image.Resampling.LANCZOS)

    extra_x = max(0, render_w - target_w)
    extra_y = max(0, render_h - target_h)
    x_position = max(0.0, min(100.0, float(x_pct or 50))) / 100.0
    y_position = max(0.0, min(100.0, float(y_pct or 50))) / 100.0
    left = int(round(extra_x * x_position))
    top = int(round(extra_y * y_position))
    canvas = source.crop((left, top, left + target_w, top + target_h))

    zoom_value = max(1.0, min(1.6, float(zoom or 1.0)))
    if zoom_value > 1.0001:
        zoom_w = max(target_w, int(round(target_w * zoom_value)))
        zoom_h = max(target_h, int(round(target_h * zoom_value)))
        canvas = canvas.resize((zoom_w, zoom_h), Image.Resampling.LANCZOS)
        zoom_left = (zoom_w - target_w) // 2
        zoom_top = (zoom_h - target_h) // 2
        canvas = canvas.crop((zoom_left, zoom_top, zoom_left + target_w, zoom_top + target_h))
    return canvas


def paste_rounded(base: Image.Image, image: Image.Image, box: tuple[int, int, int, int], radius: int) -> Image.Image:
    x1, y1, x2, y2 = box
    size = (x2 - x1, y2 - y1)
    fitted = crop_cover(image, size).convert("RGBA")
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    base.paste(fitted, (x1, y1), mask)
    return fitted


def hex_color(value: str, fallback: str = "#ef233c") -> tuple[int, int, int, int]:
    value = (value or fallback).lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    except Exception:
        return (239, 35, 60, 255)


def load_rgba(url: str, fallback_size: tuple[int, int] = (640, 640), label: str = "IMAGE") -> Image.Image:
    path = asset_disk_path(url)
    if path and path.suffix.lower() != ".svg":
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    image = Image.new("RGBA", fallback_size, (44, 47, 55, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (20, 20, fallback_size[0] - 20, fallback_size[1] - 20),
        outline=(255, 255, 255, 80),
        width=3,
    )
    font_size = max(18, min(72, fallback_size[0] // 10))
    draw.text(
        (fallback_size[0] // 2, fallback_size[1] // 2),
        label,
        anchor="mm",
        font=ImageFont.truetype(str(FONT_BOLD), font_size),
        fill=(255, 255, 255, 180),
    )
    return image


def make_placeholder_background(size: tuple[int, int] = (1080, 1350)) -> Image.Image:
    """Neutral placeholder used by the exact preview before a background upload."""
    width, height = size
    image = Image.new("RGB", size, "#171920")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        mix = y / max(1, height - 1)
        value = int(24 + 18 * mix)
        draw.line((0, y, width, y), fill=(value, value + 2, value + 9))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((560, 70, 1160, 670), fill=(92, 97, 116, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    return Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")


def readability_overlay(size: tuple[int, int], veil: float) -> Image.Image:
    """Build the same two readability gradients used by the editor preview."""
    width, height = size
    strength = max(0.25, min(0.75, float(veil or 0.48)))

    vertical = Image.new("RGBA", size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vertical)
    midpoint = 0.45
    for y in range(height):
        pos = y / max(1, height - 1)
        if pos <= midpoint:
            ratio = pos / midpoint
            alpha = 0.30 + (0.10 - 0.30) * ratio
        else:
            ratio = (pos - midpoint) / (1.0 - midpoint)
            alpha = 0.10 + (0.78 - 0.10) * ratio
        vd.line((0, y, width, y), fill=(5, 6, 9, int(round(255 * alpha * strength))))

    horizontal = Image.new("RGBA", size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(horizontal)
    stop = 0.58
    for x in range(width):
        pos = x / max(1, width - 1)
        ratio = min(1.0, pos / stop)
        alpha = 0.30 + (0.06 - 0.30) * ratio
        hd.line((x, 0, x, height), fill=(5, 6, 9, int(round(255 * alpha * strength))))

    return Image.alpha_composite(vertical, horizontal)


def contain_image(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    contained = ImageOps.exif_transpose(image).convert("RGBA")
    contained.thumbnail(max_size, Image.Resampling.LANCZOS)
    return contained


def region_luminance(image: Image.Image, box: tuple[int, int, int, int] | None = None) -> float:
    """Return perceived luminance from 0 (black) to 1 (white)."""
    sample = image.convert("RGB")
    if box is not None:
        x1, y1, x2, y2 = box
        x1 = max(0, min(sample.width - 1, int(x1)))
        y1 = max(0, min(sample.height - 1, int(y1)))
        x2 = max(x1 + 1, min(sample.width, int(x2)))
        y2 = max(y1 + 1, min(sample.height, int(y2)))
        sample = sample.crop((x1, y1, x2, y2))
    sample.thumbnail((72, 72), Image.Resampling.BILINEAR)
    stat = ImageStat.Stat(sample)
    red, green, blue = stat.mean[:3]
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def resolve_icon_tone(requested: Any, contrast_image: Image.Image, box: tuple[int, int, int, int] | None = None) -> str:
    tone = str(requested or "auto").lower()
    if tone in {"white", "black"}:
        return tone
    return "black" if region_luminance(contrast_image, box) >= 0.58 else "white"


def load_platform_icon(platform: dict[str, Any], tone: str, max_size: tuple[int, int]) -> Image.Image | None:
    key = "iconBlackUrl" if tone == "black" else "iconWhiteUrl"
    path = asset_disk_path(str(platform.get(key, "")))
    if not path:
        return None
    try:
        with Image.open(path) as source:
            return contain_image(source, max_size)
    except Exception:
        return None


def composite_icon_with_shadow(
    destination: Image.Image,
    icon: Image.Image,
    xy: tuple[int, int],
    tone: str,
    *,
    blur: int = 4,
) -> None:
    """Place a monochrome icon with a restrained opposite-tone halo."""
    x, y = xy
    alpha = icon.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(1, blur)))
    shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.62))
    shadow_color = (255, 255, 255, 210) if tone == "black" else (0, 0, 0, 210)
    shadow = Image.new("RGBA", icon.size, shadow_color)
    shadow.putalpha(shadow_alpha)
    destination.alpha_composite(shadow, (x + 1, y + 2))
    destination.alpha_composite(icon, (x, y))


def draw_shadowed_text(
    layer: Image.Image,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int] | str,
    anchor: str = "la",
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | str = (0, 0, 0, 170),
) -> None:
    draw = ImageDraw.Draw(layer)
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def layout_positions(n: int) -> list[tuple[int, int, int]]:
    """Pixel geometry mirroring the V1.3 4:5 preview grid."""
    left, top, width, height = 70, 351, 556, 702
    if n <= 1:
        size = 361
        return [(left + (width - size) // 2, top, size)]
    if n == 2:
        size, gap = 266, 23
        card_height = size + 11 + 47
        y = top + (height - card_height) // 2
        return [(left, y, size), (left + size + gap, y, size)]
    if n == 3:
        size, gap = 266, 23
        row_two_y = 699
        third_size = 256
        return [
            (left, top, size),
            (left + size + gap, top, size),
            (left + (width - third_size) // 2, row_two_y, third_size),
        ]
    if n == 4:
        size, gap = 266, 23
        row_two_y = 699
        return [
            (left, top, size),
            (left + size + gap, top, size),
            (left, row_two_y, size),
            (left + size + gap, row_two_y, size),
        ]
    size, gap, row_two_y = 174, 17, 600
    columns = [left, left + size + gap, left + 2 * (size + gap)]
    first_row = [(columns[index], top, size) for index in range(3)]
    if n == 5:
        shift = int(round(size * 0.53))
        return first_row + [
            (columns[0] + shift, row_two_y, size),
            (columns[1] + shift, row_two_y, size),
        ]
    return first_row + [(columns[index], row_two_y, size) for index in range(3)]


def visual_signature(project: dict[str, Any], platforms: list[dict[str, Any]]) -> str:
    used_platforms = {item.get("platformId") for item in project.get("playlists", []) if item.get("platformId")}
    platform_payload = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "short": item.get("short"),
            "iconBlackUrl": item.get("iconBlackUrl"),
            "iconWhiteUrl": item.get("iconWhiteUrl"),
        }
        for item in platforms
        if item.get("id") in used_platforms
    ]
    payload = {
        "renderer": RENDERER_VERSION,
        "type": project.get("type", "playlist_entry"),
        "track": project.get("track", {}),
        "background": project.get("background", {}),
        "playlists": project.get("playlists", [])[:6],
        "branding": project.get("branding", {}),
        "typography": project.get("typography", {}),
        "newRelease": project.get("newRelease", {}),
        "spectrum": project.get("spectrum", {}),
        "platforms": platform_payload,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def create_template_assets(
    project: dict[str, Any],
    output_dir: Path,
    platforms: list[dict[str, Any]],
    *,
    strict: bool,
) -> dict[str, Any]:
    """Rasterize all visual layers used by both preview and final MP4.

    This function is the single source of truth for crop, typography, card
    placement, badges, logo containment and the track block. The browser only
    displays these layers; FFmpeg only animates these same layers.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    font_regular_path, font_bold_path = project_font_paths(project)
    canvas_size = (1080, 1350)
    background_data = project.get("background", {})
    bg_path = asset_disk_path(background_data.get("url", ""))
    if bg_path:
        try:
            with Image.open(bg_path) as source:
                background = crop_cover(
                    source,
                    canvas_size,
                    background_data.get("x", 50),
                    background_data.get("y", 50),
                    background_data.get("zoom", 1.0),
                )
        except Exception as exc:
            if strict:
                raise ValueError("L’image d’arrière-plan ne peut pas être lue.") from exc
            background = make_placeholder_background(canvas_size)
    else:
        if strict:
            raise ValueError("Image d’arrière-plan introuvable.")
        background = make_placeholder_background(canvas_size)
    background = background.filter(ImageFilter.GaussianBlur(0.15))
    background_out = output_dir / "background.png"
    background.save(background_out, optimize=True)

    accent = hex_color(project.get("branding", {}).get("accent", "#ef233c"))
    veil = float(background_data.get("veil", 0.48) or 0.48)

    base_layer = readability_overlay(canvas_size, veil)
    bd = ImageDraw.Draw(base_layer)
    corner_x, corner_y, corner_w, corner_h, line_w = 37, 45, 95, 95, 7
    bd.line((corner_x, corner_y, corner_x + corner_w, corner_y), fill=accent, width=line_w)
    bd.line((corner_x, corner_y, corner_x, corner_y + corner_h), fill=accent, width=line_w)
    right_x = 1080 - corner_x
    bd.line((right_x - corner_w, corner_y, right_x, corner_y), fill=accent, width=line_w)
    bd.line((right_x, corner_y, right_x, corner_y + corner_h), fill=accent, width=line_w)
    base_out = output_dir / "base.png"
    base_layer.save(base_out, optimize=True)

    header_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(header_layer)
    branding = project.get("branding", {})
    tagline = str(branding.get("tagline", "Entrées en playlist.") or "Entrées en playlist.").replace("\\n", "\n")
    tagline_font, tagline_lines = fit_font(hd, tagline, font_bold_path, 58, 36, 455, max_lines=2)
    tagline_y = 84
    for line in tagline_lines[:2]:
        draw_shadowed_text(
            header_layer,
            (69, tagline_y),
            line,
            font=tagline_font,
            fill=accent,
            anchor="la",
            stroke_width=1,
            stroke_fill=(0, 0, 0, 85),
        )
        tagline_y += int(round(tagline_font.size * 0.97))

    logo_box = (774, 78, 1012, 213)
    logo_path = asset_disk_path(branding.get("logoUrl", ""))
    if logo_path and logo_path.suffix.lower() != ".svg":
        try:
            with Image.open(logo_path) as source_logo:
                logo = contain_image(source_logo, (logo_box[2] - logo_box[0], logo_box[3] - logo_box[1]))
            logo_x = logo_box[2] - logo.width
            logo_y = logo_box[1] + (logo_box[3] - logo_box[1] - logo.height) // 2
            header_layer.alpha_composite(logo, (logo_x, logo_y))
        except Exception:
            logo_path = None
    if not logo_path:
        fallback_font = ImageFont.truetype(str(font_bold_path), 26)
        hd.multiline_text(
            (1012, 118),
            "SPECTOOM",
            anchor="rm",
            align="right",
            spacing=2,
            font=fallback_font,
            fill="white",
        )

    platform_map = {item.get("id"): item for item in platforms}
    playlists = list(project.get("playlists", []))[:6]
    unique_platforms = {item.get("platformId") for item in playlists if item.get("platformId")}
    contrast_reference = Image.alpha_composite(background.convert("RGBA"), base_layer)
    if len(unique_platforms) == 1 and playlists:
        platform = platform_map.get(next(iter(unique_platforms)), {"short": "PL", "name": "Plateforme"})
        requested_tone = playlists[0].get("iconTone", "auto")
        logo_region = (70, 245, 470, 330)
        tone = resolve_icon_tone(requested_tone, contrast_reference, logo_region)
        icon_size = 49
        icon = load_platform_icon(platform, tone, (icon_size, icon_size))
        name_text = str(platform.get("name", "Plateforme"))
        name_font = ImageFont.truetype(str(font_bold_path), 27)
        platform_x, platform_y = 76, 253
        text_color = "#111318" if tone == "black" else "white"
        text_stroke = (255, 255, 255, 115) if tone == "black" else (0, 0, 0, 150)
        if icon:
            icon_y = platform_y + (54 - icon.height) // 2
            composite_icon_with_shadow(header_layer, icon, (platform_x, icon_y), tone, blur=4)
            text_x = platform_x + icon.width + 14
        else:
            fallback = str(platform.get("short", "PL"))
            fallback_font = ImageFont.truetype(str(font_bold_path), 25)
            hd.text((platform_x, platform_y + 27), fallback, anchor="lm", font=fallback_font, fill=text_color, stroke_width=1, stroke_fill=text_stroke)
            text_x = platform_x + 53
        hd.text(
            (text_x, platform_y + 27),
            name_text,
            anchor="lm",
            font=name_font,
            fill=text_color,
            stroke_width=1,
            stroke_fill=text_stroke,
        )

    header_box = (0, 0, 1080, 330)
    header_out = output_dir / "header.png"
    header_layer.crop(header_box).save(header_out, optimize=True)
    header_entry = {
        "path": header_out,
        "x": header_box[0],
        "y": header_box[1],
        "width": header_box[2] - header_box[0],
        "height": header_box[3] - header_box[1],
    }

    render_playlists = playlists if playlists else [{"title": "Ajoutez vos playlists", "coverUrl": "", "platformId": ""}]
    positions = layout_positions(len(render_playlists))
    card_entries: list[dict[str, Any]] = []
    is_multi_platform = len(unique_platforms) > 1
    for index, (item, (x, y, cover_size)) in enumerate(zip(render_playlists, positions), start=1):
        layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        shadow_margin = 30
        shadow = Image.new("RGBA", (cover_size + shadow_margin * 2, cover_size + shadow_margin * 2), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        radius = max(14, int(round(cover_size * 0.09)))
        sd.rounded_rectangle(
            (shadow_margin, shadow_margin, shadow_margin + cover_size, shadow_margin + cover_size),
            radius,
            fill=(0, 0, 0, 125),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, cover_size // 16)))
        layer.alpha_composite(shadow, (x - shadow_margin, y - shadow_margin + 8))

        cover = load_rgba(item.get("coverUrl", ""), (640, 640), "COVER")
        fitted_cover = paste_rounded(layer, cover, (x, y, x + cover_size, y + cover_size), radius)
        draw.rounded_rectangle(
            (x, y, x + cover_size - 1, y + cover_size - 1),
            radius,
            outline=(255, 255, 255, 90),
            width=max(2, cover_size // 100),
        )

        if is_multi_platform:
            platform = platform_map.get(item.get("platformId"), {"short": "PL", "name": "Plateforme"})
            badge_size = max(32, min(56, int(round(cover_size * 0.20))))
            local_margin = max(12, int(round(cover_size * 0.065)))
            sample_box = (
                local_margin,
                local_margin,
                local_margin + badge_size,
                local_margin + badge_size,
            )
            tone = resolve_icon_tone(item.get("iconTone", "auto"), fitted_cover, sample_box)
            platform_icon = load_platform_icon(platform, tone, (badge_size, badge_size))
            badge_x = x + local_margin
            badge_y = y + local_margin
            if platform_icon:
                composite_icon_with_shadow(layer, platform_icon, (badge_x, badge_y), tone, blur=max(2, badge_size // 12))
            else:
                badge_text = str(platform.get("short", "PL"))
                badge_font = ImageFont.truetype(str(font_bold_path), max(14, min(18, cover_size // 10)))
                fallback_color = "#111318" if tone == "black" else "white"
                fallback_stroke = (255, 255, 255, 130) if tone == "black" else (0, 0, 0, 165)
                draw.text(
                    (badge_x + badge_size // 2, badge_y + badge_size // 2),
                    badge_text,
                    anchor="mm",
                    font=badge_font,
                    fill=fallback_color,
                    stroke_width=2,
                    stroke_fill=fallback_stroke,
                )

        title = str(item.get("title", "Titre de playlist") or "Titre de playlist").upper()
        title_font, title_lines = fit_font(draw, title, font_bold_path, 22, 15, cover_size, max_lines=2)
        title_y = y + cover_size + 11
        line_height = max(18, int(round(title_font.size * 1.05)))
        for line in title_lines[:2]:
            draw.text(
                (x + cover_size // 2, title_y),
                line,
                anchor="ma",
                font=title_font,
                fill="white",
                stroke_width=2,
                stroke_fill=(0, 0, 0, 185),
            )
            title_y += line_height

        card_box = layer.getbbox() or (x, y, x + cover_size, y + cover_size + 60)
        card_out = output_dir / f"card-{index}.png"
        layer.crop(card_box).save(card_out, optimize=True)
        card_entries.append({
            "path": card_out,
            "x": card_box[0],
            "y": card_box[1],
            "width": card_box[2] - card_box[0],
            "height": card_box[3] - card_box[1],
        })

    track_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    td = ImageDraw.Draw(track_layer)
    track = project.get("track", {})
    title = str(track.get("title", "Titre du morceau") or "Titre du morceau").upper()
    artist = str(track.get("artist", "Artiste principal") or "Artiste principal").upper()
    block_right = 1019
    block_bottom = 1280
    block_width = 340
    cover_size = 269
    title_font, title_lines = fit_font(td, title, font_bold_path, 30, 20, block_width, max_lines=2)
    artist_font, artist_lines = fit_font(td, artist, font_bold_path, 19, 15, block_width, max_lines=2)
    title_line_height = int(round(title_font.size * 1.06))
    artist_line_height = int(round(artist_font.size * 1.08))
    copy_height = title_line_height * len(title_lines) + 7 + artist_line_height * len(artist_lines)
    total_height = cover_size + 20 + copy_height
    block_top = block_bottom - total_height
    cover_x = block_right - cover_size
    cover_y = block_top

    track_shadow = Image.new("RGBA", (cover_size + 70, cover_size + 70), (0, 0, 0, 0))
    tsd = ImageDraw.Draw(track_shadow)
    track_radius = int(round(cover_size * 0.11))
    tsd.rounded_rectangle((35, 35, 35 + cover_size, 35 + cover_size), track_radius, fill=(0, 0, 0, 135))
    track_shadow = track_shadow.filter(ImageFilter.GaussianBlur(18))
    track_layer.alpha_composite(track_shadow, (cover_x - 35, cover_y - 27))
    track_cover = load_rgba(track.get("coverUrl", ""), (1000, 1000), "POCHETTE")
    paste_rounded(track_layer, track_cover, (cover_x, cover_y, cover_x + cover_size, cover_y + cover_size), track_radius)
    td.rounded_rectangle(
        (cover_x, cover_y, cover_x + cover_size - 1, cover_y + cover_size - 1),
        track_radius,
        outline=(255, 255, 255, 80),
        width=2,
    )

    copy_y = cover_y + cover_size + 20
    for line in title_lines:
        td.text(
            (block_right, copy_y),
            line,
            anchor="ra",
            font=title_font,
            fill="white",
            stroke_width=2,
            stroke_fill=(0, 0, 0, 170),
        )
        copy_y += title_line_height
    copy_y += 7
    for line in artist_lines:
        td.text(
            (block_right, copy_y),
            line,
            anchor="ra",
            font=artist_font,
            fill=(242, 244, 248, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 170),
        )
        copy_y += artist_line_height

    track_box = track_layer.getbbox() or (cover_x, cover_y, block_right, block_bottom)
    track_out = output_dir / "track.png"
    track_layer.crop(track_box).save(track_out, optimize=True)
    track_entry = {
        "path": track_out,
        "x": track_box[0],
        "y": track_box[1],
        "width": track_box[2] - track_box[0],
        "height": track_box[3] - track_box[1],
    }

    composite = background.convert("RGBA")
    composite = Image.alpha_composite(composite, base_layer)
    composite.alpha_composite(header_layer.crop(header_box), (header_box[0], header_box[1]))
    for card in card_entries:
        with Image.open(card["path"]) as card_image:
            composite.alpha_composite(card_image.convert("RGBA"), (card["x"], card["y"]))
    with Image.open(track_entry["path"]) as track_image:
        composite.alpha_composite(track_image.convert("RGBA"), (track_entry["x"], track_entry["y"]))
    composite_out = output_dir / "composite.png"
    composite.convert("RGB").save(composite_out, quality=94, optimize=True)

    # FFmpeg reads one packed transparent atlas instead of opening one looping
    # image stream per layer. This keeps memory bounded on Windows and on
    # machines with modest RAM while preserving the exact same raster assets
    # shown in the browser preview.
    atlas_items: list[tuple[str, dict[str, Any]]] = [
        ("base", {"path": base_out, "x": 0, "y": 0, "width": 1080, "height": 1350}),
        ("header", header_entry),
        *[(f"card-{index}", card) for index, card in enumerate(card_entries)],
        ("track", track_entry),
    ]
    atlas_gap = 2
    atlas_height = sum(int(item["height"]) for _name, item in atlas_items) + atlas_gap * max(0, len(atlas_items) - 1)
    atlas_image = Image.new("RGBA", (1080, atlas_height), (0, 0, 0, 0))
    atlas_regions: dict[str, Any] = {"cards": []}
    atlas_y = 0
    for name, item in atlas_items:
        with Image.open(item["path"]) as source_layer:
            atlas_image.alpha_composite(source_layer.convert("RGBA"), (0, atlas_y))
        region = {
            "sourceX": 0,
            "sourceY": atlas_y,
            "width": int(item["width"]),
            "height": int(item["height"]),
            "x": int(item["x"]),
            "y": int(item["y"]),
        }
        if name.startswith("card-"):
            atlas_regions["cards"].append(region)
        else:
            atlas_regions[name] = region
        atlas_y += int(item["height"]) + atlas_gap
    atlas_out = output_dir / "layers-atlas.png"
    atlas_image.save(atlas_out, optimize=True)

    manifest = {
        "renderer": RENDERER_VERSION,
        "background": background_out,
        "base": base_out,
        "header": header_entry,
        "cards": card_entries,
        "track": track_entry,
        "atlas": atlas_out,
        "atlasRegions": atlas_regions,
        "composite": composite_out,
    }
    return manifest


def _save_scene_atlas(
    output_dir: Path,
    base_out: Path,
    header_entry: dict[str, Any],
    card_entries: list[dict[str, Any]],
    track_entry: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Pack transparent layers into one atlas so FFmpeg opens two image streams only."""
    atlas_items: list[tuple[str, dict[str, Any]]] = [
        ("base", {"path": base_out, "x": 0, "y": 0, "width": 1080, "height": 1350}),
        ("header", header_entry),
        *[(f"card-{index}", card) for index, card in enumerate(card_entries)],
        ("track", track_entry),
    ]
    atlas_gap = 2
    atlas_height = sum(int(item["height"]) for _name, item in atlas_items) + atlas_gap * max(0, len(atlas_items) - 1)
    atlas_image = Image.new("RGBA", (1080, atlas_height), (0, 0, 0, 0))
    atlas_regions: dict[str, Any] = {"cards": []}
    atlas_y = 0
    for name, item in atlas_items:
        with Image.open(item["path"]) as source_layer:
            atlas_image.alpha_composite(source_layer.convert("RGBA"), (0, atlas_y))
        region = {
            "sourceX": 0,
            "sourceY": atlas_y,
            "width": int(item["width"]),
            "height": int(item["height"]),
            "x": int(item["x"]),
            "y": int(item["y"]),
        }
        if name.startswith("card-"):
            atlas_regions["cards"].append(region)
        else:
            atlas_regions[name] = region
        atlas_y += int(item["height"]) + atlas_gap
    atlas_out = output_dir / "layers-atlas.png"
    atlas_image.save(atlas_out, optimize=True)
    return atlas_out, atlas_regions


def _extract_video_preview_frame(video_path: Path, output_path: Path) -> Path | None:
    try:
        ffmpeg_binary = require_ffmpeg()
        result = subprocess.run(
            [ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error", "-ss", "0.2", "-i", str(video_path),
             "-frames:v", "1", str(output_path)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return output_path if result.returncode == 0 and output_path.exists() else None
    except Exception:
        return None


def create_new_release_assets(
    project: dict[str, Any],
    output_dir: Path,
    platforms: list[dict[str, Any]],
    *,
    strict: bool,
) -> dict[str, Any]:
    """Create the 4:5 Virgin Music new-release scene used by preview and render."""
    del platforms
    output_dir.mkdir(parents=True, exist_ok=True)
    font_regular_path, font_bold_path = project_font_paths(project)
    canvas_size = (1080, 1350)
    background_data = project.get("background", {})
    track = project.get("track", {})
    source_path = asset_disk_path(background_data.get("url", "")) or asset_disk_path(track.get("coverUrl", ""))
    if source_path:
        try:
            with Image.open(source_path) as source:
                background = crop_cover(
                    source,
                    canvas_size,
                    background_data.get("x", 50),
                    background_data.get("y", 50),
                    background_data.get("zoom", 1.0),
                )
        except Exception as exc:
            if strict:
                raise ValueError("L’image principale de la sortie ne peut pas être lue.") from exc
            background = make_placeholder_background(canvas_size)
    else:
        if strict:
            raise ValueError("Image principale de la sortie introuvable.")
        background = make_placeholder_background(canvas_size)
    background_out = output_dir / "background.png"
    background.save(background_out, optimize=True)

    release = project.get("newRelease", {})
    branding = project.get("branding", {})
    template = release.get("template", "editorial")
    veil = max(0.0, min(0.85, float(background_data.get("veil", 0.34) or 0.34)))

    base_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(base_layer)
    # Gentle global veil plus stronger lower gradient for text protection.
    bd.rectangle((0, 0, 1080, 1350), fill=(0, 0, 0, int(veil * 120)))
    for y in range(1350):
        position = y / 1349
        bottom_alpha = int(210 * max(0.0, (position - 0.44) / 0.56) ** 1.45)
        top_alpha = int(68 * max(0.0, (0.20 - position) / 0.20))
        alpha = max(bottom_alpha, top_alpha)
        if alpha:
            bd.line((0, y, 1080, y), fill=(5, 5, 8, alpha))
    # Editorial marks borrowed from the supplied references without copying a full layout.
    line_color = (255, 255, 255, 205)
    bd.line((58, 58, 150, 58), fill=line_color, width=6)
    bd.line((58, 58, 58, 150), fill=line_color, width=6)
    bd.line((1022, 1200, 930, 1200), fill=line_color, width=6)
    bd.line((1022, 1200, 1022, 1108), fill=line_color, width=6)
    base_out = output_dir / "base.png"
    base_layer.save(base_out, optimize=True)

    header_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(header_layer)
    release_type = str(release.get("releaseType", "single") or "single").upper()
    eyebrow = "new"
    header_font = ImageFont.truetype(str(font_bold_path), 42)
    hd.text((76, 98), eyebrow, font=header_font, fill="white", anchor="la", stroke_width=1, stroke_fill=(0, 0, 0, 120))
    hd.text((1004, 98), release_type.lower(), font=header_font, fill="white", anchor="ra", stroke_width=1, stroke_fill=(0, 0, 0, 120))

    logo_url = release.get("virginLogoUrl") or branding.get("logoUrl")
    logo_path = asset_disk_path(logo_url or "")
    logo_box = (742, 405, 1006, 555) if template == "editorial" else (790, 1120, 1006, 1242)
    if logo_path and logo_path.suffix.lower() != ".svg":
        try:
            with Image.open(logo_path) as source_logo:
                logo = contain_image(source_logo, (logo_box[2] - logo_box[0], logo_box[3] - logo_box[1]))
            header_layer.alpha_composite(logo, (logo_box[2] - logo.width, logo_box[1] + (logo_box[3] - logo_box[1] - logo.height) // 2))
        except Exception:
            logo_path = None
    if not logo_path:
        virgin_font = ImageFont.truetype(str(font_bold_path), 32)
        hd.text((logo_box[2], (logo_box[1] + logo_box[3]) // 2), "VIRGIN MUSIC", font=virgin_font, fill="white", anchor="rm")

    header_box = header_layer.getbbox() or (0, 0, 1080, 560)
    header_out = output_dir / "header.png"
    header_layer.crop(header_box).save(header_out, optimize=True)
    header_entry = {
        "path": header_out,
        "x": header_box[0], "y": header_box[1],
        "width": header_box[2] - header_box[0], "height": header_box[3] - header_box[1],
    }

    card_entries: list[dict[str, Any]] = []
    if template == "artwork":
        card_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        cover_source = load_rgba(track.get("coverUrl") or background_data.get("url", ""), (1000, 1000), "COVER")
        size = 610
        x = (1080 - size) // 2
        y = 225
        shadow = Image.new("RGBA", (size + 100, size + 100), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((50, 50, 50 + size, 50 + size), 42, fill=(0, 0, 0, 170))
        shadow = shadow.filter(ImageFilter.GaussianBlur(28))
        card_layer.alpha_composite(shadow, (x - 50, y - 28))
        paste_rounded(card_layer, cover_source, (x, y, x + size, y + size), 36)
        cd = ImageDraw.Draw(card_layer)
        cd.rounded_rectangle((x, y, x + size - 1, y + size - 1), 36, outline=(255, 255, 255, 95), width=3)
        card_box = card_layer.getbbox() or (x, y, x + size, y + size)
        card_out = output_dir / "card-1.png"
        card_layer.crop(card_box).save(card_out, optimize=True)
        card_entries.append({
            "path": card_out, "x": card_box[0], "y": card_box[1],
            "width": card_box[2] - card_box[0], "height": card_box[3] - card_box[1],
        })

    track_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    td = ImageDraw.Draw(track_layer)
    title = str(track.get("title", "Titre de la sortie") or "Titre de la sortie").upper()
    artist = str(track.get("artist", "Artiste") or "Artiste")
    availability = str(release.get("availability", "Disponible maintenant") or "Disponible maintenant")
    if template == "editorial":
        left, max_width, title_y = 76, 610, 700
        title_font, title_lines = fit_font(td, title, font_bold_path, 78, 42, max_width, max_lines=2)
        line_h = int(title_font.size * 1.00)
        for line in title_lines:
            td.text((left, title_y), line, font=title_font, fill="white", anchor="la", stroke_width=2, stroke_fill=(0, 0, 0, 170))
            title_y += line_h
        artist_font, artist_lines = fit_font(td, artist, font_regular_path, 35, 24, max_width, max_lines=2)
        artist_y = title_y + 12
        for line in artist_lines:
            td.text((left, artist_y), line, font=artist_font, fill=(246, 246, 246, 245), anchor="la", stroke_width=1, stroke_fill=(0, 0, 0, 150))
            artist_y += int(artist_font.size * 1.12)
        pill_y = min(1225, artist_y + 58)
        pill_font = ImageFont.truetype(str(font_bold_path), 20)
        pill_text = availability.upper()
        bbox = td.textbbox((0, 0), pill_text, font=pill_font)
        pill_w = bbox[2] - bbox[0] + 38
        td.rounded_rectangle((left, pill_y, left + pill_w, pill_y + 48), 24, fill=(255, 255, 255, 230))
        td.text((left + 19, pill_y + 24), pill_text, font=pill_font, fill=(14, 14, 17, 255), anchor="lm")
    else:
        max_width = 880
        title_font, title_lines = fit_font(td, title, font_bold_path, 70, 38, max_width, max_lines=2)
        y = 900
        for line in title_lines:
            td.text((540, y), line, font=title_font, fill="white", anchor="ma", align="center", stroke_width=2, stroke_fill=(0, 0, 0, 180))
            y += int(title_font.size * 1.02)
        artist_font, artist_lines = fit_font(td, artist, font_regular_path, 34, 23, max_width, max_lines=2)
        y += 8
        for line in artist_lines:
            td.text((540, y), line, font=artist_font, fill=(242, 242, 244, 245), anchor="ma", align="center", stroke_width=1, stroke_fill=(0, 0, 0, 150))
            y += int(artist_font.size * 1.12)
        availability_font = ImageFont.truetype(str(font_bold_path), 18)
        td.text((76, 1237), availability.upper(), font=availability_font, fill="white", anchor="la", stroke_width=1, stroke_fill=(0, 0, 0, 130))

    track_box = track_layer.getbbox() or (60, 650, 1020, 1280)
    track_out = output_dir / "track.png"
    track_layer.crop(track_box).save(track_out, optimize=True)
    track_entry = {
        "path": track_out, "x": track_box[0], "y": track_box[1],
        "width": track_box[2] - track_box[0], "height": track_box[3] - track_box[1],
    }

    composite = background.convert("RGBA")
    composite = Image.alpha_composite(composite, base_layer)
    with Image.open(header_out) as layer:
        composite.alpha_composite(layer.convert("RGBA"), (header_entry["x"], header_entry["y"]))
    for card in card_entries:
        with Image.open(card["path"]) as layer:
            composite.alpha_composite(layer.convert("RGBA"), (card["x"], card["y"]))
    with Image.open(track_out) as layer:
        composite.alpha_composite(layer.convert("RGBA"), (track_entry["x"], track_entry["y"]))
    composite_out = output_dir / "composite.png"
    composite.convert("RGB").save(composite_out, quality=95, optimize=True)

    atlas_out, atlas_regions = _save_scene_atlas(output_dir, base_out, header_entry, card_entries, track_entry)
    return {
        "renderer": RENDERER_VERSION,
        "canvasWidth": 1080,
        "canvasHeight": 1350,
        "background": background_out,
        "base": base_out,
        "header": header_entry,
        "cards": card_entries,
        "track": track_entry,
        "atlas": atlas_out,
        "atlasRegions": atlas_regions,
        "composite": composite_out,
    }


def create_spectrum_assets(
    project: dict[str, Any],
    output_dir: Path,
    platforms: list[dict[str, Any]],
    *,
    strict: bool,
) -> dict[str, Any]:
    """Create the 16:9 static scene around the audio-reactive visualizer."""
    del platforms
    output_dir.mkdir(parents=True, exist_ok=True)
    font_regular_path, font_bold_path = project_font_paths(project)
    canvas_size = (1920, 1080)
    bg = project.get("background", {})
    track = project.get("track", {})
    image_path = asset_disk_path(bg.get("url", "")) or asset_disk_path(track.get("coverUrl", ""))
    video_path = asset_disk_path(bg.get("videoUrl", ""))
    extracted = None
    if not image_path and video_path:
        extracted = _extract_video_preview_frame(video_path, output_dir / "video-frame.png")
        image_path = extracted
    if image_path:
        try:
            with Image.open(image_path) as source:
                background = crop_cover(source, canvas_size, bg.get("x", 50), bg.get("y", 50), bg.get("zoom", 1.0))
        except Exception as exc:
            if strict and not video_path:
                raise ValueError("Le fond du spectrum ne peut pas être lu.") from exc
            background = Image.new("RGB", canvas_size, "#15121f")
    else:
        background = Image.new("RGB", canvas_size, "#15121f")
        gd = ImageDraw.Draw(background)
        colors = [hex_color(project.get("spectrum", {}).get(key, fallback))[:3] for key, fallback in (("colorA", "#8b5cf6"), ("colorB", "#22d3ee"), ("colorC", "#f472b6"))]
        for y in range(canvas_size[1]):
            t = y / max(1, canvas_size[1] - 1)
            if t < 0.5:
                a, b, u = colors[0], colors[1], t * 2
            else:
                a, b, u = colors[1], colors[2], (t - 0.5) * 2
            color = tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))
            gd.line((0, y, canvas_size[0], y), fill=color)
    background = background.filter(ImageFilter.GaussianBlur(1.2))
    background_out = output_dir / "background.png"
    background.save(background_out, optimize=True)

    veil = max(0.12, min(0.82, float(bg.get("veil", 0.52) or 0.52)))
    base_layer = Image.new("RGBA", canvas_size, (8, 7, 15, int(255 * veil)))
    bd = ImageDraw.Draw(base_layer)
    # Soft glass panel behind the information.
    bd.rounded_rectangle((110, 120, 1810, 970), 54, fill=(12, 12, 20, 112), outline=(255, 255, 255, 35), width=2)
    base_out = output_dir / "base.png"
    base_layer.save(base_out, optimize=True)

    foreground = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(foreground)
    branding = project.get("branding", {})
    if bool(branding.get("showLogo", False)):
        logo_path = asset_disk_path(branding.get("logoUrl", ""))
        if logo_path and logo_path.suffix.lower() != ".svg":
            try:
                with Image.open(logo_path) as source_logo:
                    logo = contain_image(source_logo, (230, 65))
                foreground.alpha_composite(logo, (146, 154))
            except Exception:
                # A missing or unreadable optional logo must not block the video.
                pass

    cover = load_rgba(track.get("coverUrl", ""), (1000, 1000), "COVER")
    cover_size = 430
    cover_x, cover_y = 150, 305
    shadow = Image.new("RGBA", (cover_size + 100, cover_size + 100), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((50, 50, 50 + cover_size, 50 + cover_size), 38, fill=(0, 0, 0, 175))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    foreground.alpha_composite(shadow, (cover_x - 50, cover_y - 32))
    paste_rounded(foreground, cover, (cover_x, cover_y, cover_x + cover_size, cover_y + cover_size), 32)
    fd.rounded_rectangle((cover_x, cover_y, cover_x + cover_size - 1, cover_y + cover_size - 1), 32, outline=(255, 255, 255, 68), width=2)

    title = str(track.get("title", "Titre du morceau") or "Titre du morceau")
    artist = str(track.get("artist", "Artiste") or "Artiste")
    spectrum = project.get("spectrum", {})
    title_color = hex_color(spectrum.get("titleColor", "#ffffff"))
    artist_color = hex_color(spectrum.get("artistColor", "#d9d6e7"))
    text_x, text_y, max_width = 660, 345, 1020
    title_font, title_lines = fit_font(fd, title, font_bold_path, 76, 42, max_width, max_lines=2)
    for line in title_lines:
        fd.text((text_x, text_y), line, font=title_font, fill=title_color, anchor="la", stroke_width=1, stroke_fill=(0, 0, 0, 100))
        text_y += int(title_font.size * 1.02)
    artist_font, artist_lines = fit_font(fd, artist, font_regular_path, 40, 25, max_width, max_lines=2)
    text_y += 16
    for line in artist_lines:
        fd.text((text_x, text_y), line, font=artist_font, fill=artist_color, anchor="la", stroke_width=1, stroke_fill=(0, 0, 0, 90))
        text_y += int(artist_font.size * 1.10)
    # No technical style label or Spectoom/YouTube signature is burned into the video.

    foreground_out = output_dir / "foreground.png"
    foreground.save(foreground_out, optimize=True)

    # Precompose every static element once. The renderer only has to add the
    # audio-reactive spectrum, which keeps 1080p exports practical on a laptop.
    scene = background.convert("RGBA")
    scene = Image.alpha_composite(scene, base_layer)
    scene = Image.alpha_composite(scene, foreground)
    scene_out = output_dir / "scene.png"
    scene.convert("RGB").save(scene_out, quality=94, optimize=True)

    # A deterministic still visualizer makes dashboard thumbnails useful before playback.
    visualizer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(visualizer)
    color_a = hex_color(spectrum.get("colorA", "#8b5cf6"))
    color_b = hex_color(spectrum.get("colorB", "#22d3ee"))
    seed = int(hashlib.sha256(f"{title}|{artist}".encode("utf-8")).hexdigest()[:8], 16)
    bars = 82
    left, right, mid_y = 660, 1730, 795
    width = right - left
    for index in range(bars):
        x = left + int(index * width / bars)
        mix = index / max(1, bars - 1)
        height = 28 + int(128 * (0.35 + 0.65 * abs(math.sin((index + seed % 17) * 0.37))))
        color = tuple(int(color_a[i] * (1 - mix) + color_b[i] * mix) for i in range(3)) + (225,)
        vd.rounded_rectangle((x, mid_y - height, x + max(3, width // bars - 6), mid_y + height), 4, fill=color)
    visualizer_out = output_dir / "visualizer.png"
    visualizer.save(visualizer_out, optimize=True)

    composite = Image.alpha_composite(scene, visualizer)
    composite_out = output_dir / "composite.png"
    composite.convert("RGB").save(composite_out, quality=94, optimize=True)

    visualizer_video: Path | None = None
    visualizer_geometry: dict[str, Any] | None = None
    audio_path = asset_disk_path(project.get("audio", {}).get("url", ""))
    if audio_path:
        try:
            duration = float(project.get("audio", {}).get("duration", 0) or 0)
            if duration <= 0:
                duration = probe_audio_duration(audio_path)
            visualizer_video, visualizer_geometry = _create_spectrum_visualizer_video(
                project, output_dir, audio_path, max(0.1, duration)
            )
        except Exception:
            if strict:
                raise
            visualizer_video = None
            visualizer_geometry = None
    elif strict:
        raise ValueError("Fichier audio introuvable pour le spectrum.")

    return {
        "renderer": RENDERER_VERSION,
        "canvasWidth": 1920,
        "canvasHeight": 1080,
        "background": background_out,
        "base": base_out,
        "foreground": foreground_out,
        "scene": scene_out,
        "visualizer": visualizer_out,
        "visualizerVideo": visualizer_video,
        "visualizerGeometry": visualizer_geometry,
        "composite": composite_out,
        "backgroundVideo": video_path,
    }


def _manifest_payload_for_scene(project: dict[str, Any], signature: str, assets: dict[str, Any]) -> dict[str, Any]:
    project_type = project.get("type", "playlist_entry")
    payload: dict[str, Any] = {
        "signature": signature,
        "type": project_type,
        "canvasWidth": int(assets.get("canvasWidth", 1080)),
        "canvasHeight": int(assets.get("canvasHeight", 1350)),
        "files": {"composite": assets["composite"].name},
    }
    if project_type in {"playlist_entry", "new_release"}:
        payload["files"].update({
            "background": assets["background"].name,
            "base": assets["base"].name,
            "header": {
                **{key: assets["header"][key] for key in ("x", "y", "width", "height")},
                "name": assets["header"]["path"].name,
            },
            "cards": [
                {**{key: card[key] for key in ("x", "y", "width", "height")}, "name": card["path"].name}
                for card in assets.get("cards", [])
            ],
            "track": {
                **{key: assets["track"][key] for key in ("x", "y", "width", "height")},
                "name": assets["track"]["path"].name,
            },
        })
    else:
        payload["files"].update({
            "background": assets["background"].name,
            "base": assets["base"].name,
            "foreground": assets["foreground"].name,
            "visualizer": assets["visualizer"].name,
        })
        if assets.get("visualizerVideo") and assets.get("visualizerGeometry"):
            payload["files"]["visualizerVideo"] = {
                "name": assets["visualizerVideo"].name,
                **assets["visualizerGeometry"],
            }
    return payload


def ensure_preview_assets(project: dict[str, Any], platforms: list[dict[str, Any]]) -> dict[str, Any]:
    signature = visual_signature(project, platforms)
    project_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(project.get("id", "project"))) or "project"
    target_dir = PREVIEW_DIR / project_id / signature
    manifest_path = target_dir / "manifest.json"
    project_type = project.get("type", "playlist_entry")

    with PREVIEW_LOCK:
        if not manifest_path.exists():
            temp_dir = PREVIEW_DIR / project_id / f".{signature}-{uuid.uuid4().hex[:8]}"
            shutil.rmtree(temp_dir, ignore_errors=True)
            if project_type == "new_release":
                assets = create_new_release_assets(project, temp_dir, platforms, strict=False)
            elif project_type == "youtube_spectrum":
                assets = create_spectrum_assets(project, temp_dir, platforms, strict=False)
            else:
                assets = create_template_assets(project, temp_dir, platforms, strict=False)
                assets["canvasWidth"] = 1080
                assets["canvasHeight"] = 1350
            payload = _manifest_payload_for_scene(project, signature, assets)
            (temp_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            temp_dir.replace(target_dir)
            siblings = sorted(
                [item for item in target_dir.parent.iterdir() if item.is_dir() and not item.name.startswith(".")],
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for stale in siblings[2:]:
                shutil.rmtree(stale, ignore_errors=True)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    base_url = f"/media/previews/{project_id}/{signature}"
    files = payload["files"]
    response: dict[str, Any] = {
        "projectId": project.get("id"),
        "signature": signature,
        "renderer": RENDERER_VERSION,
        "type": payload.get("type", project_type),
        "canvasWidth": payload.get("canvasWidth", 1080),
        "canvasHeight": payload.get("canvasHeight", 1350),
        "compositeUrl": f"{base_url}/{files['composite']}",
    }
    if project_type in {"playlist_entry", "new_release"}:
        response.update({
            "backgroundUrl": f"{base_url}/{files['background']}",
            "baseUrl": f"{base_url}/{files['base']}",
            "header": {
                **{key: files["header"][key] for key in ("x", "y", "width", "height")},
                "url": f"{base_url}/{files['header']['name']}",
            },
            "cards": [
                {**{key: card[key] for key in ("x", "y", "width", "height")}, "url": f"{base_url}/{card['name']}"}
                for card in files.get("cards", [])
            ],
            "track": {
                **{key: files["track"][key] for key in ("x", "y", "width", "height")},
                "url": f"{base_url}/{files['track']['name']}",
            },
        })
    else:
        response.update({
            "backgroundUrl": f"{base_url}/{files['background']}",
            "baseUrl": f"{base_url}/{files['base']}",
            "foregroundUrl": f"{base_url}/{files['foreground']}",
            "visualizerUrl": f"{base_url}/{files['visualizer']}",
        })
        if files.get("visualizerVideo"):
            visualizer_video = files["visualizerVideo"]
            response["visualizerVideoUrl"] = f"{base_url}/{visualizer_video['name']}"
            response["visualizer"] = {
                key: visualizer_video[key]
                for key in ("style", "x", "y", "width", "height", "keySimilarity", "keyBlend", "alpha")
                if key in visualizer_video
            }
    return response


def update_render(render_id: str, **updates: Any) -> None:
    with STORE_LOCK:
        store = load_store()
        for item in store.get("renders", []):
            if item.get("id") == render_id:
                item.update(updates)
                item["updatedAt"] = now_iso()
                break
        save_store(store)


def set_project_status(project_id: str, status: str) -> None:
    with STORE_LOCK:
        store = load_store()
        for project in store.get("projects", []):
            if project.get("id") == project_id:
                project["status"] = status
                project["updatedAt"] = now_iso()
                break
        save_store(store)


def probe_render_output(path: Path) -> dict[str, Any]:
    """Return technical metadata using ffprobe when present, otherwise FFmpeg."""
    ffprobe_binary, ffprobe_source = resolve_ffprobe_binary()
    if ffprobe_binary:
        try:
            probe = subprocess.run(
                [
                    ffprobe_binary, "-v", "error",
                    "-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels,bit_rate,color_space,color_transfer,color_primaries:format=duration",
                    "-of", "json", str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if probe.returncode == 0:
                try:
                    data = json.loads(probe.stdout)
                    data["probeSource"] = ffprobe_source
                    return data
                except Exception:
                    pass
        except (OSError, subprocess.TimeoutExpired):
            pass

    ffmpeg_binary = require_ffmpeg()
    try:
        probe = subprocess.run(
            [ffmpeg_binary, "-hide_banner", "-nostdin", "-i", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"probeSource": "indisponible", "format": {}, "streams": []}
    output = (probe.stderr or "") + "\n" + (probe.stdout or "")
    duration = parse_ffmpeg_duration(output)
    streams: list[dict[str, Any]] = []

    video_line = next((line.strip() for line in output.splitlines() if " Video: " in line), "")
    if video_line:
        codec_match = re.search(r"Video:\s*([^,\s]+)", video_line)
        size_match = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video_line)
        fps_match = re.search(r"\b(\d+(?:\.\d+)?)\s*fps\b", video_line)
        pix_match = re.search(r"Video:\s*[^,]+,\s*([^,(\s]+)", video_line)
        video_stream: dict[str, Any] = {
            "index": 0,
            "codec_type": "video",
            "codec_name": codec_match.group(1) if codec_match else "unknown",
        }
        if size_match:
            video_stream["width"] = int(size_match.group(1))
            video_stream["height"] = int(size_match.group(2))
        if fps_match:
            video_stream["r_frame_rate"] = fps_match.group(1)
        if pix_match:
            video_stream["pix_fmt"] = pix_match.group(1)
        streams.append(video_stream)

    audio_line = next((line.strip() for line in output.splitlines() if " Audio: " in line), "")
    if audio_line:
        codec_match = re.search(r"Audio:\s*([^,\s]+)", audio_line)
        rate_match = re.search(r"\b(\d+)\s*Hz\b", audio_line)
        channels = 2 if "stereo" in audio_line.lower() else 1 if "mono" in audio_line.lower() else None
        audio_stream: dict[str, Any] = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": codec_match.group(1) if codec_match else "unknown",
        }
        if rate_match:
            audio_stream["sample_rate"] = rate_match.group(1)
        if channels:
            audio_stream["channels"] = channels
        streams.append(audio_stream)

    return {
        "probeSource": "ffmpeg",
        "format": {"duration": f"{duration:.6f}" if duration else ""},
        "streams": streams,
    }


def render_playlist_video_job(render_id: str, project_snapshot: dict[str, Any], platforms: list[dict[str, Any]]) -> None:
    project_id = project_snapshot["id"]
    work_dir = TMP_DIR / f"render-{render_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        update_render(render_id, status="En rendu", progress=2, message="Préparation des assets")
        set_project_status(project_id, "En rendu")
        assets = create_template_assets(project_snapshot, work_dir, platforms, strict=True)
        audio_path = asset_disk_path(project_snapshot.get("audio", {}).get("url", ""))
        if not audio_path:
            raise ValueError("Fichier audio introuvable.")
        ffmpeg_binary = require_ffmpeg()
        output_name = f"{slugify(project_snapshot.get('track', {}).get('artist', 'artiste'))}_{slugify(project_snapshot.get('track', {}).get('title', 'titre'))}_playlists_{datetime.now().strftime('%Y%m%d')}_{render_id[:8]}.mp4"
        output_path = RENDER_DIR / output_name

        regions = assets["atlasRegions"]
        inputs: list[str] = [
            "-loop", "1", "-framerate", "30", "-i", str(assets["background"]),
            "-loop", "1", "-framerate", "30", "-i", str(assets["atlas"]),
            "-i", str(audio_path),
        ]
        audio_index = 2

        atlas_branches: list[tuple[str, dict[str, Any]]] = [
            ("base", regions["base"]),
            ("header", regions["header"]),
            *[(f"card_{index}", card) for index, card in enumerate(regions["cards"])],
            ("track", regions["track"]),
        ]
        split_outputs = "".join(f"[atlas_{name}_src]" for name, _region in atlas_branches)
        filters: list[str] = [
            "[0:v]zoompan=z='min(1.035,1+0.035*on/599)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1350:fps=30,format=rgba[background]",
            f"[1:v]format=rgba,split={len(atlas_branches)}{split_outputs}",
        ]

        base = regions["base"]
        filters.append(
            f"[atlas_base_src]crop={base['width']}:{base['height']}:{base['sourceX']}:{base['sourceY']},"
            "setpts=PTS-STARTPTS[base_layer]"
        )
        filters.append("[background][base_layer]overlay=0:0:format=auto[composite0]")
        current = "composite0"

        header = regions["header"]
        header_start, header_duration = 0.60, 0.80
        header_y = (
            f"if(lt(t,{header_start:.2f}),{header['y'] + 4},"
            f"if(lt(t,{header_start + header_duration:.2f}),"
            f"{header['y']}+4*(1-(t-{header_start:.2f})/{header_duration:.2f}),{header['y']}))"
        )
        filters.append(
            f"[atlas_header_src]crop={header['width']}:{header['height']}:{header['sourceX']}:{header['sourceY']},"
            f"fade=t=in:st={header_start:.2f}:d={header_duration:.2f}:alpha=1,setpts=PTS-STARTPTS[header_layer]"
        )
        filters.append(
            f"[{current}][header_layer]overlay=x={header['x']}:y='{header_y}':format=auto[composite_header]"
        )
        current = "composite_header"

        for card_index, card in enumerate(regions["cards"]):
            start_time = 1.00 + card_index * 0.22
            duration = 0.55
            y_expression = (
                f"if(lt(t,{start_time:.2f}),{card['y'] + 10},"
                f"if(lt(t,{start_time + duration:.2f}),"
                f"{card['y']}+10*(1-(t-{start_time:.2f})/{duration:.2f}),{card['y']}))"
            )
            source_name = f"atlas_card_{card_index}_src"
            layer_name = f"card_layer_{card_index}"
            next_name = f"composite_card_{card_index}"
            filters.append(
                f"[{source_name}]crop={card['width']}:{card['height']}:{card['sourceX']}:{card['sourceY']},"
                f"fade=t=in:st={start_time:.2f}:d={duration:.2f}:alpha=1,setpts=PTS-STARTPTS[{layer_name}]"
            )
            filters.append(
                f"[{current}][{layer_name}]overlay=x={card['x']}:y='{y_expression}':format=auto[{next_name}]"
            )
            current = next_name

        track = regions["track"]
        track_start, track_duration = 1.60, 0.80
        track_y = (
            f"if(lt(t,{track_start:.2f}),{track['y'] + 10},"
            f"if(lt(t,{track_start + track_duration:.2f}),"
            f"{track['y']}+10*(1-(t-{track_start:.2f})/{track_duration:.2f}),{track['y']}))"
        )
        filters.append(
            f"[atlas_track_src]crop={track['width']}:{track['height']}:{track['sourceX']}:{track['sourceY']},"
            f"fade=t=in:st={track_start:.2f}:d={track_duration:.2f}:alpha=1,setpts=PTS-STARTPTS[track_layer]"
        )
        filters.append(
            f"[{current}][track_layer]overlay=x={track['x']}:y='{track_y}':format=auto[composed]"
        )
        filters.append("[composed]fade=t=in:st=0:d=0.40,fade=t=out:st=19.30:d=0.70,format=yuv420p[vout]")

        audio_start = max(0.0, float(project_snapshot.get("audio", {}).get("start", 0) or 0))
        filters.append(
            f"[{audio_index}:a]atrim=start={audio_start:.3f}:duration=20.000,asetpts=PTS-STARTPTS,"
            "afade=t=in:st=0:d=0.06,afade=t=out:st=19.55:d=0.45,aresample=48000,alimiter=limit=0.98[aout]"
        )
        filter_complex = ";".join(filters)

        cmd = [
            ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error",
            "-filter_complex_threads", "0",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-t", "20.000", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            str(output_path),
        ]
        update_render(render_id, progress=8, message="Encodage vidéo")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        stderr_lines: list[str] = []

        def read_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                stderr_lines.append(line)
                if len(stderr_lines) > 60:
                    stderr_lines.pop(0)

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        assert proc.stdout is not None
        last_progress = 8
        for raw in proc.stdout:
            raw = raw.strip()
            if raw.startswith("out_time_ms="):
                try:
                    out_us = int(raw.split("=", 1)[1])
                    seconds = out_us / 1_000_000
                    progress = min(96, max(8, int(8 + (seconds / 20) * 88)))
                    if progress >= last_progress + 2:
                        last_progress = progress
                        update_render(render_id, progress=progress, message="Encodage vidéo")
                except Exception:
                    pass
        return_code = proc.wait()
        stderr_thread.join(timeout=1)
        if return_code != 0 or not output_path.exists():
            raise RuntimeError(f"FFmpeg a échoué (code {return_code}). " + " ".join(stderr_lines[-12:]))

        # Technical verification matching the V1 media contract. FFprobe is
        # optional because the packaged Windows fallback contains FFmpeg only.
        verification = probe_render_output(output_path)
        update_render(
            render_id,
            status="Terminé",
            progress=100,
            message="Rendu terminé",
            outputUrl=f"/media/renders/{output_name}",
            filename=output_name,
            verification=verification,
        )
        set_project_status(project_id, "Terminé")
    except Exception as exc:
        traceback.print_exc()
        update_render(render_id, status="Échec", progress=100, message="Échec du rendu", error=str(exc))
        set_project_status(project_id, "Échec")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _run_ffmpeg_progress(
    render_id: str,
    cmd: list[str],
    output_path: Path,
    duration: float,
    *,
    start_progress: int = 8,
    end_progress: int = 96,
    message: str = "Encodage vidéo",
) -> None:
    update_render(render_id, progress=start_progress, message=message)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    stderr_lines: list[str] = []

    def read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line.strip())
            if len(stderr_lines) > 80:
                stderr_lines.pop(0)

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    assert proc.stdout is not None
    last_progress = start_progress
    safe_duration = max(0.1, float(duration))
    for raw in proc.stdout:
        raw = raw.strip()
        if raw.startswith("out_time_ms="):
            try:
                out_us = int(raw.split("=", 1)[1])
                seconds = out_us / 1_000_000
                progress = min(end_progress, max(start_progress, int(start_progress + (seconds / safe_duration) * (end_progress - start_progress))))
                if progress >= last_progress + 1:
                    last_progress = progress
                    update_render(render_id, progress=progress, message=message)
            except Exception:
                pass
    return_code = proc.wait()
    stderr_thread.join(timeout=1)
    if return_code != 0 or not output_path.exists():
        details = " ".join(item for item in stderr_lines[-18:] if item)
        raise RuntimeError(f"FFmpeg a échoué (code {return_code}). {details}".strip())


def render_new_release_video_job(render_id: str, project_snapshot: dict[str, Any], platforms: list[dict[str, Any]]) -> None:
    project_id = project_snapshot["id"]
    work_dir = TMP_DIR / f"render-{render_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        update_render(render_id, status="En rendu", progress=2, message="Préparation du visuel Nouvelle sortie")
        set_project_status(project_id, "En rendu")
        assets = create_new_release_assets(project_snapshot, work_dir, platforms, strict=True)
        audio_path = asset_disk_path(project_snapshot.get("audio", {}).get("url", ""))
        if not audio_path:
            raise ValueError("Fichier audio introuvable.")
        ffmpeg_binary = require_ffmpeg()
        track = project_snapshot.get("track", {})
        output_name = f"{slugify(track.get('artist', 'artiste'))}_{slugify(track.get('title', 'titre'))}_nouvelle-sortie_{datetime.now().strftime('%Y%m%d')}_{render_id[:8]}.mp4"
        output_path = RENDER_DIR / output_name

        regions = assets["atlasRegions"]
        inputs: list[str] = [
            "-loop", "1", "-framerate", "30", "-i", str(assets["background"]),
            "-loop", "1", "-framerate", "30", "-i", str(assets["atlas"]),
            "-i", str(audio_path),
        ]
        branches: list[tuple[str, dict[str, Any]]] = [
            ("base", regions["base"]),
            ("header", regions["header"]),
            *[(f"card_{index}", card) for index, card in enumerate(regions.get("cards", []))],
            ("track", regions["track"]),
        ]
        split_outputs = "".join(f"[atlas_{name}_src]" for name, _ in branches)
        filters: list[str] = [
            "[0:v]zoompan=z='min(1.045,1+0.045*on/599)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1350:fps=30,format=rgba[background]",
            f"[1:v]format=rgba,split={len(branches)}{split_outputs}",
        ]
        base = regions["base"]
        filters.append(
            f"[atlas_base_src]crop={base['width']}:{base['height']}:{base['sourceX']}:{base['sourceY']},setpts=PTS-STARTPTS[base_layer]"
        )
        filters.append("[background][base_layer]overlay=0:0:format=auto[scene0]")
        current = "scene0"

        header = regions["header"]
        filters.append(
            f"[atlas_header_src]crop={header['width']}:{header['height']}:{header['sourceX']}:{header['sourceY']},"
            "fade=t=in:st=0.35:d=0.70:alpha=1,setpts=PTS-STARTPTS[header_layer]"
        )
        filters.append(
            f"[{current}][header_layer]overlay=x={header['x']}:y='{header['y']}+6*max(0,1-(t-0.35)/0.70)':format=auto[scene_header]"
        )
        current = "scene_header"

        for index, card in enumerate(regions.get("cards", [])):
            start = 0.78 + index * 0.18
            source = f"atlas_card_{index}_src"
            layer = f"release_card_{index}"
            next_name = f"scene_card_{index}"
            filters.append(
                f"[{source}]crop={card['width']}:{card['height']}:{card['sourceX']}:{card['sourceY']},"
                f"fade=t=in:st={start:.2f}:d=0.65:alpha=1,setpts=PTS-STARTPTS[{layer}]"
            )
            filters.append(
                f"[{current}][{layer}]overlay=x={card['x']}:y='{card['y']}+14*max(0,1-(t-{start:.2f})/0.65)':format=auto[{next_name}]"
            )
            current = next_name

        track_region = regions["track"]
        filters.append(
            f"[atlas_track_src]crop={track_region['width']}:{track_region['height']}:{track_region['sourceX']}:{track_region['sourceY']},"
            "fade=t=in:st=1.05:d=0.78:alpha=1,setpts=PTS-STARTPTS[track_layer]"
        )
        filters.append(
            f"[{current}][track_layer]overlay=x='{track_region['x']}+10*max(0,1-(t-1.05)/0.78)':y={track_region['y']}:format=auto[composed]"
        )
        filters.append("[composed]fade=t=in:st=0:d=0.35,fade=t=out:st=19.25:d=0.75,format=yuv420p[vout]")
        audio_start = max(0.0, float(project_snapshot.get("audio", {}).get("start", 0) or 0))
        filters.append(
            f"[2:a]atrim=start={audio_start:.3f}:duration=20.000,asetpts=PTS-STARTPTS,"
            "afade=t=in:st=0:d=0.06,afade=t=out:st=19.55:d=0.45,aresample=48000,alimiter=limit=0.98[aout]"
        )
        cmd = [
            ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error", "-filter_complex_threads", "1",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "[aout]", "-t", "20.000", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output_path),
        ]
        _run_ffmpeg_progress(render_id, cmd, output_path, 20.0)
        verification = probe_render_output(output_path)
        update_render(
            render_id, status="Terminé", progress=100, message="Rendu terminé",
            outputUrl=f"/media/renders/{output_name}", filename=output_name, verification=verification,
        )
        set_project_status(project_id, "Terminé")
    except Exception as exc:
        traceback.print_exc()
        update_render(render_id, status="Échec", progress=100, message="Échec du rendu", error=str(exc))
        set_project_status(project_id, "Échec")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _ffmpeg_color(value: Any, fallback: str = "#8b5cf6") -> str:
    raw = str(value or fallback)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        raw = fallback
    return "0x" + raw[1:].upper()


def _spectrum_visualizer_recipe(style: str, audio_label: str, project: dict[str, Any]) -> dict[str, Any]:
    """Return one raw (black-background) visualizer recipe shared by preview and export."""
    spectrum = project.get("spectrum", {})
    color_a = _ffmpeg_color(spectrum.get("colorA"), "#8b5cf6")
    color_b = _ffmpeg_color(spectrum.get("colorB"), "#22d3ee")
    color_c = _ffmpeg_color(spectrum.get("colorC"), "#f472b6")
    sensitivity = max(0.55, min(2.0, float(spectrum.get("sensitivity", 1.0) or 1.0)))
    recipe: dict[str, Any] = {
        "style": style,
        "label": "viz_raw",
        "x": 650,
        "y": 700,
        "width": 1100,
        "height": 280,
        "keySimilarity": 0.15,
        "keyBlend": 0.08,
        "alpha": 0.94,
        "filters": [],
    }
    if style == "mirror":
        recipe["filters"] = [
            f"[{audio_label}]showfreqs=s=1100x140:r=30:mode=bar:ascale=sqrt:fscale=log:averaging=2:colors={color_a}|{color_b}[viz_top]",
            "[viz_top]split=2[viz_up][viz_down_src]",
            "[viz_down_src]vflip[viz_down]",
            "[viz_up][viz_down]vstack,format=yuv420p[viz_raw]",
        ]
        recipe.update(keySimilarity=0.16, alpha=0.92)
    elif style == "fluid":
        recipe["filters"] = [
            f"[{audio_label}]showspectrum=s=1100x280:fps=30:slide=replace:mode=combined:color=plasma:scale=sqrt:fscale=log:gain={2.0*sensitivity:.2f}:opacity=1.0,format=yuv420p[viz_raw]"
        ]
        recipe.update(keySimilarity=0.16, alpha=0.88)
    elif style == "led":
        recipe["filters"] = [
            f"[{audio_label}]showfreqs=s=1100x280:r=30:mode=dot:ascale=log:fscale=log:averaging=1:colors={color_a}|{color_b}|{color_c},format=yuv420p[viz_raw]"
        ]
        recipe.update(alpha=0.96)
    elif style == "hill":
        recipe["filters"] = [
            f"[{audio_label}]showwaves=s=1100x260:r=30:mode=line:scale=sqrt:colors={color_a}|{color_b},format=yuv420p[viz_raw]"
        ]
        recipe.update(height=260, keySimilarity=0.14, alpha=0.92)
    elif style == "particles":
        recipe["filters"] = [
            f"[{audio_label}]showspectrum=s=1100x280:fps=30:slide=scroll:mode=combined:color=nebulae:scale=log:fscale=log:gain={2.4*sensitivity:.2f}:opacity=1.0,format=yuv420p[viz_raw]"
        ]
        recipe.update(keySimilarity=0.18, keyBlend=0.10, alpha=0.88)
    else:
        recipe["filters"] = [
            f"[{audio_label}]showfreqs=s=1100x280:r=30:mode=bar:ascale=sqrt:fscale=log:averaging=2:colors={color_a}|{color_b}|{color_c},format=yuv420p[viz_raw]"
        ]
    return recipe


def _spectrum_visualizer_filters(style: str, audio_label: str, project: dict[str, Any]) -> tuple[list[str], str, int, int]:
    """Fallback live filter path; normally export reuses the exact preview visualizer video."""
    recipe = _spectrum_visualizer_recipe(style, audio_label, project)
    filters = list(recipe["filters"])
    filters.append(
        f"[{recipe['label']}]format=rgba,colorkey=0x000000:{recipe['keySimilarity']:.2f}:{recipe['keyBlend']:.2f},"
        f"colorchannelmixer=aa={recipe['alpha']:.2f}[viz]"
    )
    return filters, "viz", int(recipe["x"]), int(recipe["y"])


def _create_spectrum_visualizer_video(
    project: dict[str, Any],
    output_dir: Path,
    audio_path: Path,
    duration: float,
) -> tuple[Path, dict[str, Any]]:
    """Encode the small visualizer once; browser preview and MP4 then share the same frames."""
    style = str(project.get("spectrum", {}).get("style", "bars"))
    recipe = _spectrum_visualizer_recipe(style, "0:a", project)
    output_path = output_dir / "visualizer-preview.mp4"
    ffmpeg_binary = require_ffmpeg()
    filters = [*recipe["filters"], f"[{recipe['label']}]fps=30,format=yuv420p[vout]"]
    command = [
        ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error", "-filter_complex_threads", "1",
        "-i", str(audio_path),
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-an", "-t", f"{duration:.3f}", "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-threads", "2",
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
        "-movflags", "+faststart", str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(120, int(duration * 2 + 60)), check=False)
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 1024:
        message = (result.stderr or "").strip().splitlines()[-1:] or ["visualiseur indisponible"]
        raise ValueError(f"Le visualiseur du spectrum ne peut pas être préparé : {message[0]}")
    geometry = {
        key: recipe[key]
        for key in ("style", "x", "y", "width", "height", "keySimilarity", "keyBlend", "alpha")
    }
    return output_path, geometry


def render_spectrum_video_job(render_id: str, project_snapshot: dict[str, Any], platforms: list[dict[str, Any]]) -> None:
    project_id = project_snapshot["id"]
    work_dir = TMP_DIR / f"render-{render_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        update_render(render_id, status="En rendu", progress=2, message="Préparation du spectrum fidèle")
        set_project_status(project_id, "En rendu")
        assets = create_spectrum_assets(project_snapshot, work_dir, platforms, strict=True)
        audio_path = asset_disk_path(project_snapshot.get("audio", {}).get("url", ""))
        if not audio_path:
            raise ValueError("Fichier audio introuvable.")
        duration = float(project_snapshot.get("audio", {}).get("duration", 0) or 0)
        if duration <= 0:
            duration = probe_audio_duration(audio_path)
        duration = max(0.1, duration)
        ffmpeg_binary = require_ffmpeg()
        track = project_snapshot.get("track", {})
        output_name = f"{slugify(track.get('artist', 'artiste'))}_{slugify(track.get('title', 'titre'))}_spectrum-youtube_{datetime.now().strftime('%Y%m%d')}_{render_id[:8]}.mp4"
        output_path = RENDER_DIR / output_name
        background_video = asset_disk_path(project_snapshot.get("background", {}).get("videoUrl", ""))
        visualizer_video = assets.get("visualizerVideo")
        visualizer_geometry = assets.get("visualizerGeometry") or {}

        inputs: list[str] = []
        animation = str(project_snapshot.get("spectrum", {}).get("backgroundAnimation", "static"))
        use_static_scene = not background_video and animation == "static"
        if use_static_scene:
            inputs.extend(["-loop", "1", "-framerate", "30", "-i", str(assets["scene"])])
            if visualizer_video:
                inputs.extend(["-i", str(visualizer_video)])
                visualizer_index = 1
                inputs.extend(["-i", str(audio_path)])
                audio_index = 2
            else:
                visualizer_index = None
                inputs.extend(["-i", str(audio_path)])
                audio_index = 1
            scene_filters = ["[0:v]scale=1920:1080,format=rgba[scene]"]
        else:
            if background_video:
                inputs.extend(["-stream_loop", "-1", "-i", str(background_video)])
                bg_filter = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=rgba[bg]"
            else:
                inputs.extend(["-loop", "1", "-framerate", "30", "-i", str(assets["background"])])
                if animation == "drift":
                    bg_filter = "[0:v]scale=2035:1145,crop=1920:1080:x='57+40*sin(n/100)':y='32+24*cos(n/130)',fps=30,format=rgba[bg]"
                else:
                    bg_filter = "[0:v]scale=1980:1114,crop=1920:1080:x='30+18*sin(n/75)':y='17+12*cos(n/92)',fps=30,format=rgba[bg]"
            inputs.extend(["-loop", "1", "-framerate", "30", "-i", str(assets["base"])])
            inputs.extend(["-loop", "1", "-framerate", "30", "-i", str(assets["foreground"])])
            if visualizer_video:
                inputs.extend(["-i", str(visualizer_video)])
                visualizer_index = 3
                inputs.extend(["-i", str(audio_path)])
                audio_index = 4
            else:
                visualizer_index = None
                inputs.extend(["-i", str(audio_path)])
                audio_index = 3
            scene_filters = [
                bg_filter,
                "[1:v]format=rgba[base_overlay]",
                "[2:v]format=rgba[foreground]",
                "[bg][base_overlay]overlay=0:0:format=auto[bg_base]",
                "[bg_base][foreground]overlay=0:0:format=auto[scene]",
            ]

        filters: list[str] = [*scene_filters]
        if visualizer_index is not None:
            similarity = float(visualizer_geometry.get("keySimilarity", 0.15))
            blend = float(visualizer_geometry.get("keyBlend", 0.08))
            alpha = float(visualizer_geometry.get("alpha", 0.94))
            viz_x = int(visualizer_geometry.get("x", 650))
            viz_y = int(visualizer_geometry.get("y", 700))
            filters.extend([
                f"[{visualizer_index}:v]fps=30,format=rgba,colorkey=0x000000:{similarity:.2f}:{blend:.2f},colorchannelmixer=aa={alpha:.2f}[viz]",
                f"[scene][viz]overlay=x={viz_x}:y={viz_y}:format=auto[scene_viz]",
                f"[{audio_index}:a]asetpts=PTS-STARTPTS[audio_render]",
            ])
        else:
            filters.append(f"[{audio_index}:a]asplit=2[audio_render][audio_viz]")
            style = str(project_snapshot.get("spectrum", {}).get("style", "bars"))
            viz_filters, viz_label, viz_x, viz_y = _spectrum_visualizer_filters(style, "audio_viz", project_snapshot)
            filters.extend(viz_filters)
            filters.append(f"[scene][{viz_label}]overlay=x={viz_x}:y={viz_y}:format=auto[scene_viz]")

        fade_out_start = max(0.0, duration - 1.0)
        filters.append(f"[scene_viz]fade=t=in:st=0:d=0.45,fade=t=out:st={fade_out_start:.3f}:d=1.0,format=yuv420p[vout]")
        filters.append(
            f"[audio_render]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.08,afade=t=out:st={max(0.0,duration-0.65):.3f}:d=0.65,"
            "aresample=48000,alimiter=limit=0.98[aout]"
        )
        cmd = [
            ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error", "-filter_complex_threads", "0",
            *inputs, "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "[aout]", "-t", f"{duration:.3f}", "-r", "30",
            "-c:v", "libx264", "-preset", "faster", "-crf", "20", "-threads", "0",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output_path),
        ]
        _run_ffmpeg_progress(render_id, cmd, output_path, duration, message="Encodage du spectrum")
        verification = probe_render_output(output_path)
        update_render(
            render_id, status="Terminé", progress=100, message="Rendu terminé",
            outputUrl=f"/media/renders/{output_name}", filename=output_name, verification=verification,
        )
        set_project_status(project_id, "Terminé")
    except Exception as exc:
        traceback.print_exc()
        update_render(render_id, status="Échec", progress=100, message="Échec du rendu", error=str(exc))
        set_project_status(project_id, "Échec")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def render_video_job(render_id: str, project_snapshot: dict[str, Any], platforms: list[dict[str, Any]]) -> None:
    """Dispatch a render to the specialised module while keeping one job API."""
    project_type = project_snapshot.get("type", "playlist_entry")
    if project_type == "new_release":
        render_new_release_video_job(render_id, project_snapshot, platforms)
    elif project_type == "youtube_spectrum":
        render_spectrum_video_job(render_id, project_snapshot, platforms)
    else:
        render_playlist_video_job(render_id, project_snapshot, platforms)


def parse_cookie(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    cookie = SimpleCookie()
    try:
        cookie.load(header)
    except Exception:
        return {}
    return {key: morsel.value for key, morsel in cookie.items()}


def cleanup_sessions() -> None:
    cutoff = time.time() - SESSION_TTL_SECONDS
    with SESSION_LOCK:
        stale = [token for token, item in SESSIONS.items() if item.get("created", 0) < cutoff]
        for token in stale:
            SESSIONS.pop(token, None)




def conversion_type_for_filename(filename: str) -> str | None:
    """Fast classification used before probing; FFmpeg remains the authority."""
    ext = Path(filename).suffix.lower()
    if ext in CONVERT_IMAGE_EXTS:
        return "cover_tiff"
    if ext in CONVERT_VIDEO_EXTS:
        return "video_wav"
    if ext in CONVERT_AUDIO_EXTS:
        return "audio_wav"
    return None


def detect_conversion_type(source_path: Path, original_name: str, content_type: str = "") -> str | None:
    """Detect covers, videos and any audio format decodable by FFmpeg.

    This deliberately does not restrict audio to a short extension list. A file
    with an uncommon container is accepted when FFprobe finds an audio stream.
    """
    content_type = str(content_type or "").lower()
    quick = conversion_type_for_filename(original_name)

    # Pillow is a reliable content check for cover files, regardless of MIME.
    try:
        with Image.open(source_path) as image:
            image.verify()
        return "cover_tiff"
    except Exception:
        pass

    if content_type.startswith("audio/"):
        return "audio_wav"
    if content_type.startswith("video/"):
        return "video_wav"
    if quick in {"audio_wav", "video_wav"}:
        return quick

    ffprobe_binary, _ = resolve_ffprobe_binary()
    if ffprobe_binary:
        try:
            probe = subprocess.run(
                [
                    ffprobe_binary, "-v", "error", "-show_entries",
                    "stream=codec_type", "-of", "json", str(source_path),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if probe.returncode == 0:
                payload = json.loads(probe.stdout or "{}")
                stream_types = [str(item.get("codec_type", "")) for item in payload.get("streams", [])]
                if "audio" in stream_types:
                    # A real video can also contain audio. Unknown audio containers
                    # normally contain no non-attached video stream, so audio-only
                    # files remain in the generic audio path.
                    if "video" in stream_types:
                        return "video_wav"
                    return "audio_wav"
        except Exception:
            pass

    # Last chance for uncommon audio formats when FFprobe is unavailable.
    if MutagenFile is not None:
        try:
            media = MutagenFile(str(source_path))
            if media is not None and getattr(media, "info", None) is not None:
                return "audio_wav"
        except Exception:
            pass

    # Do not reject an uncommon audio extension before FFmpeg has tried it.
    # The conversion worker will return a precise error for non-media files.
    return "audio_wav"

def safe_media_stem(filename: str) -> str:
    stem = Path(filename).stem.strip()
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._")
    return (stem[:110] or "fichier")


def conversion_download_url(filename: str) -> str:
    """Return a URL-safe path while keeping the human-readable filename on disk."""
    return f"/media/conversions/{urllib.parse.quote(filename, safe='')}"


def attachment_content_disposition(filename: str) -> str:
    """Build an ASCII-safe header with an RFC 5987 UTF-8 filename."""
    fallback = filename.encode("ascii", "ignore").decode("ascii")
    fallback = re.sub(r'[\r\n"\\]+', "_", fallback).strip(" .") or "download"
    encoded = urllib.parse.quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def convert_cover_to_tiff(source_path: Path, output_path: Path) -> dict[str, Any]:
    """Create a strict distribution TIFF without an embedded ICC profile."""
    try:
        with Image.open(source_path) as source:
            source = ImageOps.exif_transpose(source)
            # Flatten any alpha/transparency on white before converting to three-channel RGB.
            if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
                rgba = source.convert("RGBA")
                flattened = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                flattened.alpha_composite(rgba)
                rgb = flattened.convert("RGB")
            else:
                rgb = source.convert("RGB")
            converted = ImageOps.fit(
                rgb,
                (3000, 3000),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            # The new RGB image carries no source metadata or profile.
            converted.info.clear()
            converted.save(
                output_path,
                format="TIFF",
                compression="tiff_lzw",
                dpi=(300, 300),
            )
    except Exception as exc:
        raise ValueError("La cover ne peut pas être convertie en TIFF.") from exc

    with Image.open(output_path) as check:
        tags = check.tag_v2
        if check.size != (3000, 3000):
            raise ValueError("Le TIFF généré n’a pas la taille 3000 × 3000 px.")
        if check.mode != "RGB" or len(check.getbands()) != 3:
            raise ValueError("Le TIFF généré n’est pas en RVB trois canaux.")
        if 34675 in tags or check.info.get("icc_profile"):
            raise ValueError("Le profil ICC n’a pas pu être supprimé du TIFF.")
        compression = str(check.info.get("compression", "")).lower()
        if "lzw" not in compression:
            raise ValueError("Le TIFF généré n’utilise pas la compression LZW.")
        dpi = check.info.get("dpi", (300, 300))
        return {
            "kind": "TIFF cover",
            "width": check.width,
            "height": check.height,
            "mode": check.mode,
            "channels": len(check.getbands()),
            "bitsPerChannel": 8,
            "dpi": [round(float(dpi[0])), round(float(dpi[1]))] if isinstance(dpi, tuple) else [300, 300],
            "compression": "LZW",
            "iccTag34675": False,
        }


def convert_media_to_wav(source_path: Path, output_path: Path) -> dict[str, Any]:
    ffmpeg_binary = require_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg_binary,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=60 * 60,
        check=False,
    )
    if result.returncode != 0 or not output_path.exists():
        message = (result.stderr or "").strip().splitlines()[-1:] or ["Aucune piste audio exploitable."]
        raise ValueError(f"Conversion WAV impossible : {message[0]}")
    try:
        with wave.open(str(output_path), "rb") as wav_file:
            if wav_file.getframerate() != 44100 or wav_file.getsampwidth() != 2 or wav_file.getnchannels() != 2:
                raise ValueError("Le WAV généré ne respecte pas 44,1 kHz / 16 bits / stéréo.")
            duration = wav_file.getnframes() / max(1, wav_file.getframerate())
            return {
                "kind": "WAV audio",
                "sampleRate": wav_file.getframerate(),
                "bits": wav_file.getsampwidth() * 8,
                "channels": wav_file.getnchannels(),
                "duration": round(duration, 3),
            }
    except wave.Error as exc:
        raise ValueError("Le WAV généré est illisible.") from exc


def update_conversion(conversion_id: str, **updates: Any) -> None:
    with STORE_LOCK:
        store = load_store()
        job = next((item for item in store.get("conversions", []) if item.get("id") == conversion_id), None)
        if not job:
            return
        job.update(updates)
        job["updatedAt"] = now_iso()
        save_store(store)


def run_conversion_job(conversion_id: str, owner_id: str, input_records: list[dict[str, str]]) -> None:
    del owner_id
    work_dir = CONVERSION_TMP_DIR / conversion_id
    output_dir = work_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    package_type = "file" if len(input_records) == 1 else "zip"
    try:
        update_conversion(conversion_id, status="En cours", progress=3, message="Préparation des fichiers", packageType=package_type)
        total = max(1, len(input_records))
        used_names: set[str] = set()
        for index, record in enumerate(input_records):
            original = record["originalName"]
            source_path = Path(record["path"])
            conversion_type = record.get("conversionType") or "unsupported"
            start_progress = 5 + int(index / total * 82)
            update_conversion(
                conversion_id,
                status="En cours",
                progress=start_progress,
                message=f"Conversion de {original}",
                currentFile=index + 1,
            )
            stem = safe_media_stem(original)
            suffix = ".tiff" if conversion_type == "cover_tiff" else ".wav"
            output_name = f"{stem}{suffix}"
            duplicate = 2
            while output_name.lower() in used_names:
                output_name = f"{stem}_{duplicate}{suffix}"
                duplicate += 1
            used_names.add(output_name.lower())
            output_path = output_dir / output_name
            try:
                if conversion_type == "cover_tiff":
                    verification = convert_cover_to_tiff(source_path, output_path)
                elif conversion_type in {"audio_wav", "video_wav"}:
                    verification = convert_media_to_wav(source_path, output_path)
                else:
                    raise ValueError(record.get("detectionError") or "Format média non reconnu ou non décodable.")
                results.append({
                    "originalName": original,
                    "outputName": output_name,
                    "conversionType": conversion_type,
                    "size": output_path.stat().st_size,
                    "verification": verification,
                })
            except Exception as exc:
                failures.append({"originalName": original, "error": str(exc)})

        if not results:
            reason = failures[0]["error"] if failures else "Aucun fichier n’a pu être converti."
            raise ValueError(reason)

        if package_type == "file":
            update_conversion(conversion_id, progress=92, message="Préparation du fichier", results=results, failures=failures)
            result = results[0]
            source_output = output_dir / result["outputName"]
            base_name = result["outputName"]
            final_name = base_name
            destination = CONVERSION_DIR / final_name
            if destination.exists():
                final_name = f"{Path(base_name).stem}_{conversion_id[:8]}{Path(base_name).suffix}"
                destination = CONVERSION_DIR / final_name
            shutil.copy2(source_output, destination)
            update_conversion(
                conversion_id,
                status="Terminé",
                progress=100,
                message="Fichier converti",
                outputUrl=conversion_download_url(final_name),
                filename=final_name,
                packageType="file",
                outputMime=mimetypes.guess_type(final_name)[0] or "application/octet-stream",
                results=results,
                failures=failures,
                completedAt=now_iso(),
            )
        else:
            update_conversion(conversion_id, progress=90, message="Création de l’archive ZIP", results=results, failures=failures)
            archive_name = f"spectoom_conversions_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{conversion_id[:8]}.zip"
            archive_path = CONVERSION_DIR / archive_name
            report_lines = [
                "Spectoom — rapport de conversion",
                f"Date : {now_iso()}",
                "",
            ]
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for result in results:
                    archive.write(output_dir / result["outputName"], arcname=result["outputName"])
                    report_lines.append(f"OK — {result['originalName']} -> {result['outputName']}")
                for failure in failures:
                    report_lines.append(f"ERREUR — {failure['originalName']} : {failure['error']}")
                archive.writestr("rapport_conversion.txt", "\n".join(report_lines).encode("utf-8"))

            update_conversion(
                conversion_id,
                status="Terminé",
                progress=100,
                message=f"{len(results)} fichier(s) converti(s)",
                outputUrl=conversion_download_url(archive_name),
                filename=archive_name,
                packageType="zip",
                outputMime="application/zip",
                results=results,
                failures=failures,
                completedAt=now_iso(),
            )
    except Exception as exc:
        traceback.print_exc()
        update_conversion(
            conversion_id,
            status="Échec",
            progress=100,
            message="Échec de la conversion",
            error=str(exc),
            packageType=package_type,
            results=results,
            failures=failures,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def login_throttle_key(client_ip: str, email: str) -> str:
    return f"{client_ip}|{email.strip().lower()}"


def login_is_blocked(key: str) -> bool:
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    with LOGIN_LOCK:
        recent = [stamp for stamp in LOGIN_FAILURES.get(key, []) if stamp >= cutoff]
        if recent:
            LOGIN_FAILURES[key] = recent
        else:
            LOGIN_FAILURES.pop(key, None)
        return len(recent) >= LOGIN_MAX_FAILURES


def register_login_failure(key: str) -> None:
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    with LOGIN_LOCK:
        recent = [stamp for stamp in LOGIN_FAILURES.get(key, []) if stamp >= cutoff]
        recent.append(time.time())
        LOGIN_FAILURES[key] = recent[-LOGIN_MAX_FAILURES:]


def clear_login_failures(key: str) -> None:
    with LOGIN_LOCK:
        LOGIN_FAILURES.pop(key, None)


def build_session_cookie(token: str, max_age: int) -> str:
    parts = [
        f"{COOKIE_NAME}={token}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        f"Max-Age={max_age}",
    ]
    if SECURE_COOKIES:
        parts.append("Secure")
    return "; ".join(parts)


class AppHandler(BaseHTTPRequestHandler):
    server_version = f"Spectoom/{APP_VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        return forwarded or self.client_address[0]

    def _send_bytes(self, status: int, payload: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Spectoom-Version", APP_VERSION)
        # This is a local-first application updated by replacing files in place.
        # Never keep stale HTML/JS/CSS or brand assets after an update.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def send_json(self, status: int, data: Any, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, payload, "application/json; charset=utf-8", headers)

    def send_error_json(self, status: int, message: str, details: Any = None) -> None:
        data = {"ok": False, "error": message}
        if details is not None:
            data["details"] = details
        self.send_json(status, data)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_JSON_BODY:
            raise ValueError("Corps JSON invalide ou trop volumineux.")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def current_user(self) -> dict[str, Any] | None:
        cleanup_sessions()
        token = parse_cookie(self.headers.get("Cookie")).get(COOKIE_NAME)
        if not token:
            return None
        with SESSION_LOCK:
            session = SESSIONS.get(token)
        if not session:
            return None
        store = load_store()
        return next((user for user in store.get("users", []) if user.get("id") == session.get("userId")), None)

    def require_user(self) -> dict[str, Any] | None:
        user = self.current_user()
        if not user:
            self.send_error_json(HTTPStatus.UNAUTHORIZED, "Authentification requise.")
            return None
        return user

    def require_admin(self) -> dict[str, Any] | None:
        user = self.require_user()
        if user and user.get("role") != "admin":
            self.send_error_json(HTTPStatus.FORBIDDEN, "Accès administrateur requis.")
            return None
        return user

    def route_parts(self) -> tuple[str, list[str], dict[str, list[str]]]:
        parsed = urllib.parse.urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        query = urllib.parse.parse_qs(parsed.query)
        return parsed.path, parts, query

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path, parts, query = self.route_parts()
        try:
            if path == "/api/health":
                ffmpeg_binary, ffmpeg_source = resolve_ffmpeg_binary()
                ffprobe_binary, ffprobe_source = resolve_ffprobe_binary()
                self.send_json(200, {
                    "ok": True,
                    "service": APP_NAME,
                    "version": APP_VERSION,
                    "ffmpeg": bool(ffmpeg_binary),
                    "ffmpegSource": ffmpeg_source,
                    "ffprobe": bool(ffprobe_binary),
                    "ffprobeSource": ffprobe_source,
                    "mutagen": MutagenFile is not None,
                    "environment": ENVIRONMENT,
                    "storageWritable": os.access(DATA_DIR, os.W_OK),
                })
                return
            if path == "/api/me":
                user = self.current_user()
                if not user:
                    self.send_json(200, {"authenticated": False})
                else:
                    self.send_json(200, {"authenticated": True, "user": self.public_user(user)})
                return
            if path == "/api/config":
                user = self.require_user()
                if not user:
                    return
                store = load_store()
                self.send_json(200, {
                    "app": {"name": APP_NAME, "version": APP_VERSION},
                    "modules": [
                        {"id": "playlist_entry", "name": "Entrées en playlist"},
                        {"id": "new_release", "name": "Nouvelle sortie"},
                        {"id": "youtube_spectrum", "name": "Spectrum YouTube"},
                    ],
                    "platforms": store.get("platforms", []),
                    "presets": store.get("presets", []),
                    "fonts": available_fonts_for_user(store, str(user.get("id", ""))),
                })
                return
            if path == "/api/projects":
                user = self.require_user()
                if not user:
                    return
                store = load_store()
                projects = [p for p in store.get("projects", []) if p.get("ownerId") == user.get("id")]
                projects.sort(key=lambda p: p.get("updatedAt", ""), reverse=True)
                summary = [self.project_summary(p, store.get("renders", [])) for p in projects]
                self.send_json(200, {"projects": summary})
                return
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                store = load_store()
                project = self.find_project(store, project_id, user)
                if not project:
                    self.send_error_json(404, "Projet introuvable.")
                    return
                status, errors = project_completion(project)
                project = json.loads(json.dumps(project))
                project["computedStatus"] = status
                project["validationErrors"] = errors
                self.send_json(200, {"project": project})
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "preview":
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                store = load_store()
                project = self.find_project(store, project_id, user)
                if not project:
                    self.send_error_json(404, "Projet introuvable.")
                    return
                preview = ensure_preview_assets(project, store.get("platforms", []))
                self.send_json(200, {"preview": preview})
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "renders":
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                store = load_store()
                if not self.find_project(store, project_id, user):
                    self.send_error_json(404, "Projet introuvable.")
                    return
                renders = [r for r in store.get("renders", []) if r.get("projectId") == project_id]
                renders.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
                self.send_json(200, {"renders": renders})
                return
            if len(parts) == 3 and parts[:2] == ["api", "renders"]:
                user = self.require_user()
                if not user:
                    return
                render_id = parts[2]
                store = load_store()
                render = next((r for r in store.get("renders", []) if r.get("id") == render_id), None)
                if not render:
                    self.send_error_json(404, "Rendu introuvable.")
                    return
                project = self.find_project(store, render.get("projectId", ""), user, allow_admin=True)
                if not project:
                    self.send_error_json(403, "Accès refusé.")
                    return
                self.send_json(200, {"render": render})
                return
            if path == "/api/conversions":
                user = self.require_user()
                if not user:
                    return
                store = load_store()
                jobs = [item for item in store.get("conversions", []) if item.get("ownerId") == user.get("id")]
                jobs.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
                self.send_json(200, {"conversions": jobs[:50]})
                return
            if len(parts) == 3 and parts[:2] == ["api", "conversions"]:
                user = self.require_user()
                if not user:
                    return
                conversion_id = parts[2]
                store = load_store()
                job = next((item for item in store.get("conversions", []) if item.get("id") == conversion_id), None)
                if not job:
                    self.send_error_json(404, "Conversion introuvable.")
                    return
                if job.get("ownerId") != user.get("id") and user.get("role") != "admin":
                    self.send_error_json(403, "Accès refusé.")
                    return
                self.send_json(200, {"conversion": job})
                return
            if path == "/api/admin/overview":
                user = self.require_admin()
                if not user:
                    return
                store = load_store()
                renders = sorted(store.get("renders", []), key=lambda r: r.get("createdAt", ""), reverse=True)[:50]
                users = [self.public_user(item) for item in store.get("users", [])]
                self.send_json(200, {"platforms": store.get("platforms", []), "renders": renders, "users": users})
                return
            if path.startswith("/media/previews/"):
                user = self.require_user()
                if not user:
                    return
                if len(parts) != 5:
                    self.send_error_json(404, "Aperçu introuvable.")
                    return
                project_id, signature, filename = parts[2], parts[3], parts[4]
                if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id) or not re.fullmatch(r"[a-f0-9]{20}", signature):
                    self.send_error_json(403, "Chemin d’aperçu interdit.")
                    return
                store = load_store()
                if not self.find_project(store, project_id, user, allow_admin=True):
                    self.send_error_json(403, "Accès refusé.")
                    return
                base = (PREVIEW_DIR / project_id / signature).resolve()
                candidate = (base / Path(filename).name).resolve()
                try:
                    candidate.relative_to(base)
                except ValueError:
                    self.send_error_json(403, "Chemin d’aperçu interdit.")
                    return
                self.serve_file(candidate, attachment=False)
                return
            if path.startswith("/media/uploads/"):
                user = self.require_user()
                if not user:
                    return
                filename = Path(path).name
                store = load_store()
                asset = next((item for item in store.get("assets", []) if item.get("storageName") == filename), None)
                if not asset:
                    self.send_error_json(404, "Asset introuvable.")
                    return
                if asset.get("ownerId") != user.get("id") and user.get("role") != "admin":
                    self.send_error_json(403, "Accès refusé.")
                    return
                self.serve_file(UPLOAD_DIR / filename, attachment=False)
                return
            if path.startswith("/media/conversions/"):
                user = self.require_user()
                if not user:
                    return
                encoded_filename = path[len("/media/conversions/"):]
                filename = urllib.parse.unquote(encoded_filename)
                if not filename or "/" in filename or "\\" in filename or Path(filename).name != filename:
                    self.send_error_json(400, "Nom de fichier de conversion invalide.")
                    return
                store = load_store()
                job = next((item for item in store.get("conversions", []) if item.get("filename") == filename), None)
                if not job:
                    self.send_error_json(404, "Fichier de conversion introuvable.")
                    return
                if job.get("ownerId") != user.get("id") and user.get("role") != "admin":
                    self.send_error_json(403, "Accès refusé.")
                    return
                download = query.get("download", ["0"])[0] == "1"
                self.serve_file(CONVERSION_DIR / filename, attachment=download)
                return
            if path.startswith("/media/renders/"):
                user = self.require_user()
                if not user:
                    return
                filename = Path(path).name
                store = load_store()
                render = next((item for item in store.get("renders", []) if item.get("filename") == filename), None)
                if not render:
                    self.send_error_json(404, "Rendu introuvable.")
                    return
                if render.get("ownerId") != user.get("id") and user.get("role") != "admin":
                    self.send_error_json(403, "Accès refusé.")
                    return
                download = query.get("download", ["0"])[0] == "1"
                self.serve_file(RENDER_DIR / filename, attachment=download)
                return
            if path.startswith("/demo/"):
                self.serve_file(STATIC_DIR / "demo" / Path(path).name, attachment=False)
                return
            if path.startswith("/static/"):
                rel = Path(path[len("/static/"):])
                self.serve_static(rel)
                return
            if path == "/" or not path.startswith("/api/"):
                self.serve_file(STATIC_DIR / "index.html", attachment=False)
                return
            self.send_error_json(404, "Route introuvable.")
        except BrokenPipeError:
            return
        except Exception as exc:
            traceback.print_exc()
            self.send_error_json(500, "Erreur serveur.", str(exc))

    def do_POST(self) -> None:
        path, parts, query = self.route_parts()
        try:
            if path == "/api/login":
                data = self.read_json()
                email = str(data.get("email", "")).strip().lower()
                password = str(data.get("password", ""))
                throttle_key = login_throttle_key(self.client_ip(), email)
                if login_is_blocked(throttle_key):
                    self.send_error_json(429, "Trop de tentatives. Réessaie dans quelques minutes.")
                    return
                store = load_store()
                user = next((u for u in store.get("users", []) if u.get("email", "").lower() == email), None)
                if not user or user.get("status") != "active" or not password_verify(password, user.get("passwordHash", "")):
                    register_login_failure(throttle_key)
                    self.send_error_json(401, "E-mail ou mot de passe incorrect.")
                    return
                clear_login_failures(throttle_key)
                token = secrets.token_urlsafe(32)
                with SESSION_LOCK:
                    SESSIONS[token] = {"userId": user["id"], "created": time.time()}
                headers = {"Set-Cookie": build_session_cookie(token, SESSION_TTL_SECONDS)}
                self.send_json(200, {"ok": True, "user": self.public_user(user)}, headers)
                return
            if path == "/api/logout":
                token = parse_cookie(self.headers.get("Cookie")).get(COOKIE_NAME)
                if token:
                    with SESSION_LOCK:
                        SESSIONS.pop(token, None)
                self.send_json(200, {"ok": True}, {"Set-Cookie": build_session_cookie("", 0)})
                return
            if path == "/api/projects":
                user = self.require_user()
                if not user:
                    return
                data = self.read_json() if int(self.headers.get("Content-Length", "0") or 0) else {}
                project = default_project(user["id"], str(data.get("name", "Nouveau projet"))[:100], str(data.get("type", "playlist_entry")))
                with STORE_LOCK:
                    store = load_store()
                    store.setdefault("projects", []).append(project)
                    save_store(store)
                self.send_json(201, {"project": project})
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "duplicate":
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                with STORE_LOCK:
                    store = load_store()
                    source = self.find_project(store, project_id, user)
                    if not source:
                        self.send_error_json(404, "Projet introuvable.")
                        return
                    clone = json.loads(json.dumps(source))
                    clone["id"] = str(uuid.uuid4())
                    clone["name"] = f"{source.get('name', 'Projet')} — copie"
                    clone["status"] = "Brouillon"
                    clone["createdAt"] = now_iso()
                    clone["updatedAt"] = now_iso()
                    for item in clone.get("playlists", []):
                        item["id"] = str(uuid.uuid4())
                    store.setdefault("projects", []).append(clone)
                    save_store(store)
                self.send_json(201, {"project": clone})
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "render":
                user = self.require_user()
                if not user:
                    return
                try:
                    require_ffmpeg()
                except MediaToolUnavailable as exc:
                    self.send_error_json(503, str(exc))
                    return
                project_id = parts[2]
                with STORE_LOCK:
                    store = load_store()
                    project = self.find_project(store, project_id, user)
                    if not project:
                        self.send_error_json(404, "Projet introuvable.")
                        return
                    status, errors = project_completion(project)
                    if status != "Prêt":
                        self.send_error_json(422, "Le projet contient des erreurs bloquantes.", errors)
                        return
                    render = {
                        "id": str(uuid.uuid4()),
                        "projectId": project_id,
                        "projectType": project.get("type", "playlist_entry"),
                        "ownerId": user["id"],
                        "revision": 1 + sum(1 for r in store.get("renders", []) if r.get("projectId") == project_id),
                        "status": "En attente",
                        "progress": 0,
                        "message": "Dans la file de rendu",
                        "outputUrl": "",
                        "filename": "",
                        "error": "",
                        "createdAt": now_iso(),
                        "updatedAt": now_iso(),
                    }
                    store.setdefault("renders", []).append(render)
                    project["status"] = "En rendu"
                    project["updatedAt"] = now_iso()
                    project_snapshot = json.loads(json.dumps(project))
                    platforms = json.loads(json.dumps(store.get("platforms", [])))
                    save_store(store)
                thread = threading.Thread(target=render_video_job, args=(render["id"], project_snapshot, platforms), daemon=True)
                thread.start()
                self.send_json(202, {"render": render})
                return
            if path == "/api/conversions":
                user = self.require_user()
                if not user:
                    return
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                if content_length <= 0 or content_length > MAX_CONVERSION_BODY:
                    self.send_error_json(413, "Lot trop volumineux : limite totale de 520 Mo.")
                    return
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self.send_error_json(400, "Requête multipart requise.")
                    return
                body = self.rfile.read(content_length)
                message = BytesParser(policy=policy.default).parsebytes(
                    b"Content-Type: " + ctype.encode("utf-8") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
                )
                received: list[tuple[str, bytes, str]] = []
                for part in message.iter_parts():
                    params = dict(part.get_params(header="Content-Disposition", failobj=[]))
                    if params.get("filename") is None:
                        continue
                    filename = Path(str(params.get("filename"))).name
                    payload = part.get_payload(decode=True) or b""
                    content_type = str(part.get_content_type() or "application/octet-stream")
                    if not filename or not payload:
                        continue
                    if len(payload) > 500 * 1024 * 1024:
                        self.send_error_json(413, f"Fichier trop volumineux : {filename}")
                        return
                    received.append((filename, payload, content_type))
                if not received:
                    self.send_error_json(400, "Aucun fichier compatible reçu.")
                    return
                if len(received) > 30:
                    self.send_error_json(422, "Un lot est limité à 30 fichiers.")
                    return

                conversion_id = str(uuid.uuid4())
                work_dir = CONVERSION_TMP_DIR / conversion_id
                work_dir.mkdir(parents=True, exist_ok=True)
                input_records: list[dict[str, str]] = []
                file_summaries: list[dict[str, Any]] = []
                try:
                    for index, (filename, payload, content_type) in enumerate(received, start=1):
                        ext = Path(filename).suffix.lower()
                        safe_ext = ext if re.fullmatch(r"\.[a-z0-9]{1,10}", ext) else ".bin"
                        input_path = work_dir / f"input-{index:03d}{safe_ext}"
                        input_path.write_bytes(payload)
                        conversion_type = detect_conversion_type(input_path, filename, content_type)
                        record = {
                            "originalName": filename,
                            "path": str(input_path),
                            "conversionType": conversion_type or "unsupported",
                            "contentType": content_type,
                        }
                        if not conversion_type:
                            record["detectionError"] = "Le fichier n’est pas une image ou un média audio/vidéo décodable par FFmpeg."
                        input_records.append(record)
                        file_summaries.append({
                            "name": filename,
                            "size": len(payload),
                            "contentType": content_type,
                            "conversionType": conversion_type or "unsupported",
                        })
                    job = {
                        "id": conversion_id,
                        "ownerId": user.get("id"),
                        "status": "En attente",
                        "progress": 0,
                        "message": "Dans la file de conversion",
                        "fileCount": len(input_records),
                        "packageType": "file" if len(input_records) == 1 else "zip",
                        "currentFile": 0,
                        "files": file_summaries,
                        "results": [],
                        "failures": [],
                        "outputUrl": "",
                        "filename": "",
                        "error": "",
                        "createdAt": now_iso(),
                        "updatedAt": now_iso(),
                    }
                    with STORE_LOCK:
                        store = load_store()
                        store.setdefault("conversions", []).append(job)
                        save_store(store)
                    thread = threading.Thread(
                        target=run_conversion_job,
                        args=(conversion_id, str(user.get("id", "")), input_records),
                        daemon=True,
                    )
                    thread.start()
                    self.send_json(202, {"conversion": job})
                except Exception:
                    shutil.rmtree(work_dir, ignore_errors=True)
                    raise
                return
            if path == "/api/upload":
                user = self.require_user()
                if not user:
                    return
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                if content_length <= 0 or content_length > MAX_UPLOAD_BODY:
                    self.send_error_json(413, "Fichier trop volumineux.")
                    return
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self.send_error_json(400, "Requête multipart requise.")
                    return
                body = self.rfile.read(content_length)
                message = BytesParser(policy=policy.default).parsebytes(
                    b"Content-Type: " + ctype.encode("utf-8") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
                )
                fields: dict[str, str] = {}
                filename = ""
                payload = b""
                for part in message.iter_parts():
                    disposition = part.get("Content-Disposition", "")
                    params = dict(part.get_params(header="Content-Disposition", failobj=[]))
                    name = params.get("name")
                    if not name:
                        continue
                    if params.get("filename") is not None:
                        filename = Path(str(params.get("filename"))).name
                        payload = part.get_payload(decode=True) or b""
                    else:
                        fields[str(name)] = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
                kind = fields.get("kind", "background")
                project_id = fields.get("projectId", "")
                if project_id:
                    store = load_store()
                    if not self.find_project(store, project_id, user):
                        self.send_error_json(403, "Projet inaccessible.")
                        return
                if not filename or not payload:
                    self.send_error_json(400, "Aucun fichier reçu.")
                    return
                valid, error = validate_upload(filename, payload, kind)
                if not valid:
                    self.send_error_json(422, error)
                    return
                ext = Path(filename).suffix.lower()
                stored_name = f"{uuid.uuid4().hex}{ext}"
                path_out = UPLOAD_DIR / stored_name
                path_out.write_bytes(payload)
                if kind == "logo" and ext == ".svg":
                    try:
                        path_out = rasterize_svg(path_out)
                        stored_name = path_out.name
                    except MediaToolUnavailable as exc:
                        path_out.unlink(missing_ok=True)
                        self.send_error_json(503, str(exc))
                        return
                    except ValueError as exc:
                        path_out.unlink(missing_ok=True)
                        self.send_error_json(422, str(exc))
                        return
                try:
                    metadata = media_metadata(path_out, kind)
                    if kind == "font":
                        metadata["fontName"] = safe_media_stem(filename)
                except MediaToolUnavailable as exc:
                    path_out.unlink(missing_ok=True)
                    self.send_error_json(503, str(exc))
                    return
                except ValueError as exc:
                    path_out.unlink(missing_ok=True)
                    self.send_error_json(422, str(exc))
                    return
                warnings: list[str] = []
                if kind == "background" and metadata.get("width") and metadata.get("height"):
                    if metadata["width"] < 720 or metadata["height"] < 900:
                        path_out.unlink(missing_ok=True)
                        self.send_error_json(422, "Image trop petite : minimum 720 × 900 px.")
                        return
                    if metadata["width"] < 1080 or metadata["height"] < 1350:
                        warnings.append("Résolution inférieure à 1080 × 1350 : le rendu peut manquer de netteté.")
                if kind == "track-cover" and metadata.get("width") and min(metadata["width"], metadata["height"]) < 500:
                    path_out.unlink(missing_ok=True)
                    self.send_error_json(422, "Pochette trop petite : minimum 500 × 500 px.")
                    return
                if kind == "playlist-cover" and metadata.get("width") and min(metadata["width"], metadata["height"]) < 300:
                    path_out.unlink(missing_ok=True)
                    self.send_error_json(422, "Couverture trop petite : minimum 300 × 300 px.")
                    return
                if kind == "audio" and float(metadata.get("duration", 0) or 0) < 20:
                    path_out.unlink(missing_ok=True)
                    self.send_error_json(422, "Le fichier audio doit durer au moins 20 secondes.")
                    return
                asset_url = f"/media/uploads/{stored_name}"
                font_entry: dict[str, Any] | None = None
                with STORE_LOCK:
                    store = load_store()
                    asset_id = str(uuid.uuid4())
                    store.setdefault("assets", []).append({
                        "id": asset_id,
                        "ownerId": user.get("id"),
                        "projectId": project_id or None,
                        "kind": kind,
                        "originalName": filename,
                        "storageName": stored_name,
                        "url": asset_url,
                        "mime": mimetypes.guess_type(stored_name)[0] or "application/octet-stream",
                        "size": path_out.stat().st_size,
                        **metadata,
                        "createdAt": now_iso(),
                    })
                    if kind == "font":
                        font_entry = {
                            "id": str(uuid.uuid4()),
                            "ownerId": user.get("id"),
                            "assetId": asset_id,
                            "name": metadata.get("fontName") or safe_media_stem(filename),
                            "url": asset_url,
                            "cssFamily": f"SpectoomCustom-{stored_name.rsplit('.', 1)[0]}",
                            "builtIn": False,
                            "active": True,
                            "originalName": filename,
                            "createdAt": now_iso(),
                        }
                        store.setdefault("fonts", []).append(font_entry)
                    save_store(store)
                response_asset = {
                    "url": asset_url,
                    "filename": filename,
                    "kind": kind,
                    "size": len(payload),
                    **metadata,
                    "warnings": warnings,
                }
                if font_entry:
                    response_asset["font"] = font_entry
                self.send_json(201, {"ok": True, "asset": response_asset})
                return
            self.send_error_json(404, "Route introuvable.")
        except json.JSONDecodeError:
            self.send_error_json(400, "JSON invalide.")
        except BrokenPipeError:
            return
        except Exception as exc:
            traceback.print_exc()
            self.send_error_json(500, "Erreur serveur.", str(exc))

    def do_PUT(self) -> None:
        path, parts, _query = self.route_parts()
        try:
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                data = self.read_json()
                incoming = data.get("project", data)
                with STORE_LOCK:
                    store = load_store()
                    project = self.find_project(store, project_id, user)
                    if not project:
                        self.send_error_json(404, "Projet introuvable.")
                        return
                    immutable = {"id": project["id"], "ownerId": project["ownerId"], "createdAt": project["createdAt"]}
                    allowed_keys = {"name", "type", "track", "background", "playlists", "branding", "typography", "newRelease", "spectrum", "audio", "templateVersion"}
                    for key in allowed_keys:
                        if key in incoming:
                            project[key] = incoming[key]
                    project.update(immutable)
                    project["name"] = str(project.get("name", "Nouveau projet"))[:100]
                    project["playlists"] = list(project.get("playlists", []))[:6] if project.get("type", "playlist_entry") == "playlist_entry" else list(project.get("playlists", []))
                    project["updatedAt"] = now_iso()
                    status, errors = project_completion(project)
                    if project.get("status") not in {"En rendu", "Échec"}:
                        project["status"] = status
                    save_store(store)
                self.send_json(200, {"ok": True, "project": project, "validationErrors": errors})
                return
            if len(parts) == 4 and parts[:3] == ["api", "admin", "platforms"]:
                user = self.require_admin()
                if not user:
                    return
                platform_id = parts[3]
                data = self.read_json()
                with STORE_LOCK:
                    store = load_store()
                    platform = next((p for p in store.get("platforms", []) if p.get("id") == platform_id), None)
                    if not platform:
                        self.send_error_json(404, "Plateforme introuvable.")
                        return
                    for key in ("name", "short", "active", "order"):
                        if key in data:
                            platform[key] = data[key]
                    save_store(store)
                self.send_json(200, {"ok": True, "platform": platform})
                return
            self.send_error_json(404, "Route introuvable.")
        except Exception as exc:
            traceback.print_exc()
            self.send_error_json(500, "Erreur serveur.", str(exc))

    def do_DELETE(self) -> None:
        path, parts, _query = self.route_parts()
        try:
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                user = self.require_user()
                if not user:
                    return
                project_id = parts[2]
                with STORE_LOCK:
                    store = load_store()
                    project = self.find_project(store, project_id, user)
                    if not project:
                        self.send_error_json(404, "Projet introuvable.")
                        return
                    store["projects"] = [p for p in store.get("projects", []) if p.get("id") != project_id]
                    save_store(store)
                self.send_json(200, {"ok": True})
                return
            self.send_error_json(404, "Route introuvable.")
        except Exception as exc:
            traceback.print_exc()
            self.send_error_json(500, "Erreur serveur.", str(exc))

    def public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return {key: user.get(key) for key in ("id", "name", "email", "role", "status")}

    def find_project(self, store: dict[str, Any], project_id: str, user: dict[str, Any], allow_admin: bool = False) -> dict[str, Any] | None:
        project = next((p for p in store.get("projects", []) if p.get("id") == project_id), None)
        if not project:
            return None
        if project.get("ownerId") == user.get("id"):
            return project
        if allow_admin and user.get("role") == "admin":
            return project
        return None

    def project_summary(self, project: dict[str, Any], renders: list[dict[str, Any]]) -> dict[str, Any]:
        project_renders = [r for r in renders if r.get("projectId") == project.get("id")]
        latest = max(project_renders, key=lambda r: r.get("createdAt", ""), default=None)
        return {
            "id": project.get("id"),
            "name": project.get("name"),
            "status": project.get("status"),
            "updatedAt": project.get("updatedAt"),
            "createdAt": project.get("createdAt"),
            "type": project.get("type", "playlist_entry"),
            "track": project.get("track"),
            "background": project.get("background"),
            "newRelease": project.get("newRelease", {}),
            "spectrum": project.get("spectrum", {}),
            "audio": project.get("audio", {}),
            "playlistsCount": len(project.get("playlists", [])),
            "latestRender": latest,
        }

    def serve_static(self, rel: Path) -> None:
        try:
            full = (STATIC_DIR / rel).resolve()
            full.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self.send_error_json(403, "Chemin interdit.")
            return
        self.serve_file(full, attachment=False)

    def serve_file(self, path: Path, attachment: bool = False) -> None:
        if not path.exists() or not path.is_file():
            if str(path).endswith("index.html"):
                self.send_error_json(500, "Le frontend n’est pas installé.")
            else:
                self.send_error_json(404, "Fichier introuvable.")
            return
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or "application/octet-stream"
        stat = path.stat()
        range_header = self.headers.get("Range")
        if range_header and (content_type.startswith("video/") or content_type.startswith("audio/")):
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start = int(match.group(1) or 0)
                end = int(match.group(2) or stat.st_size - 1)
                end = min(end, stat.st_size - 1)
                if start <= end:
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Content-Range", f"bytes {start}-{end}/{stat.st_size}")
                    self.send_header("Accept-Ranges", "bytes")
                    if attachment:
                        self.send_header("Content-Disposition", attachment_content_disposition(path.name))
                    self.end_headers()
                    if self.command != "HEAD":
                        with path.open("rb") as handle:
                            handle.seek(start)
                            remaining = length
                            while remaining > 0:
                                chunk = handle.read(min(64 * 1024, remaining))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                    return
        headers: dict[str, str] = {"Accept-Ranges": "bytes"}
        if attachment:
            headers["Content-Disposition"] = attachment_content_disposition(path.name)
        self._send_bytes(200, path.read_bytes(), content_type, headers)


def main() -> None:
    if not STORE_PATH.exists():
        init_store()
    sync_bootstrap_accounts()
    ffmpeg_binary, ffmpeg_source = resolve_ffmpeg_binary(refresh=True)
    ffprobe_binary, ffprobe_source = resolve_ffprobe_binary(refresh=True)
    if ffmpeg_binary:
        print(f"Moteur FFmpeg : {ffmpeg_source} ({ffmpeg_binary})")
    else:
        print("AVERTISSEMENT : FFmpeg est indisponible.")
        print("Relancez run.bat afin d’installer automatiquement le moteur audio/vidéo.")
    if ffprobe_binary:
        print(f"Analyse FFprobe : {ffprobe_source} ({ffprobe_binary})")
    else:
        print("FFprobe absent : l’application utilisera FFmpeg/Mutagen pour l’analyse média.")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"{APP_NAME} {APP_VERSION} démarré sur http://{host}:{port}")
    print(f"Environnement : {ENVIRONMENT} | Données : {DATA_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
