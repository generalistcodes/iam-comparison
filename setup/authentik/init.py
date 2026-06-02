#!/usr/bin/env python3
"""Bootstrap Authentik: application, test user; save API token."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "challenges"))

from config import CLIENT_ID, TEST_USER, TEST_USER_PASSWORD, get_system_config  # noqa: E402

TOKEN_FILE = Path(__file__).resolve().parent / ".token"


def create_token_via_bootstrap(cfg: dict) -> str | None:
    """Create API token if bootstrap credentials are configured."""
    password = os.environ.get("AUTHENTIK_ADMIN_PASSWORD", "")
    user = os.environ.get("AUTHENTIK_ADMIN_USER", "akadmin")
    if not password:
        return None
    session = requests.Session()
    r = session.get(f"{cfg['base_url']}/if/flow/initial-setup/", timeout=15)
    if r.status_code == 404:
        pass  # setup already done
    # Use API token endpoint with existing admin — requires prior token for full automation
    return None


def ensure_application(cfg: dict, token: str) -> None:
    r = requests.get(
        f"{cfg['base_url']}/api/v3/core/applications/",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": CLIENT_ID},
        timeout=15,
    )
    r.raise_for_status()
    if any(a.get("slug") == CLIENT_ID for a in r.json().get("results", [])):
        print(f"  application '{CLIENT_ID}' exists")
        return
    provider = requests.post(
        f"{cfg['base_url']}/api/v3/providers/oauth2/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "IAM Lab Provider",
            "authorization_flow": "a8d8b30a-2905-48b1-ad7d-3ec4a6ef9e98",
            "invalidation_flow": "1a1ac45a-0866-41a4-b81d-881ac2160fcd",
            "client_type": "confidential",
            "client_id": CLIENT_ID,
            "client_secret": os.environ.get("IAM_LAB_CLIENT_SECRET", "iam-lab-secret-change-me"),
            "redirect_uris": [{"matching_mode": "strict", "url": "http://localhost:1234/callback"}],
        },
        timeout=30,
    )
    if provider.status_code >= 400:
        print(f"  provider create skipped ({provider.status_code})")
        return
    pid = provider.json().get("pk")
    requests.post(
        f"{cfg['base_url']}/api/v3/core/applications/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "IAM Lab", "slug": CLIENT_ID, "provider": pid},
        timeout=30,
    )
    print(f"  created application '{CLIENT_ID}'")


def ensure_user(cfg: dict, token: str) -> None:
    r = requests.get(
        f"{cfg['base_url']}/api/v3/core/users/",
        headers={"Authorization": f"Bearer {token}"},
        params={"username": TEST_USER},
        timeout=15,
    )
    r.raise_for_status()
    if r.json().get("pagination", {}).get("count", 0) > 0:
        print(f"  user '{TEST_USER}' exists")
        return
    r = requests.post(
        f"{cfg['base_url']}/api/v3/core/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": TEST_USER,
            "name": "Test User",
            "is_active": True,
            "path": "users",
        },
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"  user create skipped ({r.status_code})")
        return
    pk = r.json().get("pk")
    requests.post(
        f"{cfg['base_url']}/api/v3/core/users/{pk}/set_password/",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": TEST_USER_PASSWORD},
        timeout=30,
    )
    print(f"  created user '{TEST_USER}'")


def main() -> int:
    cfg = get_system_config("authentik")
    print(f"[authentik] bootstrapping {cfg['base_url']} ...")

    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        print(f"  using existing token from {TOKEN_FILE}")
    else:
        token = create_token_via_bootstrap(cfg)
        if not token:
            print("[authentik] API token required.", file=sys.stderr)
            print("  1. Complete initial setup: http://localhost:9090/if/flow/initial-setup/", file=sys.stderr)
            print("  2. Admin → Applications → Tokens → Create token", file=sys.stderr)
            print(f"  3. Save token to {TOKEN_FILE}", file=sys.stderr)
            print("     echo 'YOUR_TOKEN' > setup/authentik/.token", file=sys.stderr)
            return 1

    try:
        r = requests.get(
            f"{cfg['base_url']}/api/v3/core/users/me/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        ensure_application(cfg, token)
        ensure_user(cfg, token)
    except requests.RequestException as exc:
        print(f"[authentik] FAILED: {exc}", file=sys.stderr)
        print("  Start Authentik: make up PROFILE=authentik", file=sys.stderr)
        return 1

    print("[authentik] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
