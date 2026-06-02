"""Level 4: biometric auth stub (WebAuthn readiness)."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token
from lib import run_for_all_systems

LEVEL = 4
CHALLENGE = "biometric_stub"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(
        f"{cfg['base_url']}/realms/{cfg['realm']}/.well-known/openid-configuration",
        timeout=15,
    )
    return r.status_code == 200, "OIDC discovery OK — WebAuthn enrollment manual"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/debug/ready", timeout=15)
    return r.status_code == 200, "Biometric stub — not automated in lab"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/stages/authenticator_validate/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"Validation stages API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
