#!/usr/bin/env python3
"""Health-check IAM systems and run all challenge levels with live output."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CHALLENGES_DIR = ROOT / "challenges"
sys.path.insert(0, str(CHALLENGES_DIR))

from config import SYSTEMS  # noqa: E402
from runner import RESULTS_FILE, discover_modules, write_results  # noqa: E402

# ANSI colors (work on most terminals)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

RETRY_DELAY_SEC = 5

HEALTH_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "keycloak": (
        "http://localhost:8080/health/ready",
        "http://localhost:8080/health",
        "http://localhost:8080/",
    ),
    "zitadel": (
        "http://localhost:8081/debug/ready",
        "http://localhost:8081/debug/healthz",
    ),
    "authentik": (
        "http://localhost:9090/-/health/live/",
        "http://localhost:9090/-/health/ready/",
    ),
}


def _load_env_ports() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    import os

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

    kc = os.environ.get("KEYCLOAK_HTTP_PORT", "8080")
    zt = os.environ.get("ZITADEL_HTTP_PORT", "8081")
    ak = os.environ.get("AUTHENTIK_HTTP_PORT", "9090")
    HEALTH_ENDPOINTS["keycloak"] = (
        f"http://localhost:{kc}/health/ready",
        f"http://localhost:{kc}/health",
        f"http://localhost:{kc}/",
    )
    HEALTH_ENDPOINTS["zitadel"] = (
        f"http://localhost:{zt}/debug/ready",
        f"http://localhost:{zt}/debug/healthz",
    )
    HEALTH_ENDPOINTS["authentik"] = (
        f"http://localhost:{ak}/-/health/live/",
        f"http://localhost:{ak}/-/health/ready/",
    )


def check_system_health(system: str) -> bool:
    for url in HEALTH_ENDPOINTS[system]:
        try:
            r = requests.get(url, timeout=5, allow_redirects=True)
            if r.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def print_health_status(status: dict[str, bool]) -> list[str]:
    print(f"\n{BOLD}{CYAN}IAM System Health{RESET}")
    print("-" * 40)
    up: list[str] = []
    for system in SYSTEMS:
        if status[system]:
            print(f"  {GREEN}●{RESET} {system:<12} UP")
            up.append(system)
        else:
            print(f"  {RED}●{RESET} {system:<12} DOWN  {DIM}(tests skipped){RESET}")
    print()
    return up


def format_result_line(r: dict) -> str:
    if r.get("passed"):
        icon = f"{GREEN}✅ pass{RESET}"
    elif r.get("partial"):
        icon = f"{YELLOW}⚠️  partial{RESET}"
    else:
        icon = f"{RED}❌ fail{RESET}"

    err = r.get("error") or ""
    err_suffix = f"  {DIM}{err[:80]}{RESET}" if err and not r.get("passed") else ""
    retry = " (retry)" if r.get("_retried") else ""
    jwks = f"  {DIM}jwks={r['jwks_fetch_ms']}ms{RESET}" if r.get("jwks_fetch_ms") is not None else ""
    return (
        f"  L{r['level']} {r['challenge_name']:<22} "
        f"{r['system']:<12} {icon}  {r['response_time_ms']:>4}ms{jwks}{retry}{err_suffix}"
    )


def run_challenge_once(module: object, system: str) -> dict:
    batch = module.run(system_filter=system)  # type: ignore[attr-defined]
    for item in batch:
        if item["system"] == system:
            return item
    raise RuntimeError(f"No result returned for system={system}")


def run_with_retry(module: object, system: str) -> dict:
    result = run_challenge_once(module, system)
    if result.get("passed") or result.get("partial"):
        return result

    print(f"  {DIM}retry in {RETRY_DELAY_SEC}s...{RESET}", flush=True)
    time.sleep(RETRY_DELAY_SEC)
    retry = run_challenge_once(module, system)
    retry["_retried"] = True
    if retry.get("passed") or retry.get("partial"):
        return retry
    return retry


def print_summary_table(results: list[dict], up_systems: list[str]) -> None:
    print(f"\n{BOLD}{CYAN}Summary (passed/total per level){RESET}")
    header = f"{'Level':<8}" + "".join(f"{s:<14}" for s in SYSTEMS)
    print(header)
    print("-" * len(header))

    for level in range(1, 7):
        row = f"L{level:<7}"
        for system in SYSTEMS:
            if system not in up_systems:
                row += f"{'—':<14}"
                continue
            level_results = [
                r for r in results if r["level"] == level and r["system"] == system
            ]
            if not level_results:
                row += f"{'0/0':<14}"
                continue
            passed = sum(1 for r in level_results if r.get("passed") or r.get("partial"))
            row += f"{passed}/{len(level_results):<13}"
        print(row)

    total_pass = sum(1 for r in results if r.get("passed") or r.get("partial"))
    total_fail = sum(1 for r in results if not r.get("passed") and not r.get("partial"))
    print(f"\n{BOLD}Total:{RESET} {total_pass} passed/partial, {total_fail} failed "
          f"({len(results)} tests on {len(up_systems)} system(s))")


def main() -> int:
    _load_env_ports()

    print(f"{BOLD}IAM Challenge Lab — verify.py{RESET}")

    health = {s: check_system_health(s) for s in SYSTEMS}
    up_systems = print_health_status(health)

    if not up_systems:
        print(f"{RED}No IAM systems are up. Start one with: make up PROFILE=<name>{RESET}")
        write_results([])
        return 1

    modules = discover_modules()
    if not modules:
        print(f"{RED}No challenge modules found under challenges/{RESET}")
        return 1

    all_results: list[dict] = []

    print(f"{BOLD}Running {len(modules)} challenges × {len(up_systems)} system(s)...{RESET}\n")

    for level, name, module in modules:
        for system in up_systems:
            print(f"{CYAN}▶{RESET} L{level}/{name} [{system}]", flush=True)
            try:
                r = run_with_retry(module, system)
            except Exception as exc:  # noqa: BLE001
                r = {
                    "system": system,
                    "level": level,
                    "challenge_name": name,
                    "passed": False,
                    "partial": False,
                    "response_time_ms": 0,
                    "error": str(exc),
                }
            r.pop("_retried", None)
            all_results.append(r)
            print(format_result_line(r), flush=True)

    write_results(all_results)
    print(f"\n{DIM}Results written to {RESULTS_FILE}{RESET}")

    print_summary_table(all_results, up_systems)

    failed = [r for r in all_results if not r.get("passed") and not r.get("partial")]
    if failed:
        print(f"\n{RED}{BOLD}FAILED{RESET} — {len(failed)} test(s) did not pass")
        return 1

    print(f"\n{GREEN}{BOLD}ALL PASSED{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
