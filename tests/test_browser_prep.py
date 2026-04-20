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

    def test_should_attempt_browser_conflict_recovery_only_for_headless_channel_browsers(self) -> None:
        exc = RuntimeError("BrowserType.launch_persistent_context: Target page, context or browser has been closed")
        self.assertTrue(
            browser_prep.should_attempt_browser_conflict_recovery(
                exc,
                selected_browser={"selected_browser": "chrome", "user_data_dir": "C:/tmp/chrome"},
                headless=True,
            )
        )
        self.assertFalse(
            browser_prep.should_attempt_browser_conflict_recovery(
                exc,
                selected_browser={"selected_browser": "chrome", "user_data_dir": "C:/tmp/chrome"},
                headless=False,
            )
        )
        self.assertFalse(
            browser_prep.should_attempt_browser_conflict_recovery(
                exc,
                selected_browser={"selected_browser": "chromium", "user_data_dir": "C:/tmp/chromium"},
                headless=True,
            )
        )

    def test_launch_persistent_context_retries_after_conflict_cleanup(self) -> None:
        selected_browser = {"selected_browser": "chrome", "user_data_dir": "C:/tmp/chrome"}
        expected = object()
        chromium = mock.Mock()
        chromium.launch_persistent_context.side_effect = [
            RuntimeError("BrowserType.launch_persistent_context: Target page, context or browser has been closed"),
            expected,
        ]
        playwright = mock.Mock()
        playwright.chromium = chromium
        with mock.patch.object(
            browser_prep,
            "terminate_conflicting_browser_processes",
            return_value={"terminated": 1, "removed_lockfiles": ["C:/tmp/chrome/lockfile"]},
        ) as cleanup, mock.patch.object(browser_prep.time, "sleep"):
            result = browser_prep.launch_persistent_context_with_retry(
                playwright,
                selected_browser=selected_browser,
                headless=True,
                max_attempts=3,
            )
        self.assertIs(result, expected)
        cleanup.assert_called_once_with(selected_browser, only_headless=True)
        self.assertEqual(chromium.launch_persistent_context.call_count, 2)


if __name__ == "__main__":
    unittest.main()
