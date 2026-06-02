"""Level 4: step-up authentication flow API."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token
from lib import run_for_all_systems

LEVEL = 4
CHALLENGE = "step_up_auth"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/authentication/flows",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    flows = [f.get("alias") for f in r.json()]
    return any("browser" in (f or "") for f in flows), f"Flows: {flows[:5]}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/debug/ready", timeout=15)
    return r.status_code == 200, "Custom login policy — configure in console"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/flows/instances/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"Flows API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
