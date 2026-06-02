"""Level 1: obtain access token."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_client_credentials_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 1
CHALLENGE = "get_token"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_client_credentials_token(cfg)
    return (bool(token), None if token else "Empty token")


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
    return True, None


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/core/applications/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    apps = [a for a in r.json().get("results", []) if a.get("slug") == cfg["client_id"]]
    if not apps:
        return False, f"Application {cfg['client_id']} not found — run: make setup"
    return True, None


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL,
        CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter,
    )
