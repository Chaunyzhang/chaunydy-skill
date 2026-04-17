#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from dy_core import extract_info, list_formats, normalize_info


def main() -> None:
    parser = argparse.ArgumentParser(description="Douyin metadata workflow")
    parser.add_argument("url")
    parser.add_argument("--formats", action="store_true")
    parser.add_argument("--browser", default="", help="Optional browser cookie source, e.g. chrome or edge")
    parser.add_argument("--cookie-file", default="", help="Optional Netscape cookies.txt path")
    args = parser.parse_args()

    if args.formats:
        result = list_formats(args.url, browser_cookie_source=args.browser or None, cookie_file=args.cookie_file or None)
    else:
        info = extract_info(args.url, browser_cookie_source=args.browser or None, cookie_file=args.cookie_file or None)
        result = {"success": True, "source_url": args.url, "info": normalize_info(info)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
