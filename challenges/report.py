#!/usr/bin/env python3
"""Print challenges/results.json as a terminal table."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results.json"


def main() -> int:
    if not RESULTS.exists():
        print("No results yet. Run: make challenge L=all", file=sys.stderr)
        return 1

    rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not rows:
        print("results.json is empty.")
        return 0

    headers = ("LEVEL", "CHALLENGE", "SYSTEM", "STATUS", "MS", "ERROR")
    widths = [5, 22, 12, 8, 6, 40]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))

    for row in rows:
        if row.get("partial"):
            status = "PARTIAL"
        elif row.get("passed"):
            status = "PASS"
        else:
            status = "FAIL"
        err = (row.get("error") or "")[:40]
        print(
            f"{row['level']:<5}  "
            f"{row['challenge_name']:<22}  "
            f"{row['system']:<12}  "
            f"{status:<8}  "
            f"{row['response_time_ms']:<6}  "
            f"{err}"
        )

    passed = sum(1 for r in rows if r.get("passed"))
    print(f"\nTotal: {passed}/{len(rows)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
