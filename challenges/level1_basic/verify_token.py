"""Level 1: verify token via userinfo / introspection."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_realm_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 1
CHALLENGE = "verify_token"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_realm_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code != 200:
        return False, f"Userinfo failed ({r.status_code})"
    if r.json().get("preferred_username") != cfg["test_user"]:
        return False, "Token subject mismatch"
    return True, None


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.get(
        f"{cfg['base_url']}/oauth/v2/userinfo",
        headers={"Authorization": f"Bearer {pat}"},
        timeout=15,
    )
    if r.status_code == 200:
        return True, None
    r = requests.get(f"{cfg['base_url']}/debug/ready", headers={"Authorization": f"Bearer {pat}"}, timeout=15)
    return r.status_code == 200, "PAT accepted; userinfo unavailable for service token"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/core/users/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    username = body.get("username") or (body.get("user") or {}).get("username")
    return bool(username), None if username else "Could not verify API token"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL,
        CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter,
    )
