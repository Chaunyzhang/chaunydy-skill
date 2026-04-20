#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from browser_prep import select_login_browser
from dy_comments import fetch_comments
from dy_core import (
    PREP_PROBE_SEARCH_KEYWORD,
    PREP_PROBE_VIDEO_URL,
    PREP_STATE,
    PROFILE_ROOT,
    USER_DATA_DIR,
    extract_info_browser,
    health_snapshot,
    load_cookie_dict,
    probe_browser_login_state,
    runtime_signature_from_snapshot,
)
from dy_impl.api_client import DouyinAPIClient
from dy_login import login_and_export_cookies
from dy_reactions import read_reaction_state
from prepare_state import default_prepare_state, set_capability, set_phase, write_prepare_state


EXIT_READY = 0
EXIT_FAILED = 1
EXIT_NEEDS_HUMAN_ACTION = 2


def search_human_handoff(state: Dict[str, Any]) -> Dict[str, Any] | None:
    search_verify = (state.get("phases", {}).get("search_verify") or {})
    if search_verify.get("status") != "needs_human_action":
        return None
    details = search_verify.get("details") or {}
    keyword = details.get("keyword") or PREP_PROBE_SEARCH_KEYWORD
    return {
        "type": "search_verify_check",
        "keyword": keyword,
        "commands": [
            "python scripts/dy_search_verify.py",
            "python scripts/dy_prepare.py",
        ],
        "message": details.get("message")
        or "Search needs human verification in the dedicated browser before prepare can finish.",
    }


def prepare_status(state: Dict[str, Any]) -> str:
    if search_human_handoff(state):
        return "needs_human_action"
    if state.get("blockers"):
        return "failed"
    capabilities = state.get("capabilities", {})
    if all(bool((capabilities.get(name) or {}).get("ready")) for name in ["metadata", "comments", "reactions", "search"]):
        return "ready"
    return "failed"


def prepare_payload(state: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    capabilities = state.get("capabilities", {})
    blockers = state.get("blockers", [])
    handoff = search_human_handoff(state)
    status = prepare_status(state)
    payload = {
        "success": status == "ready",
        "status": status,
        "human_action_required": bool(handoff),
        "human_action": handoff,
        "state_file": str(PREP_STATE),
        "selected_browser": state.get("selected_browser"),
        "user_data_dir": state.get("user_data_dir"),
        "runtime_signature": state.get("runtime_signature"),
        "phases": state.get("phases", {}),
        "capabilities": capabilities,
        "blockers": blockers,
        "status_snapshot": {
            "needs_login": snapshot.get("needs_login"),
            "all_ready": snapshot.get("all_ready"),
            "prepare_state": snapshot.get("prepare_state", {}),
        },
        "next_actions": build_next_actions_from_state(state),
    }
    return payload


def build_next_actions_from_state(state: Dict[str, Any]) -> list[str]:
    caps = state.get("capabilities", {})
    actions: list[str] = []
    if (state.get("phases", {}).get("login_confirm") or {}).get("status") == "failed":
        actions.append("Dedicated browser login state is not confirmed. Run python scripts/dy_login.py and complete login in the visible dedicated browser window.")
    if not (caps.get("metadata") or {}).get("ready"):
        actions.append("Fix metadata readiness first. Rerun: python scripts/dy_prepare.py")
    if not (caps.get("comments") or {}).get("ready"):
        actions.append("Comments are not ready. Rerun prepare or inspect the comments_probe failure details.")
    if not (caps.get("reactions") or {}).get("ready"):
        actions.append("Reactions are not ready. Rerun prepare or inspect the reactions_probe failure details.")
    search_handoff = search_human_handoff(state)
    if search_handoff:
        actions.append(f"Search needs human verification. Run: {search_handoff['commands'][0]}")
        actions.append(f"After the dedicated browser verification succeeds, rerun: {search_handoff['commands'][1]}")
    elif not (caps.get("search") or {}).get("ready"):
        actions.append("Search is not ready yet. Rerun prepare or inspect the search_probe failure details.")
    if not actions:
        actions.append("Preparation passed. You can continue with dy_info.py, dy_download.py, dy_comments.py, and dy_reactions.py.")
    return actions


async def probe_search_readiness(keyword: str) -> Dict[str, Any]:
    cookies = load_cookie_dict()
    if not cookies:
        return {"success": False, "message": "No usable Douyin cookies loaded for search probe."}
    async with DouyinAPIClient(cookies) as client:
        data = await client.probe_search(keyword=keyword, count=5)
    verify_needed = ((data.get("search_nil_info") or {}).get("search_nil_type") == "verify_check")
    items = data.get("data") or []
    return {
        "success": bool(items) and not verify_needed,
        "verify_needed": verify_needed,
        "count": len(items),
        "message": (
            "Douyin search returned verify_check. The dedicated browser likely still needs a human verification step for search."
            if verify_needed
            else "Search probe succeeded."
            if items
            else "Search probe returned no items."
        ),
        "raw": {
            "status_code": data.get("status_code"),
            "has_more": data.get("has_more"),
            "search_nil_info": data.get("search_nil_info"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare dedicated browser state and verify read-only Douyin workflow readiness.")
    parser.add_argument("--browser", default="auto", help="Preferred dedicated browser: auto, chrome, edge, chromium")
    parser.add_argument("--force-login", action="store_true", help="Force an interactive login even if cookies already look usable")
    args = parser.parse_args()

    state = default_prepare_state()
    blockers: list[str] = []

    try:
        launch_plan = select_login_browser(PROFILE_ROOT, USER_DATA_DIR, requested_browser=args.browser)
        state["selected_browser"] = launch_plan["selected_browser"]
        state["user_data_dir"] = launch_plan["user_data_dir"]
        set_phase(state, "browser_prepare", "ready", launch_plan)
        write_prepare_state(PREP_STATE, state)
    except Exception as exc:
        set_phase(state, "browser_prepare", "failed", {"message": str(exc)})
        blockers.append(f"browser_prepare failed: {exc}")
        state["blockers"] = blockers
        write_prepare_state(PREP_STATE, state)
        print(json.dumps(prepare_payload(state, health_snapshot()), ensure_ascii=False, indent=2))
        return 1

    snapshot = health_snapshot()
    login_probe = probe_browser_login_state(browser_name=args.browser, timeout_ms=3000) if not args.force_login else {"success": False, "message": "Forced login requested."}
    login_confirmed = bool(login_probe.get("success"))
    set_phase(state, "login_confirm", "ready" if login_confirmed else "failed", login_probe)
    write_prepare_state(PREP_STATE, state)

    if args.force_login or snapshot.get("needs_login") or not login_confirmed:
        login_result = login_and_export_cookies(requested_browser=args.browser, timeout_seconds=300, emit_progress=True)
        if not login_result.get("success"):
            set_phase(state, "login", "failed", login_result)
            blockers.append(login_result.get("message") or "login failed")
            state["blockers"] = blockers
            write_prepare_state(PREP_STATE, state)
            print(json.dumps(prepare_payload(state, health_snapshot()), ensure_ascii=False, indent=2))
            return 1
        set_phase(state, "login", "ready", login_result)
        write_prepare_state(PREP_STATE, state)
        login_probe = probe_browser_login_state(browser_name=args.browser, timeout_ms=6000)
        login_confirmed = bool(login_probe.get("success"))
        set_phase(state, "login_confirm", "ready" if login_confirmed else "failed", login_probe)
        write_prepare_state(PREP_STATE, state)
        if not login_confirmed:
            blockers.append("dedicated browser login state is still not confirmed after login")
            state["blockers"] = blockers
            write_prepare_state(PREP_STATE, state)
            print(json.dumps(prepare_payload(state, health_snapshot()), ensure_ascii=False, indent=2))
            return 1
    else:
        set_phase(state, "login", "ready", {"message": "Existing cookies already look usable."})
        write_prepare_state(PREP_STATE, state)

    snapshot = health_snapshot()
    state["runtime_signature"] = runtime_signature_from_snapshot(snapshot)

    metadata_info = extract_info_browser(PREP_PROBE_VIDEO_URL, browser_name=args.browser, headless=True)
    metadata_ready = bool(metadata_info and metadata_info.get("id"))
    set_phase(
        state,
        "metadata_probe",
        "ready" if metadata_ready else "failed",
        {"probe_url": PREP_PROBE_VIDEO_URL, "result": metadata_info or {"message": "No metadata returned from browser probe."}},
    )
    set_capability(
        state,
        "metadata",
        metadata_ready,
        "Metadata probe succeeded." if metadata_ready else "Metadata probe failed. Browser environment is not fully ready.",
        {"probe_url": PREP_PROBE_VIDEO_URL},
    )
    set_capability(
        state,
        "download",
        metadata_ready,
        "Download uses the same readiness foundation as metadata." if metadata_ready else "Download is blocked until metadata readiness passes.",
        {"probe_url": PREP_PROBE_VIDEO_URL},
    )
    write_prepare_state(PREP_STATE, state)

    comments_result = asyncio.run(fetch_comments(PREP_PROBE_VIDEO_URL, count=1))
    comments_ready = bool(comments_result.get("success"))
    set_phase(state, "comments_probe", "ready" if comments_ready else "failed", comments_result)
    set_capability(
        state,
        "comments",
        comments_ready,
        "Comments probe succeeded." if comments_ready else comments_result.get("message") or "Comments probe failed.",
        {"probe_url": PREP_PROBE_VIDEO_URL},
    )
    write_prepare_state(PREP_STATE, state)

    reactions_result = asyncio.run(read_reaction_state(PREP_PROBE_VIDEO_URL))
    reactions_ready = bool(reactions_result.get("success"))
    set_phase(state, "reactions_probe", "ready" if reactions_ready else "failed", reactions_result)
    set_capability(
        state,
        "reactions",
        reactions_ready,
        "Reactions probe succeeded." if reactions_ready else reactions_result.get("message") or "Reactions probe failed.",
        {"probe_url": PREP_PROBE_VIDEO_URL},
    )
    write_prepare_state(PREP_STATE, state)

    search_result = asyncio.run(probe_search_readiness(PREP_PROBE_SEARCH_KEYWORD))
    search_ready = bool(search_result.get("success"))
    set_phase(state, "search_probe", "ready" if search_ready else "failed", search_result)
    set_capability(
        state,
        "search",
        search_ready,
        search_result.get("message") or ("Search probe succeeded." if search_ready else "Search probe failed."),
        {"probe_keyword": PREP_PROBE_SEARCH_KEYWORD},
    )
    if search_result.get("verify_needed"):
        set_phase(
            state,
            "search_verify",
            "needs_human_action",
            {
                "success": False,
                "verification_type": "search_verify_check",
                "keyword": PREP_PROBE_SEARCH_KEYWORD,
                "commands": [
                    "python scripts/dy_search_verify.py",
                    "python scripts/dy_prepare.py",
                ],
                "message": "Search needs human verification in the dedicated browser. Run python scripts/dy_search_verify.py and then rerun python scripts/dy_prepare.py.",
            },
        )
    else:
        set_phase(state, "search_verify", "ready" if search_ready else "pending", {"message": "No separate search verification step is currently required."})
    write_prepare_state(PREP_STATE, state)

    if not metadata_ready:
        blockers.append("metadata readiness failed")
    if not comments_ready:
        blockers.append("comments readiness failed")
    if not reactions_ready:
        blockers.append("reactions readiness failed")
    if not search_ready:
        blockers.append("search human verification required" if search_result.get("verify_needed") else "search readiness failed")
    state["blockers"] = blockers
    write_prepare_state(PREP_STATE, state)

    final_snapshot = health_snapshot()
    payload = prepare_payload(state, final_snapshot)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get("success"):
        return EXIT_READY
    if payload.get("human_action_required"):
        return EXIT_NEEDS_HUMAN_ACTION
    return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
