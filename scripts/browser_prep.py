from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class BrowserSpec:
    name: str
    playwright_channel: Optional[str]
    executable_env_keys: tuple[str, ...]
    executable_candidates: tuple[str, ...]


WINDOWS_BROWSER_SPECS: tuple[BrowserSpec, ...] = (
    BrowserSpec(
        name="chrome",
        playwright_channel="chrome",
        executable_env_keys=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
        executable_candidates=(
            r"Google\Chrome\Application\chrome.exe",
        ),
    ),
    BrowserSpec(
        name="edge",
        playwright_channel="msedge",
        executable_env_keys=("PROGRAMFILES", "PROGRAMFILES(X86)"),
        executable_candidates=(
            r"Microsoft\Edge\Application\msedge.exe",
        ),
    ),
    BrowserSpec(
        name="chromium",
        playwright_channel=None,
        executable_env_keys=(),
        executable_candidates=(),
    ),
)


def _path_exists(path: str) -> bool:
    try:
        return Path(path).is_file()
    except Exception:
        return False


def resolve_system_browser_executable(spec: BrowserSpec) -> Optional[str]:
    for env_key in spec.executable_env_keys:
        base = os.environ.get(env_key, "").strip()
        if not base:
            continue
        for suffix in spec.executable_candidates:
            candidate = str(Path(base) / suffix)
            if _path_exists(candidate):
                return candidate
    return None


def ensure_browser_profile_dirs(profile_root: Path, legacy_profile_dir: Path) -> Dict[str, Path]:
    profile_root.mkdir(parents=True, exist_ok=True)
    legacy_profile_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Path] = {}
    for spec in WINDOWS_BROWSER_SPECS:
        if spec.name == "chromium":
            profile_dir = legacy_profile_dir
        else:
            profile_dir = profile_root / spec.name
            profile_dir.mkdir(parents=True, exist_ok=True)
        result[spec.name] = profile_dir
    return result


def scan_browser_environment(profile_root: Path, legacy_profile_dir: Path) -> Dict[str, Any]:
    profile_dirs = ensure_browser_profile_dirs(profile_root, legacy_profile_dir)
    browsers: List[Dict[str, Any]] = []
    for spec in WINDOWS_BROWSER_SPECS:
        executable = resolve_system_browser_executable(spec)
        profile_dir = profile_dirs[spec.name]
        existing_profile = profile_dir.exists() and any(profile_dir.iterdir())
        browsers.append(
            {
                "name": spec.name,
                "playwright_channel": spec.playwright_channel,
                "system_executable": executable,
                "available": bool(executable) or spec.name == "chromium",
                "dedicated_profile_dir": str(profile_dir),
                "dedicated_profile_exists": existing_profile,
            }
        )
    preferred = choose_preferred_browser(browsers)
    return {
        "browsers": browsers,
        "preferred_browser": preferred,
    }


def choose_preferred_browser(browsers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    preferred_order = ["chrome", "edge", "chromium"]
    by_name = {browser["name"]: browser for browser in browsers}
    for name in preferred_order:
        browser = by_name.get(name)
        if browser and browser.get("available"):
            return browser
    return None


def select_login_browser(
    profile_root: Path,
    legacy_profile_dir: Path,
    requested_browser: str = "auto",
) -> Dict[str, Any]:
    snapshot = scan_browser_environment(profile_root, legacy_profile_dir)
    browsers = {browser["name"]: browser for browser in snapshot["browsers"]}
    requested = (requested_browser or "auto").strip().lower()
    if requested not in {"auto", "chrome", "edge", "chromium"}:
        raise ValueError(f"Unsupported browser choice: {requested_browser}")
    if requested == "auto":
        chosen = snapshot["preferred_browser"]
    else:
        chosen = browsers.get(requested)
        if chosen and not chosen.get("available"):
            chosen = None
    if not chosen:
        raise RuntimeError("No usable dedicated browser environment is available.")
    return {
        "requested_browser": requested,
        "selected_browser": chosen["name"],
        "playwright_channel": chosen.get("playwright_channel"),
        "system_executable": chosen.get("system_executable"),
        "user_data_dir": chosen["dedicated_profile_dir"],
        "browser_scan": snapshot["browsers"],
    }
