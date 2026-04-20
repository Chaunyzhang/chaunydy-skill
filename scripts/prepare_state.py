from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_prepare_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "selected_browser": None,
        "user_data_dir": None,
        "runtime_signature": {},
        "phases": {
            "browser_prepare": {"status": "pending", "details": {}},
            "login": {"status": "pending", "details": {}},
            "metadata_probe": {"status": "pending", "details": {}},
            "comments_probe": {"status": "pending", "details": {}},
            "reactions_probe": {"status": "pending", "details": {}},
            "search_verify": {"status": "pending", "details": {}},
            "search_probe": {"status": "pending", "details": {}},
        },
        "capabilities": {
            "metadata": {"ready": False, "message": "Not prepared yet."},
            "download": {"ready": False, "message": "Not prepared yet."},
            "comments": {"ready": False, "message": "Not prepared yet."},
            "reactions": {"ready": False, "message": "Not prepared yet."},
            "search": {"ready": False, "message": "Not prepared yet."},
        },
        "blockers": [],
    }


def read_prepare_state(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return default_prepare_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_prepare_state()
    state = default_prepare_state()
    if isinstance(raw, dict):
        state.update({k: v for k, v in raw.items() if k in state})
        if isinstance(raw.get("phases"), dict):
            state["phases"].update(raw["phases"])
        if isinstance(raw.get("capabilities"), dict):
            state["capabilities"].update(raw["capabilities"])
    return state


def write_prepare_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(state)
    payload["updated_at"] = utc_now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def set_phase(state: Dict[str, Any], phase: str, status: str, details: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("phases", {})
    state["phases"][phase] = {"status": status, "details": details}
    return state


def set_capability(state: Dict[str, Any], capability: str, ready: bool, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    state.setdefault("capabilities", {})
    state["capabilities"][capability] = {
        "ready": ready,
        "message": message,
        "details": details or {},
    }
    return state
