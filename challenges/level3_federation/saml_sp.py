"""Level 3: SAML SP configuration API."""

from __future__ import annotations

from typing import Any

import requests

from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import run_for_all_systems

LEVEL = 3
CHALLENGE = "saml_sp"


def run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/saml/descriptor",
        timeout=15,
    )
    return r.status_code == 200 and "EntityDescriptor" in r.text, f"SAML descriptor status {r.status_code}"


def run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    r = requests.get(
        f"{cfg['base_url']}/v2/saml/metadata",
        headers={"Authorization": f"Bearer {pat}"},
        timeout=15,
    )
    return r.status_code < 500, f"SAML metadata status {r.status_code}"


def run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    r = requests.get(
        f"{cfg['base_url']}/api/v3/providers/saml/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code == 200, f"SAML providers API status {r.status_code}"


def run(system_filter: str | None = None) -> list[dict]:
    return run_for_all_systems(
        LEVEL, CHALLENGE,
        {"keycloak": run_keycloak, "zitadel": run_zitadel, "authentik": run_authentik},
        system_filter, partial_on_fail=True,
    )
