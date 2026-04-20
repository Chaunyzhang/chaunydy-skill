from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL
from browser_prep import probe_playwright_browser, scan_browser_environment, select_login_browser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dy_impl.api_client import DouyinAPIClient
from dy_impl.url_parser import URLParser
from prepare_state import read_prepare_state
from dy_utils import parse_url_type, validate_url
DATA_DIR = Path.home() / ".local" / "share" / "chaunydy-skill"
OUTPUT_DIR = ROOT / "out"
PROFILE_ROOT = DATA_DIR / "browser-profiles"
USER_DATA_DIR = DATA_DIR / "browser-profile"
COOKIE_JSON = DATA_DIR / "cookies.json"
COOKIE_TXT = DATA_DIR / "cookies.txt"
PREP_STATE = DATA_DIR / "prepare-state.json"
PREP_PROBE_VIDEO_URL = "https://www.douyin.com/video/7604129988555574538"
PREP_PROBE_SEARCH_KEYWORD = "动画"
COOKIE_FILE_CANDIDATES = [
    COOKIE_TXT,
    ROOT / "cookies.txt",
]
BROWSER_JSON_COOKIE_CANDIDATES = [
    COOKIE_JSON,
    ROOT / "cookies.json",
]
BROWSER_CANDIDATES = ["chrome", "edge", "brave", "firefox"]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)


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


def looks_logged_in(cookies: list[dict[str, Any]]) -> bool:
    names = {str(cookie.get("name", "") or "").strip() for cookie in cookies}
    required = {"passport_csrf_token", "passport_csrf_token_default", "ttwid"}
    if not required.issubset(names):
        return False
    return any(name in names for name in ["odin_tt", "sid_guard", "sessionid_ss", "uid_tt", "sid_tt"])


def cookie_health_snapshot() -> dict[str, Any]:
    cookies = load_cookie_list()
    cookie_names = sorted(str(cookie.get("name", "") or "").strip() for cookie in cookies if cookie.get("name"))
    return {
        "cookie_json": str(COOKIE_JSON),
        "cookie_txt": str(COOKIE_TXT),
        "cookie_json_exists": COOKIE_JSON.is_file(),
        "cookie_txt_exists": COOKIE_TXT.is_file(),
        "cookie_count": len(cookies),
        "looks_logged_in": looks_logged_in(cookies),
        "cookie_name_preview": cookie_names[:12],
        "cookie_json_mtime": COOKIE_JSON.stat().st_mtime if COOKIE_JSON.is_file() else None,
        "cookie_txt_mtime": COOKIE_TXT.stat().st_mtime if COOKIE_TXT.is_file() else None,
    }


def runtime_signature_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    cookies = snapshot.get("cookies", {})
    signature = {
        "preferred_login_browser": snapshot.get("preferred_login_browser"),
        "preferred_login_profile_dir": snapshot.get("preferred_login_profile_dir"),
        "cookie_json_exists": cookies.get("cookie_json_exists"),
        "cookie_txt_exists": cookies.get("cookie_txt_exists"),
        "cookie_count": cookies.get("cookie_count"),
        "looks_logged_in": cookies.get("looks_logged_in"),
        "cookie_json_mtime": cookies.get("cookie_json_mtime"),
        "cookie_txt_mtime": cookies.get("cookie_txt_mtime"),
    }
    digest = hashlib.sha256(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {**signature, "digest": digest}


def prepare_state_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = read_prepare_state(PREP_STATE)
    current_signature = runtime_signature_from_snapshot(snapshot)
    saved_signature = state.get("runtime_signature", {}) if isinstance(state, dict) else {}
    signature_matches = bool(saved_signature) and saved_signature.get("digest") == current_signature.get("digest")
    capabilities = state.get("capabilities", {}) if isinstance(state, dict) else {}
    return {
        "state_file": str(PREP_STATE),
        "state_exists": PREP_STATE.is_file(),
        "updated_at": state.get("updated_at"),
        "selected_browser": state.get("selected_browser"),
        "user_data_dir": state.get("user_data_dir"),
        "signature_matches": signature_matches,
        "capabilities": capabilities,
        "blockers": state.get("blockers", []),
        "prepared_workflows_ready": bool(capabilities) and all(bool((capabilities.get(name) or {}).get("ready")) for name in ["metadata", "download", "comments", "reactions", "search"]),
    }


def capability_gate(capability: str) -> dict[str, Any]:
    snapshot = health_snapshot(include_prepare_state=False)
    prepare_summary = prepare_state_summary(snapshot)
    capabilities = prepare_summary.get("capabilities", {})
    capability_state = capabilities.get(capability) if isinstance(capabilities, dict) else None
    if not prepare_summary.get("state_exists"):
        return {
            "ready": False,
            "message": f"No prepare-state file found. Run python scripts/dy_prepare.py before using the {capability} workflow.",
            "status_snapshot": snapshot,
            "prepare_summary": prepare_summary,
        }
    if not prepare_summary.get("signature_matches"):
        return {
            "ready": False,
            "message": f"Prepare-state no longer matches the current browser/cookie environment. Rerun python scripts/dy_prepare.py before using the {capability} workflow.",
            "status_snapshot": snapshot,
            "prepare_summary": prepare_summary,
        }
    if not isinstance(capability_state, dict) or not capability_state.get("ready"):
        return {
            "ready": False,
            "message": (capability_state or {}).get("message") or f"{capability} is not prepared yet. Run python scripts/dy_prepare.py.",
            "status_snapshot": snapshot,
            "prepare_summary": prepare_summary,
        }
    if capability in {"metadata", "download", "comments", "reactions", "search"}:
        try:
            plan = select_login_browser(PROFILE_ROOT, USER_DATA_DIR, requested_browser=prepare_summary.get("selected_browser") or "auto")
            launch_probe = probe_playwright_browser(selected_browser=plan, headless=True, target_url="about:blank", wait_ms=300)
        except Exception as exc:
            launch_probe = {"success": False, "message": str(exc)}
        if not launch_probe.get("success"):
            return {
                "ready": False,
                "message": "Prepared browser runtime is no longer launchable. Close conflicting dedicated browser windows and rerun python scripts/dy_prepare.py.",
                "status_snapshot": snapshot,
                "prepare_summary": {**prepare_summary, "launch_probe": launch_probe},
            }
    return {
        "ready": True,
        "message": "",
        "status_snapshot": snapshot,
        "prepare_summary": prepare_summary,
    }


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


def _extract_render_payload_text(page: Any) -> str:
    selectors = [
        "#RENDER_DATA",
        "script#RENDER_DATA",
        "#__UNIVERSAL_DATA_FOR_REHYDRATION__",
        "script#__UNIVERSAL_DATA_FOR_REHYDRATION__",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                text = locator.first.text_content()
                if text and text.strip():
                    return text
        except Exception:
            continue
    return ""


def normalize_aweme_detail(detail: dict[str, Any], *, source: str, webpage_url: str, page_title: str = "", browser_profile: str = "", browser_user_data_dir: str = "") -> dict[str, Any]:
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    stats = detail.get("statistics") if isinstance(detail.get("statistics"), dict) else {}
    video = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    desc = detail.get("desc") or detail.get("preview_title") or page_title
    return {
        "id": detail.get("aweme_id", "") or detail.get("group_id", ""),
        "title": desc,
        "description": detail.get("desc", "") or desc,
        "uploader": author.get("nickname", ""),
        "uploader_id": author.get("sec_uid", "") or author.get("uid", ""),
        "duration": int((video.get("duration") or 0) / 1000) if video.get("duration") else 0,
        "view_count": stats.get("play_count", 0),
        "like_count": stats.get("digg_count", 0),
        "comment_count": stats.get("comment_count", 0),
        "timestamp": detail.get("create_time", 0),
        "webpage_url": webpage_url,
        "ext": "mp4",
        "_raw_aweme": detail,
        "_source": source,
        "_page_title": page_title,
        "_browser_profile": browser_profile,
        "_browser_user_data_dir": browser_user_data_dir,
    }


def probe_browser_login_state(browser_name: str = "auto", timeout_ms: int = 6000) -> dict[str, Any]:
    info = extract_info_browser(PREP_PROBE_VIDEO_URL, wait_ms=timeout_ms, browser_name=browser_name, headless=True)
    return {
        "success": bool(info and info.get("id")),
        "message": "Dedicated browser login state looks usable." if info and info.get("id") else "Dedicated browser login state could not be confirmed from the browser probe.",
        "info": normalize_info(info) if info else None,
    }


def extract_info_browser(url: str, wait_ms: int = 8000, browser_name: str = "auto", headless: bool = True) -> dict[str, Any] | None:
    ensure_directories()
    try:
        launch_plan = select_login_browser(PROFILE_ROOT, USER_DATA_DIR, requested_browser=browser_name)
    except Exception:
        return None
    with sync_playwright() as p:
        context = None
        try:
            launch_kwargs = {
                "user_data_dir": launch_plan["user_data_dir"],
                "headless": headless,
            }
            if launch_plan.get("playwright_channel"):
                launch_kwargs["channel"] = launch_plan["playwright_channel"]
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            page = context.new_page()
            detail_payload: dict[str, Any] | None = None

            def on_response(resp: Any) -> None:
                nonlocal detail_payload
                if detail_payload is not None:
                    return
                response_url = str(getattr(resp, "url", "") or "")
                if "/aweme/v1/web/aweme/detail/" not in response_url:
                    return
                try:
                    payload = resp.json()
                except Exception:
                    return
                if isinstance(payload, dict) and isinstance(payload.get("aweme_detail"), dict):
                    detail_payload = payload["aweme_detail"]

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(max(wait_ms, 10000))
            final_url = page.url
            try:
                title = page.title()
            except Exception:
                title = ""
            if detail_payload:
                return normalize_aweme_detail(
                    detail_payload,
                    source="browser_detail_api",
                    webpage_url=final_url,
                    page_title=title,
                    browser_profile=launch_plan["selected_browser"],
                    browser_user_data_dir=launch_plan["user_data_dir"],
                )
            render_text = _extract_render_payload_text(page)
            if not render_text:
                return None
            render_data = json.loads(unquote(render_text))
            aweme = _find_aweme_candidate(render_data)
            if not aweme:
                return None
            return normalize_aweme_detail(
                aweme,
                source="browser_render_data",
                webpage_url=final_url,
                page_title=title,
                browser_profile=launch_plan["selected_browser"],
                browser_user_data_dir=launch_plan["user_data_dir"],
            )
        except Exception:
            return None
        finally:
            try:
                context.close()
            except Exception:
                pass


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
    browser_info = extract_info_browser(url, browser_name=browser_cookie_source or "auto")
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
    browser_info = extract_info_browser(url, browser_name=browser_cookie_source or "auto")
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


def health_snapshot(*, include_prepare_state: bool = True) -> dict[str, Any]:
    ensure_directories()
    browser_cookie_source = pick_browser_cookie_source()
    browser_scan = scan_browser_environment(PROFILE_ROOT, USER_DATA_DIR)
    cookie_state = cookie_health_snapshot()
    preferred_browser = browser_scan.get("preferred_browser") or {}
    base_ready = bool(cookie_state["looks_logged_in"] and preferred_browser.get("name"))
    payload = {
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "yt_dlp_ready": True,
        "ffmpeg_present": bool(shutil.which("ffmpeg")),
        "preferred_login_browser": preferred_browser.get("name"),
        "preferred_login_profile_dir": preferred_browser.get("dedicated_profile_dir"),
        "dedicated_browser_scan": browser_scan.get("browsers", []),
        "cookies": cookie_state,
        "cookie_file": preferred_cookie_file(),
        "browser_cookie_source": browser_cookie_source,
        "read_only_ready": bool(preferred_browser.get("name")),
        "write_actions_default": "disabled",
        "needs_login": not cookie_state["looks_logged_in"],
        "login_hint": (
            "Run python scripts/dy_login.py and only continue after you personally see the dedicated Douyin login window."
            if not cookie_state["looks_logged_in"]
            else ""
        ),
        "doctor_hint": "Run python scripts/dy_doctor.py --json before first use on a new machine.",
        "base_ready": base_ready,
        "all_ready": base_ready,
    }
    payload["runtime_signature"] = runtime_signature_from_snapshot(payload)
    if include_prepare_state:
        payload["prepare_state"] = prepare_state_summary(payload)
        payload["prepared_workflows_ready"] = payload["prepare_state"].get("prepared_workflows_ready", False)
        payload["all_ready"] = bool(
            base_ready
            and payload["prepare_state"].get("state_exists")
            and payload["prepare_state"].get("signature_matches")
            and payload["prepared_workflows_ready"]
        )
    return payload
