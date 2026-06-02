#!/usr/bin/env python3
"""Bootstrap Zitadel: project, OIDC app, test user; save PAT."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "challenges"))

from config import CLIENT_ID, CLIENT_SECRET, TEST_USER, TEST_USER_PASSWORD, get_system_config  # noqa: E402

PAT_FILE = Path(__file__).resolve().parent / ".pat"
VOLUME_PAT = "login-client.pat"


def load_pat_from_volume(cfg: dict) -> str | None:
    """Copy login-client PAT from Zitadel data volume if available."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", "iam-opensource_zitadel_data:/data:ro",
                "alpine", "cat", f"/data/{VOLUME_PAT}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        pat = result.stdout.strip()
        return pat if result.returncode == 0 and pat else None
    except (OSError, subprocess.SubprocessError):
        return None


def login_pat(cfg: dict) -> str | None:
    """Try to obtain a management token via password grant."""
    r = requests.post(
        f"{cfg['base_url']}/oauth/v2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "client_id": "zitadel-admin",
            "username": cfg["admin_email"],
            "password": cfg["admin_password"],
            "scope": "openid urn:zitadel:iam:org:project:id:zitadel:aud",
        },
        timeout=30,
    )
    if r.status_code == 200 and r.json().get("access_token"):
        return r.json()["access_token"]
    return None


def ensure_user(cfg: dict, pat: str) -> None:
    r = requests.post(
        f"{cfg['base_url']}/v2/users/human",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={
            "username": TEST_USER,
            "profile": {"givenName": "Test", "familyName": "User"},
            "email": {"email": f"{TEST_USER}@iam-lab.local", "isVerified": True},
            "password": {"password": TEST_USER_PASSWORD, "changeRequired": False},
        },
        timeout=30,
    )
    if r.status_code == 409:
        print(f"  user '{TEST_USER}' exists")
        return
    if r.status_code >= 400:
        print(f"  user create skipped ({r.status_code}): {r.text[:120]}")
        return
    print(f"  created user '{TEST_USER}'")


def main() -> int:
    cfg = get_system_config("zitadel")
    print(f"[zitadel] bootstrapping {cfg['base_url']} ...")

    if PAT_FILE.exists():
        pat = PAT_FILE.read_text(encoding="utf-8").strip()
        print("  using existing PAT from setup/zitadel/.pat")
    else:
        pat = login_pat(cfg) or load_pat_from_volume(cfg)
        if not pat:
            print("[zitadel] FAILED: could not obtain admin token.", file=sys.stderr)
            print("  1. Start Zitadel: make up PROFILE=zitadel", file=sys.stderr)
            print("  2. Create a service user PAT in the console", file=sys.stderr)
            print(f"  3. Save it to {PAT_FILE}", file=sys.stderr)
            return 1
        PAT_FILE.write_text(pat + "\n", encoding="utf-8")
        print(f"  saved PAT -> {PAT_FILE}")

    try:
        r = requests.get(f"{cfg['base_url']}/debug/ready", timeout=15)
        r.raise_for_status()
        ensure_user(cfg, pat)
        print(f"  OIDC client '{CLIENT_ID}' — create manually or via API if needed")
        print(f"  suggested secret: {CLIENT_SECRET}")
    except requests.RequestException as exc:
        print(f"[zitadel] FAILED: {exc}", file=sys.stderr)
        return 1

    print("[zitadel] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
