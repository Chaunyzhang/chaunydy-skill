from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dy_impl.api_client import DouyinAPIClient
from dy_impl.url_parser import URLParser
from dy_utils import parse_url_type, validate_url
DATA_DIR = Path.home() / ".local" / "share" / "chaunydy-skill"
OUTPUT_DIR = ROOT / "out"
USER_DATA_DIR = DATA_DIR / "browser-profile"
COOKIE_FILE_CANDIDATES = [
    DATA_DIR / "cookies.txt",
    ROOT / "cookies.txt",
]
BROWSER_JSON_COOKIE_CANDIDATES = [
    DATA_DIR / "cookies.json",
    ROOT / "cookies.json",
]
BROWSER_CANDIDATES = ["chrome", "edge", "brave", "firefox"]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def preferred_cookie_file() -> str | None:
    for candidate in COOKIE_FILE_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def preferred_cookie_json() -> str | None:
    for candidate in BROWSER_JSON_COOKIE_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def load_cookie_dict() -> dict[str, str]:
    cookie_json = preferred_cookie_json()
    if not cookie_json:
        return {}
    try:
        raw = json.loads(Path(cookie_json).read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if k}
    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "").strip()
            value = str(item.get("value", "") or "").strip()
            if name:
                result[name] = value
        return result
    return {}


def load_cookie_list() -> list[dict[str, Any]]:
    cookie_json = preferred_cookie_json()
    if not cookie_json:
        return []
    try:
        raw = json.loads(Path(cookie_json).read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    cookies = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        value = str(item.get("value", "") or "").strip()
        domain = str(item.get("domain", "") or "").strip()
        if not name or not domain:
            continue
        cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": str(item.get("path", "/") or "/"),
            "httpOnly": bool(item.get("httpOnly", False)),
            "secure": bool(item.get("secure", False)),
        }
        try:
            expires = int(item.get("expires", 0) or 0)
            if expires > 0:
                cookie["expires"] = expires
        except Exception:
            pass
        cookies.append(cookie)
    return cookies


async def extract_info_api(url: str) -> dict[str, Any] | None:
    cookies = load_cookie_dict()
    if not cookies:
        return None
    async with DouyinAPIClient(cookies) as client:
        resolved = url
        if url.startswith("https://v.douyin.com"):
            resolved_url = await client.resolve_short_url(url)
            if resolved_url:
                resolved = resolved_url
        parsed = URLParser.parse(resolved)
        if not parsed or not parsed.get("aweme_id"):
            return None
        detail = await client.get_video_detail(parsed["aweme_id"])
        if not detail:
            return None
        return {
            "id": detail.get("aweme_id", ""),
            "title": detail.get("desc", "") or detail.get("preview_title", ""),
            "description": detail.get("desc", ""),
            "uploader": ((detail.get("author") or {}).get("nickname") if isinstance(detail.get("author"), dict) else ""),
            "uploader_id": ((detail.get("author") or {}).get("sec_uid") if isinstance(detail.get("author"), dict) else ""),
            "duration": ((detail.get("video") or {}).get("duration") or 0) // 1000 if isinstance(detail.get("video"), dict) else 0,
            "view_count": (detail.get("statistics") or {}).get("play_count", 0) if isinstance(detail.get("statistics"), dict) else 0,
            "like_count": (detail.get("statistics") or {}).get("digg_count", 0) if isinstance(detail.get("statistics"), dict) else 0,
            "comment_count": (detail.get("statistics") or {}).get("comment_count", 0) if isinstance(detail.get("statistics"), dict) else 0,
            "timestamp": detail.get("create_time", 0),
            "webpage_url": resolved,
            "ext": "mp4",
            "_raw_aweme": detail,
            "_source": "signed_api",
        }


def _find_aweme_candidate(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        video = node.get("video")
        if isinstance(video, dict) and (video.get("playAddr") or video.get("play_addr") or video.get("download_addr")):
            return node
        for value in node.values():
            found = _find_aweme_candidate(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_aweme_candidate(item)
            if found:
                return found
    return None


def extract_info_browser(url: str, wait_ms: int = 8000) -> dict[str, Any] | None:
    ensure_directories()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        cookie_list = load_cookie_list()
        if cookie_list:
            context.add_cookies(cookie_list)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(max(wait_ms, 10000))
            final_url = page.url
            try:
                title = page.title()
            except Exception:
                title = ""
            render_text = page.locator("#RENDER_DATA").text_content()
            if not render_text:
                return None
            render_data = json.loads(unquote(render_text))
            aweme = _find_aweme_candidate(render_data)
            if not aweme:
                return None
            author = (
                aweme.get("author")
                if isinstance(aweme.get("author"), dict)
                else aweme.get("authorInfo")
                if isinstance(aweme.get("authorInfo"), dict)
                else {}
            )
            stats = (
                aweme.get("statistics")
                if isinstance(aweme.get("statistics"), dict)
                else aweme.get("stats")
                if isinstance(aweme.get("stats"), dict)
                else {}
            )
            video = aweme.get("video") if isinstance(aweme.get("video"), dict) else {}
            aweme_id = aweme.get("aweme_id") or aweme.get("awemeId") or aweme.get("groupId") or ""
            desc = aweme.get("desc") or aweme.get("itemTitle") or aweme.get("caption") or title
            uploader = author.get("nickname") or author.get("nickName") or author.get("name") or ""
            uploader_id = author.get("sec_uid") or author.get("secUid") or author.get("uid") or aweme.get("authorUserId") or ""
            return {
                "id": aweme_id,
                "title": desc,
                "description": desc,
                "uploader": uploader,
                "uploader_id": uploader_id,
                "duration": int((video.get("duration") or 0) / 1000) if video.get("duration") else 0,
                "view_count": stats.get("play_count", 0) or stats.get("playCount", 0),
                "like_count": stats.get("digg_count", 0) or stats.get("diggCount", 0),
                "comment_count": stats.get("comment_count", 0) or stats.get("commentCount", 0),
                "timestamp": aweme.get("create_time", 0) or aweme.get("createTime", 0),
                "webpage_url": final_url,
                "ext": "mp4",
                "_raw_aweme": aweme,
                "_source": "browser_render_data",
                "_page_title": title,
            }
        except Exception:
            return None
        finally:
            context.close()
            browser.close()


def _extract_best_url(obj: Any) -> str:
    if isinstance(obj, dict):
        src = obj.get("src")
        if isinstance(src, str) and src:
            return src
        direct_uri = obj.get("uri")
        if isinstance(direct_uri, str) and direct_uri.startswith("http"):
            return direct_uri
        url_list = obj.get("url_list")
        if not isinstance(url_list, list):
            url_list = obj.get("urlList")
        if isinstance(url_list, list):
            for item in url_list:
                if isinstance(item, str) and item:
                    return item
                if isinstance(item, dict):
                    nested_src = item.get("src")
                    if isinstance(nested_src, str) and nested_src:
                        return nested_src
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, str) and item:
                return item
            nested = _extract_best_url(item)
            if nested:
                return nested
    if isinstance(obj, str) and obj:
        return obj
    return ""


def pick_browser_cookie_source() -> str | None:
    for browser in BROWSER_CANDIDATES:
        try:
            with YoutubeDL({"cookiesfrombrowser": (browser,)}) as _:
                return browser
        except Exception:
            continue
    return None


def ydl_options(
    download: bool,
    output_dir: str,
    audio_only: bool = False,
    browser_cookie_source: str | None = None,
    cookie_file: str | None = None,
) -> dict[str, Any]:
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
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if browser_cookie_source:
        opts["cookiesfrombrowser"] = (browser_cookie_source,)
    return opts


def extract_info(url: str, browser_cookie_source: str | None = None, cookie_file: str | None = None) -> dict[str, Any]:
    if not validate_url(url):
        raise SystemExit(f"Invalid URL: {url}")
    browser_info = extract_info_browser(url)
    if browser_info:
        return browser_info
    api_info = asyncio.run(extract_info_api(url))
    if api_info:
        return api_info
    with YoutubeDL(
        ydl_options(
            download=False,
            output_dir=str(OUTPUT_DIR),
            browser_cookie_source=browser_cookie_source,
            cookie_file=cookie_file or preferred_cookie_file(),
        )
    ) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


def normalize_info(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": info.get("_source", "yt_dlp"),
        "source_type": parse_url_type(info.get("webpage_url") or ""),
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


def list_formats(url: str, browser_cookie_source: str | None = None, cookie_file: str | None = None) -> dict[str, Any]:
    info = extract_info(url, browser_cookie_source=browser_cookie_source, cookie_file=cookie_file)
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


def download_media(
    url: str,
    output_dir: str,
    audio_only: bool = False,
    browser_cookie_source: str | None = None,
    cookie_file: str | None = None,
) -> dict[str, Any]:
    if not validate_url(url):
        raise SystemExit(f"Invalid URL: {url}")
    browser_info = extract_info_browser(url)
    if browser_info and isinstance(browser_info.get("_raw_aweme"), dict):
        aweme = browser_info["_raw_aweme"]
        video = aweme.get("video") or {}
        music = aweme.get("music") or {}
        candidate = (
            _extract_best_url(music.get("play_url"))
            or _extract_best_url(music.get("playUrl"))
        ) if audio_only else (
            _extract_best_url(video.get("playAddr"))
            or _extract_best_url(video.get("play_addr"))
            or _extract_best_url(video.get("download_addr"))
        )
        if candidate:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            stem = browser_info.get("title") or browser_info.get("id") or "douyin-media"
            safe_stem = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in str(stem))[:80].strip(" .") or "douyin-media"
            suffix = ".mp3" if audio_only else ".mp4"
            file_path = output_path / f"{safe_stem}{suffix}"
            response = requests.get(candidate, timeout=120, stream=True, headers={"Referer": "https://www.douyin.com/"})
            response.raise_for_status()
            with file_path.open("wb") as handle:
                for chunk in response.iter_content(1024 * 256):
                    if chunk:
                        handle.write(chunk)
            exists = file_path.exists()
            size = file_path.stat().st_size if exists else 0
            return {
                "success": exists and size > 0,
                "source_url": url,
                "media_kind": "audio" if audio_only else "video",
                "file_path": str(file_path) if exists else "",
                "file_size_bytes": size,
                "info": normalize_info(browser_info),
                "source": "browser_render_data",
            }
    api_info = asyncio.run(extract_info_api(url))
    if api_info and isinstance(api_info.get("_raw_aweme"), dict):
        aweme = api_info["_raw_aweme"]
        video = aweme.get("video") or {}
        music = aweme.get("music") or {}
        candidate = _extract_best_url(music.get("play_url")) if audio_only else _extract_best_url(video.get("play_addr")) or _extract_best_url(video.get("download_addr"))
        if candidate:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            stem = api_info.get("title") or api_info.get("id") or "douyin-media"
            safe_stem = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in str(stem))[:80].strip(" .") or "douyin-media"
            suffix = ".mp3" if audio_only else ".mp4"
            file_path = output_path / f"{safe_stem}{suffix}"
            response = requests.get(candidate, timeout=120, stream=True)
            response.raise_for_status()
            with file_path.open("wb") as handle:
                for chunk in response.iter_content(1024 * 256):
                    if chunk:
                        handle.write(chunk)
            exists = file_path.exists()
            size = file_path.stat().st_size if exists else 0
            return {
                "success": exists and size > 0,
                "source_url": url,
                "media_kind": "audio" if audio_only else "video",
                "file_path": str(file_path) if exists else "",
                "file_size_bytes": size,
                "info": normalize_info(api_info),
                "source": "signed_api",
            }
    with YoutubeDL(
        ydl_options(
            download=True,
            output_dir=output_dir,
            audio_only=audio_only,
            browser_cookie_source=browser_cookie_source,
            cookie_file=cookie_file or preferred_cookie_file(),
        )
    ) as ydl:
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
        "ffmpeg_present": bool(shutil.which("ffmpeg")),
        "cookie_file": preferred_cookie_file(),
        "browser_cookie_source": browser_cookie_source,
        "read_only_ready": True,
        "write_actions_default": "disabled",
    }
