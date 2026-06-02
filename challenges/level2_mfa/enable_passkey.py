"""Level 2: WebAuthn / passkey capability check."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 2
CHALLENGE = "enable_passkey"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/authentication/authenticator-providers",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    providers = [p.get("id") for p in r.json()]
    return "webauthn-authenticator" in providers, f"Providers: {providers[:5]}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.get(
        f"{cfg['base_url']}/v2/features",
        headers={"Authorization": f"Bearer {pat}"},
        timeout=15,
    )
    return r.status_code == 200, "Passkey API probe — manual enrollment required"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/stages/authenticator_webauthn/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"WebAuthn stages API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
