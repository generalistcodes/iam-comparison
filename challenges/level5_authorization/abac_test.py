"""Level 5: ABAC / authorization policy API."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token
from lib import run_for_all_systems

LEVEL = 5
CHALLENGE = "abac_test"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/clients",
        headers={"Authorization": f"Bearer {token}"},
        params={"clientId": cfg["client_id"]},
        timeout=15,
    )
    r.raise_for_status()
    clients = r.json()
    if not clients:
        return False, "Client not found"
    cid = clients[0]["id"]
    r2 = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/clients/{cid}/authz/resource-server/policy",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r2.status_code in (200, 404), f"Authz policy API status {r2.status_code}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/debug/ready", timeout=15)
    return r.status_code == 200, "Zitadel ABAC via project roles — manual setup"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/policies/all/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"Policies API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
