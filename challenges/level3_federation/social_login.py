"""Level 3: social / OIDC IdP federation API."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 3
CHALLENGE = "social_login"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/identity-provider/instances",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, "Identity provider API reachable"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.post(
        f"{cfg['base_url']}/v2/idps",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={"queries": []},
        timeout=15,
    )
    return r.status_code < 500, f"IdP list API status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/sources/oauth/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"OAuth sources API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
