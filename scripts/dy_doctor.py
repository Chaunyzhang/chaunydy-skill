#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from browser_prep import probe_playwright_browser, select_login_browser
from dy_core import DATA_DIR, OUTPUT_DIR, PROFILE_ROOT, USER_DATA_DIR, health_snapshot


def build_next_actions(snapshot: Dict[str, Any], probe: Dict[str, Any] | None) -> List[str]:
    actions: List[str] = []
    if not snapshot.get("preferred_login_browser"):
        actions.append("Install Chrome or Edge, or install Playwright Chromium, then rerun: python scripts/dy_doctor.py --json")
    if probe and not probe.get("success"):
        actions.append("Browser launch probe failed. Fix the reported browser/channel issue before attempting login.")
    if snapshot.get("needs_login"):
        actions.append("Run: python scripts/dy_login.py")
        actions.append("Only continue after a human personally sees the dedicated Douyin login window.")
    else:
        actions.append("Login cookies look usable. You can continue with: python scripts/dy_info.py \"<douyin_url>\"")
    if not snapshot.get("ffmpeg_present"):
        actions.append("Install ffmpeg if you plan to transcribe local video files.")
    return actions


def doctor_snapshot(requested_browser: str = "auto", probe_window: bool = False) -> Dict[str, Any]:
    snapshot = health_snapshot()
    probe_result: Dict[str, Any] | None = None
    selected_browser_name = snapshot.get("preferred_login_browser")
    if selected_browser_name:
        try:
            plan = select_login_browser(PROFILE_ROOT, USER_DATA_DIR, requested_browser=requested_browser)
            probe_result = probe_playwright_browser(
                selected_browser=plan,
                headless=not probe_window,
                target_url="about:blank" if not probe_window else "https://www.douyin.com/",
                wait_ms=1200 if not probe_window else 2500,
            )
        except Exception as exc:
            probe_result = {
                "success": False,
                "requested_browser": requested_browser,
                "selected_browser": selected_browser_name,
                "headless": not probe_window,
                "message": str(exc),
            }

    blockers: List[str] = []
    if not snapshot.get("preferred_login_browser"):
        blockers.append("No dedicated browser candidate is available.")
    if probe_result and not probe_result.get("success"):
        blockers.append("Preferred dedicated browser could not be launched by Playwright.")

    return {
        "success": len(blockers) == 0,
        "doctor_version": 1,
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "paths": {
            "data_dir": str(DATA_DIR),
            "output_dir": str(OUTPUT_DIR),
            "profile_root": str(PROFILE_ROOT),
            "legacy_profile_dir": str(USER_DATA_DIR),
        },
        "runtime": {
            "ffmpeg_present": snapshot.get("ffmpeg_present"),
            "yt_dlp_module_ready": True,
            "playwright_ready": True,
            "dashscope_installed": _module_present("dashscope"),
            "requests_installed": _module_present("requests"),
        },
        "browser_preflight": {
            "requested_browser": requested_browser,
            "preferred_login_browser": snapshot.get("preferred_login_browser"),
            "dedicated_browser_scan": snapshot.get("dedicated_browser_scan", []),
            "launch_probe": probe_result,
            "probe_mode": "visible_window" if probe_window else "headless_preflight",
        },
        "cookies": snapshot.get("cookies", {}),
        "status": {
            "needs_login": snapshot.get("needs_login"),
            "all_ready": snapshot.get("all_ready"),
            "read_only_ready": snapshot.get("read_only_ready"),
        },
        "blockers": blockers,
        "next_actions": build_next_actions(snapshot, probe_result),
        "weak_model_hint": (
            "Run this doctor first on a new machine. If blockers is non-empty, fix blockers before trying dy_login.py or dy_info.py."
        ),
    }


def _module_present(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-check and preflight diagnostics for chaunydy-skill.")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--browser", default="auto", help="Preferred dedicated browser: auto, chrome, edge, chromium")
    parser.add_argument("--probe-window", action="store_true", help="Open a visible browser window during the preflight probe")
    args = parser.parse_args()

    payload = doctor_snapshot(requested_browser=args.browser, probe_window=args.probe_window)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
