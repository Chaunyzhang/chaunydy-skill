#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dy_impl.api_client import DouyinAPIClient
from scripts.dy_core import load_cookie_dict, normalize_aweme_detail


def normalize_search_item(item: dict) -> dict | None:
    aweme = item.get("aweme_info") if isinstance(item.get("aweme_info"), dict) else None
    if not aweme:
        return None
    normalized = normalize_aweme_detail(
        aweme,
        source="search_api",
        webpage_url=f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
    )
    return {
        "id": normalized["id"],
        "title": normalized["title"],
        "description": normalized["description"],
        "uploader": normalized["uploader"],
        "uploader_id": normalized["uploader_id"],
        "duration": normalized["duration"],
        "like_count": normalized["like_count"],
        "comment_count": normalized["comment_count"],
        "timestamp": normalized["timestamp"],
        "webpage_url": normalized["webpage_url"],
    }


async def search_videos(keyword: str, count: int = 10, offset: int = 0) -> dict:
    cookies = load_cookie_dict()
    if not cookies:
        return {
            "success": False,
            "message": "No usable Douyin cookies loaded",
            "keyword": keyword,
        }
    async with DouyinAPIClient(cookies) as client:
        data = await client.search_videos(keyword=keyword, count=count, offset=offset)

    raw_items = data.get("data") or []
    items = [item for item in (normalize_search_item(entry) for entry in raw_items if isinstance(entry, dict)) if item]
    verify_needed = ((data.get("search_nil_info") or {}).get("search_nil_type") == "verify_check")
    result = {
        "success": bool(items),
        "keyword": keyword,
        "count": len(items),
        "items": items,
        "offset": data.get("cursor", offset),
        "has_more": data.get("has_more", 0),
        "source": "search_api",
        "verify_needed": verify_needed,
    }
    if verify_needed and not items:
        result["message"] = (
            "Douyin search API returned verify_check. The current cookies/profile may need a fresh human verification step before keyword search can work."
        )
    elif not items:
        result["message"] = "No search results were returned."
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Douyin keyword video search workflow")
    parser.add_argument("keyword")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    result = asyncio.run(search_videos(args.keyword, count=args.count, offset=args.offset))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
