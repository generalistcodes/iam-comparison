"""Level 2: brute-force / lockout policy probe."""

from __future__ import annotations

from typing import Any

import requests

from helpers import keycloak_admin_token
from lib import run_for_all_systems

LEVEL = 2
CHALLENGE = "brute_force"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    enabled = data.get("bruteForceProtected", False)
    return enabled, f"bruteForceProtected={enabled}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.post(
        f"{cfg['base_url']}/oauth/v2/token",
        data={"grant_type": "password", "username": "nobody", "password": "wrong"},
        timeout=15,
    )
    return r.status_code in (400, 401, 403), f"Failed login status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.post(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        json={"uid_field": "nobody", "password": "wrong"},
        timeout=15,
    )
    return r.status_code in (400, 401, 403, 404), f"Auth flow status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
