"""Level 6: audit / event log API."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 6
CHALLENGE = "audit_log"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"max": 5},
        timeout=15,
    )
    return r.status_code == 200, f"Events API status {r.status_code}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.post(
        f"{cfg['base_url']}/admin/v1/events/_search",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={"query": {"offset": "0", "limit": 5}},
        timeout=15,
    )
    return r.status_code < 500, f"Events API status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/events/events/",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 5},
        timeout=15,
    )
    return r.status_code == 200, f"Events API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
