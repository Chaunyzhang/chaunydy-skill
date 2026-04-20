#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from dy_core import health_snapshot


def main() -> None:
    snapshot = health_snapshot()
    if "--json" in sys.argv:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
