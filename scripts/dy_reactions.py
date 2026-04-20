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

from scripts.dy_core import capability_gate, extract_info_browser


async def read_reaction_state(url: str) -> dict:
    info = await asyncio.to_thread(extract_info_browser, url)
    if not info or not isinstance(info.get("_raw_aweme"), dict):
        return {"success": False, "message": "Could not resolve Douyin aweme from browser-render-data path"}

    aweme = info["_raw_aweme"]
    stats = (
        aweme.get("statistics")
        if isinstance(aweme.get("statistics"), dict)
        else aweme.get("stats")
        if isinstance(aweme.get("stats"), dict)
        else {}
    )

    return {
        "success": True,
        "aweme_id": info.get("id", ""),
        "title": info.get("title", ""),
        "like_count": stats.get("digg_count", 0) or stats.get("diggCount", 0),
        "collect_count": stats.get("collect_count", 0) or stats.get("collectCount", 0),
        "comment_count": stats.get("comment_count", 0) or stats.get("commentCount", 0),
        "user_digged": aweme.get("userDigged"),
        "user_collected": aweme.get("userCollected"),
        "action_support": "read_state_only",
        "message": "Like and favorite toggle actions are not enabled yet because a stable low-risk browser interaction path has not been verified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Douyin like/favorite state from browser-render-data.")
    parser.add_argument("url")
    args = parser.parse_args()

    gate = capability_gate("reactions")
    if not gate.get("ready"):
        result = {"success": False, "message": gate.get("message"), "prepare_summary": gate.get("prepare_summary")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    result = asyncio.run(read_reaction_state(args.url))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
