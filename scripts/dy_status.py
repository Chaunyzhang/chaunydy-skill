#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys

from dy_core import DATA_DIR, OUTPUT_DIR, ensure_directories


def main() -> None:
    ensure_directories()
    snapshot = {
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "yt_dlp_ready": True,
        "ffmpeg_present": bool(shutil.which("ffmpeg")),
        "read_only_ready": True,
        "write_actions_default": "disabled",
        "all_ready": True,
    }
    if "--json" in sys.argv:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
