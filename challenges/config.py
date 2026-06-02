"""Endpoints and credentials for IAM challenge lab."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

REALM = "iam-lab"
CLIENT_ID = "iam-lab-client"
CLIENT_SECRET = os.environ.get("IAM_LAB_CLIENT_SECRET", "iam-lab-secret-change-me")
TEST_USER = "testuser"
TEST_USER_PASSWORD = os.environ.get("IAM_LAB_TEST_PASSWORD", "Test1234!")
TEST_USER_EMAIL = "testuser@iam-lab.local"

SYSTEMS = ("keycloak", "zitadel", "authentik")

SYSTEM_DEFAULTS: dict[str, dict[str, str | int]] = {
    "keycloak": {
        "base_url": f"http://localhost:{os.environ.get('KEYCLOAK_HTTP_PORT', '8080')}",
        "admin_user": os.environ.get("KEYCLOAK_ADMIN", "admin"),
        "admin_password": os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin"),
        "realm": REALM,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "test_user": TEST_USER,
        "test_password": TEST_USER_PASSWORD,
    },
    "zitadel": {
        "base_url": f"http://localhost:{os.environ.get('ZITADEL_HTTP_PORT', '8081')}",
        "login_url": f"http://localhost:{os.environ.get('ZITADEL_LOGIN_PORT', '3001')}",
        "admin_email": "zitadel-admin@zitadel.localhost",
        "admin_password": "Password1!",
        "org_name": "IAM Lab",
        "project_name": "iam-lab",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "test_user": TEST_USER,
        "test_password": TEST_USER_PASSWORD,
        "pat_file": str(ROOT / "setup" / "zitadel" / ".pat"),
    },
    "authentik": {
        "base_url": f"http://localhost:{os.environ.get('AUTHENTIK_HTTP_PORT', '9090')}",
        "admin_user": os.environ.get("AUTHENTIK_ADMIN_USER", "akadmin"),
        "admin_password": os.environ.get("AUTHENTIK_ADMIN_PASSWORD", ""),
        "token_file": str(ROOT / "setup" / "authentik" / ".token"),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "test_user": TEST_USER,
        "test_password": TEST_USER_PASSWORD,
    },
}


def get_system_config(system: str) -> dict[str, str | int]:
    if system not in SYSTEM_DEFAULTS:
        raise ValueError(f"Unknown system: {system}")
    return dict(SYSTEM_DEFAULTS[system])
