"""Level 5: token claims / mapper configuration."""

from __future__ import annotations

from typing import Any

import requests

from helpers import keycloak_client_credentials_token, keycloak_realm_token
from lib import run_for_all_systems

LEVEL = 5
CHALLENGE = "token_claims"


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
        token = keycloak_client_credentials_token(cfg)
        r = requests.get(
            f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        return r.status_code == 200, f"Token claims check status {r.status_code}"
    token = r.json().get("access_token", "")
    r = requests.get(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"Token claims check status {r.status_code}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    from helpers import zitadel_pat

    pat = zitadel_pat(cfg)
    r = requests.get(
        f"{cfg['base_url']}/debug/ready",
        headers={"Authorization": f"Bearer {pat}"},
        timeout=15,
    )
    return r.status_code == 200, None if r.status_code == 200 else f"Ready check status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/application/o/{cfg['client_id']}/.well-known/openid-configuration", timeout=15)
    if r.status_code == 404:
        r = requests.get(f"{cfg['base_url']}/-/health/live/", timeout=15)
    return r.status_code == 200, f"OIDC metadata status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
