from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from scripts.dy_utils import sanitize_cookies


class CookieManager:
    def __init__(self, cookie_file: str):
        self.cookie_file = Path(cookie_file)
        self.cookies: Dict[str, str] = {}

    def set_cookies(self, cookies: Dict[str, str]) -> None:
        self.cookies = sanitize_cookies(cookies)
        self.save()

    def load(self) -> Dict[str, str]:
        if self.cookies:
            return self.cookies
        if not self.cookie_file.exists():
            return {}
        try:
            self.cookies = sanitize_cookies(json.loads(self.cookie_file.read_text(encoding="utf-8")))
        except Exception:
            self.cookies = {}
        return self.cookies

    def save(self) -> None:
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_file.write_text(json.dumps(self.cookies, ensure_ascii=False, indent=2), encoding="utf-8")

    def validate(self) -> bool:
        cookies = self.load()
        required = {"ttwid", "passport_csrf_token"}
        return all(cookies.get(key) for key in required)
