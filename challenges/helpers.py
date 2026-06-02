"""HTTP helpers for IAM system APIs."""

from __future__ import annotations

from typing import Any

import requests


def keycloak_admin_token(cfg: dict[str, Any]) -> str:
    r = requests.post(
        f"{cfg['base_url']}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": cfg["admin_user"],
            "password": cfg["admin_password"],
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def keycloak_realm_token(cfg: dict[str, Any]) -> str:
    r = requests.post(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "username": cfg["test_user"],
            "password": cfg["test_password"],
            "scope": "openid profile email",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def keycloak_client_credentials_token(cfg: dict[str, Any]) -> str:
    r = requests.post(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def authentik_token(cfg: dict[str, Any]) -> str:
    token_file = cfg.get("token_file")
    if token_file:
        from pathlib import Path

        path = Path(str(token_file))
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    raise requests.RequestException(
        "Authentik API token missing. Run: make setup (or create setup/authentik/.token)"
    )


def zitadel_pat(cfg: dict[str, Any]) -> str:
    pat_file = cfg.get("pat_file")
    if pat_file:
        from pathlib import Path

        path = Path(str(pat_file))
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    raise requests.RequestException(
        "Zitadel PAT missing. Run: make setup (or create setup/zitadel/.pat)"
    )


def ping(url: str, timeout: int = 10) -> tuple[int, float]:
    import time

    start = time.perf_counter()
    r = requests.get(url, timeout=timeout, allow_redirects=True)
    elapsed = (time.perf_counter() - start) * 1000
    return r.status_code, elapsed
