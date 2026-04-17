from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from .logger import setup_logger
from .ms_token_manager import MsTokenManager
from .xbogus import XBogus
from scripts.dy_utils import sanitize_cookies

logger = setup_logger("DouyinAPIClient")


_USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class DouyinAPIClient:
    BASE_URL = "https://www.douyin.com"

    def __init__(self, cookies: Dict[str, str], proxy: Optional[str] = None):
        self.cookies = sanitize_cookies(cookies or {})
        self.proxy = str(proxy or "").strip()
        self._session: Optional[aiohttp.ClientSession] = None
        selected_ua = random.choice(_USER_AGENT_POOL)
        self.headers = {
            "User-Agent": selected_ua,
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }
        self._signer = XBogus(self.headers["User-Agent"])
        self._ms_token_manager = MsTokenManager(user_agent=self.headers["User-Agent"])
        self._ms_token = (self.cookies.get("msToken") or "").strip()

    async def __aenter__(self) -> "DouyinAPIClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                cookies=self.cookies,
                timeout=aiohttp.ClientTimeout(total=30),
                raise_for_status=False,
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _ensure_ms_token(self) -> str:
        if self._ms_token:
            return self._ms_token
        token = await asyncio.to_thread(self._ms_token_manager.ensure_ms_token, self.cookies)
        self._ms_token = token.strip()
        if self._ms_token:
            self.cookies["msToken"] = self._ms_token
            if self._session and not self._session.closed:
                self._session.cookie_jar.update_cookies({"msToken": self._ms_token})
        return self._ms_token

    async def _default_query(self) -> Dict[str, Any]:
        ms_token = await self._ensure_ms_token()
        return {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "130.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "130.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "12",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "100",
            "msToken": ms_token,
        }

    def sign_url(self, url: str) -> Tuple[str, str]:
        signed_url, _xbogus, ua = self._signer.build(url)
        return signed_url, ua

    def build_signed_path(self, path: str, params: Dict[str, Any]) -> Tuple[str, str]:
        query = urlencode(params)
        base_url = f"{self.BASE_URL}{path}"
        return self.sign_url(f"{base_url}?{query}")

    async def _request_json(self, path: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        await self._ensure_session()
        delays = [1, 2, 5]
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            signed_url, ua = self.build_signed_path(path, params)
            try:
                async with self._session.get(signed_url, headers={**self.headers, "User-Agent": ua}, proxy=self.proxy or None) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        return data if isinstance(data, dict) else {}
                    if response.status < 500 and response.status != 429:
                        return {}
                    last_exc = RuntimeError(f"HTTP {response.status} for {path}")
            except Exception as exc:
                last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
        logger.error("Request failed after %d attempts: path=%s, error=%s", max_retries, path, last_exc)
        return {}

    async def resolve_short_url(self, short_url: str) -> Optional[str]:
        try:
            await self._ensure_session()
            async with self._session.get(short_url, allow_redirects=True, proxy=self.proxy or None) as response:
                return str(response.url)
        except Exception as exc:
            logger.error("Failed to resolve short URL: %s", exc)
            return None

    async def get_video_detail(self, aweme_id: str) -> Optional[Dict[str, Any]]:
        params = await self._default_query()
        params.update({"aweme_id": aweme_id, "aid": "6383"})
        data = await self._request_json("/aweme/v1/web/aweme/detail/", params)
        if data:
            return data.get("aweme_detail")
        return None
