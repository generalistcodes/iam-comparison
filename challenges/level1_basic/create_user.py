"""Level 1: verify test user exists."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 1
CHALLENGE = "create_user"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/users",
        headers={"Authorization": f"Bearer {token}"},
        params={"username": cfg["test_user"], "exact": "true"},
        timeout=15,
    )
    r.raise_for_status()
    users = r.json()
    if not users:
        return False, f"User {cfg['test_user']} not found — run: make setup"
    return True, None


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.post(
        f"{cfg['base_url']}/v2/users",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={"queries": [{"userNameQuery": {"userName": cfg["test_user"], "method": "TEXT_QUERY_METHOD_EQUALS"}}]},
        timeout=15,
    )
    if r.status_code == 401:
        return False, "Invalid PAT — run: make setup"
    r.raise_for_status()
    if not r.json().get("result"):
        return False, f"User {cfg['test_user']} not found — run: make setup"
    return True, None


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/core/users/",
        headers={"Authorization": f"Bearer {token}"},
        params={"username": cfg["test_user"]},
        timeout=15,
    )
    r.raise_for_status()
    if r.json().get("pagination", {}).get("count", 0) == 0:
        return False, f"User {cfg['test_user']} not found — run: make setup"
    return True, None


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL,
        CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter,
    )
