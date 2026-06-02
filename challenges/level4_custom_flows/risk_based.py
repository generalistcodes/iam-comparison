"""Level 4: risk-based / conditional access probe."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token
from lib import run_for_all_systems

LEVEL = 4
CHALLENGE = "risk_based"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/authentication/conditional-credential-authenticators",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, "Conditional auth API reachable"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    r = requests.get(f"{cfg['base_url']}/ui/console", timeout=15, allow_redirects=True)
    return r.status_code < 500, "Risk policies — configure in Zitadel console"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/policies/expression/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"Expression policies API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
