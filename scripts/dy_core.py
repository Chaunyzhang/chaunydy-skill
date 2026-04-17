from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path.home() / ".local" / "share" / "chaunydy-skill"
OUTPUT_DIR = ROOT / "out"
BROWSER_CANDIDATES = ["chrome", "edge", "brave", "firefox"]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def pick_browser_cookie_source() -> str | None:
    for browser in BROWSER_CANDIDATES:
        try:
            with YoutubeDL({"cookiesfrombrowser": (browser,)}) as _:
                return browser
        except Exception:
            continue
    return None


def ydl_options(download: bool, output_dir: str, audio_only: bool = False, browser_cookie_source: str | None = None) -> dict[str, Any]:
    ensure_directories()
    opts: dict[str, Any] = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": False,
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
    }
    if not download:
        opts["skip_download"] = True
    elif audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"
    if browser_cookie_source:
        opts["cookiesfrombrowser"] = (browser_cookie_source,)
    return opts


def extract_info(url: str, browser_cookie_source: str | None = None) -> dict[str, Any]:
    with YoutubeDL(ydl_options(download=False, output_dir=str(OUTPUT_DIR), browser_cookie_source=browser_cookie_source)) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


def normalize_info(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "uploader": info.get("uploader", ""),
        "uploader_id": info.get("uploader_id", ""),
        "duration": info.get("duration", 0),
        "view_count": info.get("view_count", 0),
        "like_count": info.get("like_count", 0),
        "comment_count": info.get("comment_count", 0),
        "timestamp": info.get("timestamp", 0),
        "webpage_url": info.get("webpage_url", ""),
        "ext": info.get("ext", ""),
    }


def list_formats(url: str, browser_cookie_source: str | None = None) -> dict[str, Any]:
    info = extract_info(url, browser_cookie_source=browser_cookie_source)
    formats = []
    for item in info.get("formats", []) or []:
        formats.append(
            {
                "format_id": item.get("format_id"),
                "ext": item.get("ext"),
                "resolution": item.get("resolution") or f"{item.get('width', '')}x{item.get('height', '')}",
                "vcodec": item.get("vcodec"),
                "acodec": item.get("acodec"),
                "filesize": item.get("filesize"),
            }
        )
    return {
        "success": True,
        "source_url": url,
        "info": normalize_info(info),
        "formats": formats,
    }


def download_media(url: str, output_dir: str, audio_only: bool = False, browser_cookie_source: str | None = None) -> dict[str, Any]:
    with YoutubeDL(ydl_options(download=True, output_dir=output_dir, audio_only=audio_only, browser_cookie_source=browser_cookie_source)) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = Path(ydl.prepare_filename(info))
        if audio_only:
            file_path = file_path.with_suffix(".mp3")

    exists = file_path.exists()
    size = file_path.stat().st_size if exists else 0
    return {
        "success": exists and size > 0,
        "source_url": url,
        "media_kind": "audio" if audio_only else "video",
        "file_path": str(file_path) if exists else "",
        "file_size_bytes": size,
        "info": normalize_info(info),
    }


def health_snapshot() -> dict[str, Any]:
    ensure_directories()
    browser_cookie_source = pick_browser_cookie_source()
    return {
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "yt_dlp_ready": True,
        "ffmpeg_present": bool(shutil.which("ffmpeg")) if "shutil" in globals() else True,
        "browser_cookie_source": browser_cookie_source,
        "read_only_ready": True,
        "write_actions_default": "disabled",
    }
