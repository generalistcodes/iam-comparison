"""Level 6: token revocation / logout."""

from __future__ import annotations

from typing import Any

import requests

from helpers import keycloak_realm_token
from lib import run_for_all_systems

LEVEL = 6
CHALLENGE = "token_revocation"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.post(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "username": cfg["test_user"],
            "password": cfg["test_password"],
        },
        timeout=15,
    )
    if r.status_code != 200:
        return False, f"Token request failed ({r.status_code})"
    refresh = r.json().get("refresh_token")
    if not refresh:
        return False, "No refresh_token returned"
    r = requests.post(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/logout",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "refresh_token": refresh,
        },
        timeout=15,
    )
    return r.status_code in (200, 204), f"Logout endpoint status {r.status_code}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(
        f"{cfg['base_url']}/oauth/v2/revoke",
        timeout=15,
        allow_redirects=False,
    )
    return r.status_code in (404, 405, 400, 200), f"Revoke endpoint status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/if/session-end/authentik/", timeout=15, allow_redirects=True)
    return r.status_code < 500, f"Session end status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
