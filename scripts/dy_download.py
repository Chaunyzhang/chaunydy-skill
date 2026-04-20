#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dy_core import capability_gate, download_media


def main() -> None:
    parser = argparse.ArgumentParser(description="Douyin download workflow")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default=str(Path.cwd() / "out"))
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--browser", default="", help="Optional browser cookie source, e.g. chrome or edge")
    parser.add_argument("--cookie-file", default="", help="Optional Netscape cookies.txt path")
    args = parser.parse_args()

    gate = capability_gate("download")
    if not gate.get("ready"):
        result = {"success": False, "message": gate.get("message"), "prepare_summary": gate.get("prepare_summary")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    result = download_media(
        args.url,
        output_dir=args.output_dir,
        audio_only=args.audio_only,
        browser_cookie_source=args.browser or None,
        cookie_file=args.cookie_file or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
