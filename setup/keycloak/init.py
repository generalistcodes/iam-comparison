#!/usr/bin/env python3
"""Bootstrap Keycloak: realm, client, test user."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "challenges"))

from config import CLIENT_ID, CLIENT_SECRET, REALM, TEST_USER, TEST_USER_EMAIL, TEST_USER_PASSWORD, get_system_config  # noqa: E402


def admin_token(cfg: dict) -> str:
    r = requests.post(
        f"{cfg['base_url']}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": cfg["admin_user"],
            "password": cfg["admin_password"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def ensure_realm(cfg: dict, token: str) -> None:
    base = f"{cfg['base_url']}/admin/realms"
    r = requests.get(f"{base}/{REALM}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if r.status_code == 200:
        print(f"  realm '{REALM}' exists")
        return
    r = requests.post(
        base,
        headers={"Authorization": f"Bearer {token}"},
        json={"realm": REALM, "enabled": True, "registrationAllowed": False},
        timeout=15,
    )
    r.raise_for_status()
    print(f"  created realm '{REALM}'")


def ensure_client(cfg: dict, token: str) -> None:
    base = f"{cfg['base_url']}/admin/realms/{REALM}/clients"
    r = requests.get(base, headers={"Authorization": f"Bearer {token}"}, params={"clientId": CLIENT_ID}, timeout=15)
    r.raise_for_status()
    if r.json():
        print(f"  client '{CLIENT_ID}' exists")
        return
    r = requests.post(
        base,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "clientId": CLIENT_ID,
            "enabled": True,
            "publicClient": False,
            "secret": CLIENT_SECRET,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": True,
        },
        timeout=15,
    )
    r.raise_for_status()
    print(f"  created client '{CLIENT_ID}'")


def ensure_user(cfg: dict, token: str) -> None:
    base = f"{cfg['base_url']}/admin/realms/{REALM}/users"
    r = requests.get(
        base,
        headers={"Authorization": f"Bearer {token}"},
        params={"username": TEST_USER, "exact": "true"},
        timeout=15,
    )
    r.raise_for_status()
    if r.json():
        print(f"  user '{TEST_USER}' exists")
        uid = r.json()[0]["id"]
        requests.put(
            f"{base}/{uid}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": TEST_USER,
                "firstName": "Test",
                "lastName": "User",
                "email": TEST_USER_EMAIL,
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
            },
            timeout=15,
        )
        return
    r = requests.post(
        base,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": TEST_USER,
            "firstName": "Test",
            "lastName": "User",
            "email": TEST_USER_EMAIL,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": TEST_USER_PASSWORD, "temporary": False}],
        },
        timeout=15,
    )
    r.raise_for_status()
    print(f"  created user '{TEST_USER}'")


def main() -> int:
    cfg = get_system_config("keycloak")
    print(f"[keycloak] bootstrapping {cfg['base_url']} ...")
    try:
        token = admin_token(cfg)
        ensure_realm(cfg, token)
        ensure_client(cfg, token)
        ensure_user(cfg, token)
    except requests.RequestException as exc:
        print(f"[keycloak] FAILED: {exc}", file=sys.stderr)
        print("  Start Keycloak: make up PROFILE=keycloak", file=sys.stderr)
        return 1
    print("[keycloak] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
