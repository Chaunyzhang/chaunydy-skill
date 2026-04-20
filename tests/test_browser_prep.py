from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import browser_prep  # noqa: E402
import dy_doctor  # noqa: E402
import dy_core  # noqa: E402
import dy_prepare  # noqa: E402


class BrowserPreparationTest(unittest.TestCase):
    def test_choose_preferred_browser_prefers_chrome_then_edge_then_chromium(self) -> None:
        browsers = [
            {"name": "edge", "available": True},
            {"name": "chromium", "available": True},
            {"name": "chrome", "available": True},
        ]
        chosen = browser_prep.choose_preferred_browser(browsers)
        self.assertEqual(chosen["name"], "chrome")

    def test_select_login_browser_returns_dedicated_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(
                browser_prep,
                "scan_browser_environment",
                return_value={
                    "browsers": [
                        {
                            "name": "chrome",
                            "available": True,
                            "playwright_channel": "chrome",
                            "system_executable": "C:/Chrome/chrome.exe",
                            "dedicated_profile_dir": str(root / "chrome"),
                        }
                    ],
                    "preferred_browser": {
                        "name": "chrome",
                        "available": True,
                        "playwright_channel": "chrome",
                        "system_executable": "C:/Chrome/chrome.exe",
                        "dedicated_profile_dir": str(root / "chrome"),
                    },
                },
            ):
                plan = browser_prep.select_login_browser(root / "profiles", root / "legacy", requested_browser="auto")
        self.assertEqual(plan["selected_browser"], "chrome")
        self.assertIn("chrome", plan["user_data_dir"])

    def test_looks_logged_in_requires_key_cookie_names(self) -> None:
        cookies = [
            {"name": "passport_csrf_token", "value": "a"},
            {"name": "passport_csrf_token_default", "value": "b"},
            {"name": "ttwid", "value": "c"},
            {"name": "sessionid_ss", "value": "d"},
        ]
        self.assertTrue(dy_core.looks_logged_in(cookies))
        self.assertFalse(dy_core.looks_logged_in(cookies[:-1]))

    def test_doctor_next_actions_asks_for_login_when_needed(self) -> None:
        snapshot = {
            "preferred_login_browser": "chrome",
            "needs_login": True,
            "ffmpeg_present": False,
        }
        actions = dy_doctor.build_next_actions(snapshot, {"success": True})
        self.assertTrue(any("dy_prepare.py" in action for action in actions))
        self.assertTrue(any("ffmpeg" in action for action in actions))

    def test_prepare_payload_marks_search_verify_as_human_action(self) -> None:
        state = {
            "selected_browser": "chrome",
            "user_data_dir": "D:/profiles/chrome",
            "runtime_signature": {"digest": "abc"},
            "phases": {
                "login_confirm": {"status": "ready", "details": {}},
                "search_verify": {
                    "status": "needs_human_action",
                    "details": {
                        "keyword": "动画",
                        "message": "Search needs human verification in the dedicated browser.",
                    },
                },
            },
            "capabilities": {
                "metadata": {"ready": True},
                "download": {"ready": True},
                "comments": {"ready": True},
                "reactions": {"ready": True},
                "search": {"ready": False},
            },
            "blockers": ["search human verification required"],
        }
        payload = dy_prepare.prepare_payload(state, {"needs_login": False, "all_ready": False, "prepare_state": {}})
        self.assertFalse(payload["success"])
        self.assertEqual(payload["status"], "needs_human_action")
        self.assertTrue(payload["human_action_required"])
        self.assertEqual(
            payload["human_action"]["commands"],
            ["python scripts/dy_search_verify.py", "python scripts/dy_prepare.py"],
        )
        self.assertTrue(any("dy_search_verify.py" in action for action in payload["next_actions"]))

    def test_prepare_next_actions_distinguishes_search_handoff_from_failure(self) -> None:
        actions = dy_prepare.build_next_actions_from_state(
            {
                "phases": {
                    "search_verify": {
                        "status": "needs_human_action",
                        "details": {"keyword": "动画"},
                    }
                },
                "capabilities": {
                    "metadata": {"ready": True},
                    "comments": {"ready": True},
                    "reactions": {"ready": True},
                    "search": {"ready": False},
                },
            }
        )
        self.assertEqual(actions[0], "Search needs human verification. Run: python scripts/dy_search_verify.py")
        self.assertEqual(actions[1], "After the dedicated browser verification succeeds, rerun: python scripts/dy_prepare.py")


if __name__ == "__main__":
    unittest.main()
