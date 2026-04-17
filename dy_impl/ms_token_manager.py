from __future__ import annotations

import json
import random
import string
import time
import urllib.request
from http.cookies import SimpleCookie
from threading import Lock
from typing import Any, Dict, Optional

import yaml


class MsTokenManager:
    F2_CONF_URL = "https://raw.githubusercontent.com/Johnserf-Seed/f2/main/f2/conf/conf.yaml"
    _cached_conf: Optional[Dict[str, Any]] = None
    _cached_at: float = 0
    _cache_ttl_seconds: int = 3600
    _lock = Lock()

    def __init__(self, user_agent: str, conf_url: Optional[str] = None, timeout_seconds: int = 15):
        self.user_agent = user_agent
        self.conf_url = conf_url or self.F2_CONF_URL
        self.timeout_seconds = timeout_seconds

    @classmethod
    def is_valid_ms_token(cls, token: Optional[str]) -> bool:
        return bool(token and isinstance(token, str) and len(token.strip()) in (164, 184))

    @classmethod
    def gen_false_ms_token(cls) -> str:
        return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(182)) + "=="

    def ensure_ms_token(self, cookies: Dict[str, str]) -> str:
        current = (cookies or {}).get("msToken", "").strip()
        if current:
            return current
        real = self.gen_real_ms_token()
        if real:
            return real
        return self.gen_false_ms_token()

    def gen_real_ms_token(self) -> Optional[str]:
        conf = self._load_f2_ms_token_conf()
        if not conf:
            return None

        payload = {
            "magic": conf["magic"],
            "version": conf["version"],
            "dataType": conf["dataType"],
            "strData": conf["strData"],
            "ulr": conf["ulr"],
            "tspFromClient": int(time.time() * 1000),
        }
        request = urllib.request.Request(
            conf["url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": self.user_agent},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                token = self._extract_ms_token_from_headers(resp.headers)
            return token if self.is_valid_ms_token(token) else None
        except Exception:
            return None

    def _load_f2_ms_token_conf(self) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            if self._cached_conf and (now - self._cached_at) < self._cache_ttl_seconds:
                return self._cached_conf
        try:
            with urllib.request.urlopen(self.conf_url, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
            data = yaml.safe_load(raw) or {}
            ms_conf = (data.get("f2", {}) or {}).get("douyin", {}).get("msToken", {})
            required = {"url", "magic", "version", "dataType", "ulr", "strData"}
            if not required.issubset(ms_conf.keys()):
                return None
            with self._lock:
                self._cached_conf = ms_conf
                self._cached_at = now
            return ms_conf
        except Exception:
            return None

    @staticmethod
    def _extract_ms_token_from_headers(headers: Any) -> Optional[str]:
        set_cookies = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
        for header in set_cookies or []:
            cookie = SimpleCookie()
            cookie.load(header)
            morsel = cookie.get("msToken")
            if morsel and morsel.value:
                return morsel.value.strip()
        return None
