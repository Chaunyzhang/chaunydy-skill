#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dy_impl.api_client import DouyinAPIClient
from scripts.dy_core import get_video_detail_via_api, load_cookie_dict, resolve_aweme_id


def normalize_comment(item: dict) -> dict:
    user = item.get("user") or {}
    replies = []
    for reply in item.get("reply_comment") or []:
        r_user = reply.get("user") or {}
        replies.append(
            {
                "cid": reply.get("cid"),
                "text": reply.get("text", ""),
                "digg_count": reply.get("digg_count", 0),
                "user": r_user.get("nickname", ""),
                "uid": r_user.get("uid", ""),
            }
        )
    return {
        "cid": item.get("cid"),
        "text": item.get("text", ""),
        "digg_count": item.get("digg_count", 0),
        "reply_comment_total": item.get("reply_comment_total", 0),
        "user": user.get("nickname", ""),
        "uid": user.get("uid", ""),
        "replies": replies,
    }


async def fetch_comments(url: str, count: int = 10) -> dict:
    aweme_id = await resolve_aweme_id(url)
    if not aweme_id:
        return {"success": False, "message": "Could not resolve aweme id from URL or short-link path"}

    cookies = load_cookie_dict()
    if not cookies:
        return {"success": False, "message": "No usable Douyin cookies loaded"}

    info = await get_video_detail_via_api(aweme_id)
    async with DouyinAPIClient(cookies) as client:
        data = await client.get_comments(str(aweme_id), cursor=0, count=count)

    comments = data.get("comments") or []
    normalized = [normalize_comment(item) for item in comments if isinstance(item, dict)]
    return {
        "success": bool(normalized),
        "aweme_id": aweme_id,
        "title": (info or {}).get("title", ""),
        "count": len(normalized),
        "comments": normalized,
        "raw_has_more": data.get("has_more", False),
        "source": "signed_api",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Douyin comments workflow")
    parser.add_argument("url")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    result = asyncio.run(fetch_comments(args.url, count=args.count))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
