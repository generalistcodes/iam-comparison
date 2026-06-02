"""Shared utilities for IAM challenge scripts."""

from __future__ import annotations

import time
import traceback
from dataclasses import asdict, dataclass
from typing import Any, Callable

import requests

from config import SYSTEMS, get_system_config


@dataclass
class ChallengeResult:
    system: str
    level: int
    challenge_name: str
    passed: bool
    response_time_ms: int
    error: str | None = None
    partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def result(
    system: str,
    level: int,
    challenge_name: str,
    passed: bool,
    response_time_ms: int,
    error: str | None = None,
    partial: bool = False,
) -> dict[str, Any]:
    return ChallengeResult(
        system=system,
        level=level,
        challenge_name=challenge_name,
        passed=passed,
        response_time_ms=response_time_ms,
        error=error,
        partial=partial,
    ).to_dict()


def timed_run(
    system: str,
    level: int,
    challenge_name: str,
    fn: Callable[[dict[str, Any]], tuple[bool, str | None]],
    partial_on_fail: bool = False,
) -> dict[str, Any]:
    cfg = get_system_config(system)
    start = time.perf_counter()
    try:
        passed, error = fn(cfg)
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(
            system,
            level,
            challenge_name,
            passed,
            elapsed,
            error,
            partial=partial_on_fail and not passed and error is not None,
        )
    except requests.RequestException as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(system, level, challenge_name, False, elapsed, str(exc))
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(
            system,
            level,
            challenge_name,
            False,
            elapsed,
            f"{exc}\n{traceback.format_exc()}",
        )


def run_for_all_systems(
    level: int,
    challenge_name: str,
    runners: dict[str, Callable[[dict[str, Any]], tuple[bool, str | None]]],
    system_filter: str | None = None,
    partial_on_fail: bool = False,
) -> list[dict[str, Any]]:
    targets = [system_filter] if system_filter else list(SYSTEMS)
    return [
        timed_run(system, level, challenge_name, runners[system], partial_on_fail)
        for system in targets
        if system in runners
    ]
