from __future__ import annotations

import re
from typing import Any, Dict, Optional

from scripts.dy_utils import parse_url_type


class URLParser:
    @staticmethod
    def parse(url: str) -> Optional[Dict[str, Any]]:
        url_type = parse_url_type(url)
        if not url_type:
            return None
        result = {"original_url": url, "type": url_type}
        if url_type == "video":
            aweme_id = URLParser._extract_video_id(url)
            if aweme_id:
                result["aweme_id"] = aweme_id
        return result

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        match = re.search(r"/video/(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"modal_id=(\d+)", url)
        if match:
            return match.group(1)
        return None
