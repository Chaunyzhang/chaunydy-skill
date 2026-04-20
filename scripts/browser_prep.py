from __future__ import annotations

import json
import os
import subprocess
import time
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


def probe_playwright_browser(
    *,
    selected_browser: Dict[str, Any],
    headless: bool,
    target_url: str = "about:blank",
    wait_ms: int = 1000,
) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = launch_persistent_context_with_retry(p, selected_browser=selected_browser, headless=headless)
        page = context.new_page()
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(max(wait_ms, 0))
            return {
                "success": True,
                "selected_browser": selected_browser["selected_browser"],
                "playwright_channel": selected_browser.get("playwright_channel"),
                "user_data_dir": selected_browser["user_data_dir"],
                "headless": headless,
                "current_url": page.url,
                "page_title": page.title(),
            }
        finally:
            context.close()


def build_launch_kwargs(selected_browser: Dict[str, Any], *, headless: bool) -> Dict[str, Any]:
    launch_kwargs: Dict[str, Any] = {
        "user_data_dir": selected_browser["user_data_dir"],
        "headless": headless,
    }
    if selected_browser.get("playwright_channel"):
        launch_kwargs["channel"] = selected_browser["playwright_channel"]
    return launch_kwargs


def browser_process_name(selected_browser: Dict[str, Any]) -> Optional[str]:
    mapping = {
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
    }
    return mapping.get(str(selected_browser.get("selected_browser", "") or "").lower())


def _escape_powershell_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def find_conflicting_browser_processes(selected_browser: Dict[str, Any], *, only_headless: bool = False) -> List[Dict[str, Any]]:
    process_name = browser_process_name(selected_browser)
    user_data_dir = str(selected_browser.get("user_data_dir", "") or "").strip()
    if not process_name or not user_data_dir or os.name != "nt":
        return []
    headless_clause = ' -and $_.CommandLine -like "*--headless*"' if only_headless else ""
    command = f"""
$processName = '{_escape_powershell_single_quoted(process_name)}'
$userDataDir = '{_escape_powershell_single_quoted(user_data_dir)}'
$needle = "--user-data-dir=$userDataDir"
$items = Get-CimInstance Win32_Process |
  Where-Object {{ $_.Name -eq $processName -and $_.CommandLine -like "*$needle*"{headless_clause} }} |
  Select-Object ProcessId, Name, CommandLine
$items | ConvertTo-Json -Compress
""".strip()
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def cleanup_browser_profile_lockfiles(selected_browser: Dict[str, Any]) -> List[str]:
    removed: List[str] = []
    user_data_dir = Path(str(selected_browser.get("user_data_dir", "") or "").strip())
    if not user_data_dir.exists():
        return removed
    for name in ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
        candidate = user_data_dir / name
        try:
            if candidate.exists():
                candidate.unlink()
                removed.append(str(candidate))
        except Exception:
            continue
    return removed


def terminate_conflicting_browser_processes(selected_browser: Dict[str, Any], *, only_headless: bool = False) -> Dict[str, Any]:
    conflicts = find_conflicting_browser_processes(selected_browser, only_headless=only_headless)
    if not conflicts or os.name != "nt":
        return {"found": 0, "terminated": 0, "removed_lockfiles": []}
    terminated = 0
    for item in conflicts:
        pid = item.get("ProcessId")
        if not pid:
            continue
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {int(pid)} -Force"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            terminated += 1
        except Exception:
            continue
    time.sleep(1.0)
    removed_lockfiles = cleanup_browser_profile_lockfiles(selected_browser)
    return {
        "found": len(conflicts),
        "terminated": terminated,
        "removed_lockfiles": removed_lockfiles,
        "processes": conflicts,
    }


def should_attempt_browser_conflict_recovery(exc: Exception, *, selected_browser: Dict[str, Any], headless: bool) -> bool:
    if not headless:
        return False
    if not browser_process_name(selected_browser):
        return False
    message = str(exc)
    return "Target page, context or browser has been closed" in message


def launch_persistent_context_with_retry(
    playwright: Any,
    *,
    selected_browser: Dict[str, Any],
    headless: bool,
    max_attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> Any:
    last_exc: Optional[Exception] = None
    launch_kwargs = build_launch_kwargs(selected_browser, headless=headless)
    recovery_attempted = False
    for attempt in range(1, max_attempts + 1):
        try:
            return playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not recovery_attempted and should_attempt_browser_conflict_recovery(exc, selected_browser=selected_browser, headless=headless):
                recovery = terminate_conflicting_browser_processes(selected_browser, only_headless=True)
                if recovery.get("terminated") or recovery.get("removed_lockfiles"):
                    recovery_attempted = True
                    continue
            if attempt >= max_attempts:
                break
            time.sleep(retry_delay_seconds)
    raise RuntimeError(
        f"Failed to launch dedicated {selected_browser['selected_browser']} persistent context after {max_attempts} attempts: {last_exc}"
    ) from last_exc
