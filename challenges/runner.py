#!/usr/bin/env python3
"""Run IAM challenges and write results to challenges/results.json."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

CHALLENGES_DIR = Path(__file__).resolve().parent
RESULTS_FILE = CHALLENGES_DIR / "results.json"

LEVEL_DIRS = {
    1: "level1_basic",
    2: "level2_mfa",
    3: "level3_federation",
    4: "level4_custom_flows",
    5: "level5_authorization",
    6: "level6_hardening",
}


def discover_modules(level: int | None = None) -> list[tuple[int, str, object]]:
    import importlib.util

    sys.path.insert(0, str(CHALLENGES_DIR))
    modules: list[tuple[int, str, object]] = []
    levels = [level] if level else sorted(LEVEL_DIRS)
    for lvl in levels:
        folder = CHALLENGES_DIR / LEVEL_DIRS[lvl]
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "run"):
                modules.append((lvl, path.stem, module))
    if str(CHALLENGES_DIR) in sys.path:
        sys.path.remove(str(CHALLENGES_DIR))
    return modules


def load_existing_results() -> list[dict]:
    if not RESULTS_FILE.exists():
        return []
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


def merge_results(existing: list[dict], new_results: list[dict]) -> list[dict]:
    index = {
        (item["system"], item["level"], item["challenge_name"]): item for item in existing
    }
    for item in new_results:
        index[(item["system"], item["level"], item["challenge_name"])] = item
    return sorted(
        index.values(),
        key=lambda x: (x["level"], x["challenge_name"], x["system"]),
    )


def write_results(results: list[dict]) -> None:
    RESULTS_FILE.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IAM challenge lab tests")
    parser.add_argument("--level", default="all", help="Level number 1-6 or 'all'")
    parser.add_argument("--system", choices=["keycloak", "zitadel", "authentik"])
    parser.add_argument("--challenge", help="Run a single challenge by module name")
    args = parser.parse_args()

    level = None if args.level == "all" else int(args.level)
    modules = discover_modules(level)

    if args.challenge:
        modules = [(lvl, name, mod) for lvl, name, mod in modules if name == args.challenge]

    if not modules:
        print("No challenges found.", file=sys.stderr)
        return 1

    all_results: list[dict] = []
    for lvl, name, module in modules:
        print(f"Running level {lvl}/{name}...")
        batch = module.run(system_filter=args.system)
        all_results.extend(batch)

    merged = merge_results(load_existing_results(), all_results)
    write_results(merged)

    passed = sum(1 for r in all_results if r["passed"])
    print(f"Done: {passed}/{len(all_results)} passed. Results -> {RESULTS_FILE}")
    return 0 if passed == len(all_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
