from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse


INVALID_COOKIE_NAME_CHARS = set('()<>@,;:\\"/[]?={} \t\r\n')


def is_valid_cookie_name(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in name):
        return False
    if any(ch in INVALID_COOKIE_NAME_CHARS for ch in name):
        return False
    return True


def sanitize_cookies(cookies: Mapping[Any, Any]) -> Dict[str, str]:
    sanitized: Dict[str, str] = {}
    for raw_key, raw_value in (cookies or {}).items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.strip()
        if not is_valid_cookie_name(key):
            continue
        value = "" if raw_value is None else str(raw_value).strip()
        sanitized[key] = value
    return sanitized


def validate_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except Exception:
        return False


def parse_url_type(url: str) -> Optional[str]:
    if "v.douyin.com" in url:
        return "video"

    path = urlparse(url).path
    if "/video/" in path:
        return "video"
    if "/user/" in path:
        return "user"
    if "/note/" in path or "/gallery/" in path or "/slides/" in path:
        return "gallery"
    if "/collection/" in path or "/mix/" in path:
        return "collection"
    if "/music/" in path:
        return "music"
    return None


def sanitize_filename(filename: str, max_length: int = 80) -> str:
    filename = filename.replace("\n", " ").replace("\r", " ")
    filename = re.sub(r'[<>:"/\\|?*#\x00-\x1f]', "_", filename)
    filename = re.sub(r"[\s_]+", "_", filename)
    filename = filename.strip("._- ")
    if len(filename) > max_length:
        filename = filename[:max_length].rstrip("._- ")
    return filename or "untitled"
