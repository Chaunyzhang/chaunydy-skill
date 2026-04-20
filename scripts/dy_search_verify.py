#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from urllib.parse import quote

from browser_prep import select_login_browser
from dy_core import PREP_PROBE_SEARCH_KEYWORD, PROFILE_ROOT, USER_DATA_DIR
from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the dedicated Douyin search page and keep it visible for human verification.")
    parser.add_argument("--browser", default="auto", help="Preferred dedicated browser: auto, chrome, edge, chromium")
    parser.add_argument("--keyword", default=PREP_PROBE_SEARCH_KEYWORD, help="Search keyword to open for verification")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    launch_plan = select_login_browser(PROFILE_ROOT, USER_DATA_DIR, requested_browser=args.browser)
    search_url = f"https://www.douyin.com/search/{quote(args.keyword)}?type=video"

    print("Opening the dedicated Douyin search verification window now.")
    print("Please complete the captcha / human verification in the visible dedicated browser window.")
    print("After you believe the search page is usable, close the window and rerun: python scripts/dy_prepare.py")

    deadline = time.time() + max(args.timeout_seconds, 30)
    with sync_playwright() as p:
        launch_kwargs = {
            "user_data_dir": launch_plan["user_data_dir"],
            "headless": False,
        }
        if launch_plan.get("playwright_channel"):
            launch_kwargs["channel"] = launch_plan["playwright_channel"]
        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.new_page()
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(3000)
            print(
                json.dumps(
                    {
                        "success": True,
                        "window_ready": True,
                        "verification_type": "search_verify_check",
                        "selected_browser": launch_plan["selected_browser"],
                        "user_data_dir": launch_plan["user_data_dir"],
                        "current_url": page.url,
                        "page_title": page.title(),
                        "human_action_required": "Complete the captcha in this dedicated window. Then close the window yourself and rerun dy_prepare.py.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            while time.time() < deadline and not page.is_closed():
                page.wait_for_timeout(1000)
            if page.is_closed():
                return 0
            print("Timed out while waiting for manual search verification. You can still close the window and rerun dy_prepare.py later.")
            return 1
        finally:
            try:
                context.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
