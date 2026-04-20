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
import dy_core  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
