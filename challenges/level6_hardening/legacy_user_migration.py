"""Level 6: bulk-import users, verify via list API, authenticate end to end."""

from __future__ import annotations

import textwrap
import time
from typing import Any

import requests

from config import SYSTEMS, get_system_config
from helpers import authentik_token, keycloak_admin_token, zitadel_pat
from lib import result

LEVEL = 6
CHALLENGE = "legacy_user_migration"
USER_COUNT = 10
MIGRATE_PREFIX = "migrate-bulk"
MIGRATE_PASSWORD = "Migrate1234!"


# -----------------------------------------------------------------------------
# Keycloak User Storage Federation pattern (documentation only — not executed)
# -----------------------------------------------------------------------------
# Legacy identity stores (LDAP, Active Directory, custom JDBC, REST SPI) can be
# connected via Keycloak's User Storage SPI without importing password hashes
# into Keycloak's local database. Keycloak delegates lookup and authenticate()
# to the external provider; users appear in the admin console and token claims
# while credentials remain in the legacy store.
#
#   Admin Console → User Federation → Add provider → ldap | kerberos | scim
#   Or: custom UserStorageProviderFactory for phased REST/JDBC migration
#
# Federation fits when forcing a password reset is unacceptable: users keep
# existing credentials while apps switch to OIDC tokens issued by Keycloak.
# Bulk partialImport (used below) is the alternative when hashes can be
# migrated; federation is the pattern when they cannot.
# -----------------------------------------------------------------------------


def _usernames() -> list[str]:
    return [f"{MIGRATE_PREFIX}-{i:02d}" for i in range(1, USER_COUNT + 1)]


def _bulk_import_keycloak(cfg: dict[str, Any], token: str) -> None:
    users = [
        {
            "username": name,
            "enabled": True,
            "firstName": "Migrate",
            "lastName": name.split("-")[-1],
            "email": f"{name}@iam-lab.local",
            "emailVerified": True,
            "credentials": [
                {"type": "password", "value": MIGRATE_PASSWORD, "temporary": False}
            ],
        }
        for name in _usernames()
    ]
    r = requests.post(
        f"{cfg['base_url']}/admin/realms/{cfg['realm']}/partialImport",
        headers={"Authorization": f"Bearer {token}"},
        json={"ifResourceExists": "SKIP", "users": users},
        timeout=60,
    )
    r.raise_for_status()


def _list_keycloak(cfg: dict[str, Any], token: str) -> set[str]:
    found: set[str] = set()
    for name in _usernames():
        r = requests.get(
            f"{cfg['base_url']}/admin/realms/{cfg['realm']}/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"username": name, "exact": "true"},
            timeout=15,
        )
        r.raise_for_status()
        if r.json():
            found.add(name)
    return found


def _auth_keycloak(cfg: dict[str, Any], username: str) -> None:
    r = requests.post(
        f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "username": username,
            "password": MIGRATE_PASSWORD,
            "scope": "openid profile email",
        },
        timeout=15,
    )
    r.raise_for_status()
    if not r.json().get("access_token"):
        raise requests.RequestException("Keycloak auth returned no access_token")


def _zitadel_org_id(cfg: dict[str, Any], pat: str) -> str:
    r = requests.post(
        f"{cfg['base_url']}/v2/organizations/_search",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={"queries": []},
        timeout=15,
    )
    r.raise_for_status()
    if r.json().get("result"):
        org = r.json()["result"][0]
        return org.get("id") or org.get("orgId") or org.get("organizationId", "")
    r = requests.get(
        f"{cfg['base_url']}/management/v1/orgs/me",
        headers={"Authorization": f"Bearer {pat}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("org", {}).get("id", "")


def _scim_operation_status(op: dict[str, Any]) -> int:
    status = op.get("status")
    if isinstance(status, dict):
        return int(status.get("code", 200))
    if status is None:
        response = op.get("response") or {}
        nested = response.get("status")
        if nested is not None:
            return int(nested)
        return 200
    return int(status)


def _bulk_import_zitadel_scim(cfg: dict[str, Any], pat: str, org_id: str) -> None:
    operations = []
    for name in _usernames():
        suffix = name.split("-")[-1]
        operations.append(
            {
                "method": "POST",
                "path": "/Users",
                "bulkId": name,
                "data": {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "userName": name,
                    "name": {"givenName": "Migrate", "familyName": suffix},
                    "emails": [{"value": f"{name}@iam-lab.local", "primary": True}],
                    "password": MIGRATE_PASSWORD,
                    "active": True,
                },
            }
        )
    r = requests.post(
        f"{cfg['base_url']}/scim/v2/{org_id}/Bulk",
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/scim+json",
            "Accept": "application/scim+json",
        },
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
            "Operations": operations,
        },
        timeout=60,
    )
    if r.status_code >= 400:
        raise requests.RequestException(
            f"Zitadel SCIM bulk import failed ({r.status_code}): {r.text[:200]}"
        )
    body = r.json()
    failed = [
        op
        for op in body.get("Operations", [])
        if _scim_operation_status(op) >= 400 and _scim_operation_status(op) != 409
    ]
    if failed and len(failed) == len(operations):
        detail = (failed[0].get("response") or {}).get("detail", "unknown error")
        raise requests.RequestException(f"All SCIM bulk operations failed: {detail}")


def _bulk_import_zitadel(cfg: dict[str, Any], pat: str) -> None:
    org_id = _zitadel_org_id(cfg, pat)
    if not org_id:
        raise requests.RequestException("Could not resolve Zitadel organization ID")
    _bulk_import_zitadel_scim(cfg, pat, org_id)


def _list_zitadel(cfg: dict[str, Any], pat: str) -> set[str]:
    found: set[str] = set()
    for name in _usernames():
        r = requests.post(
            f"{cfg['base_url']}/v2/users",
            headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
            json={
                "queries": [
                    {"userNameQuery": {"userName": name, "method": "TEXT_QUERY_METHOD_EQUALS"}}
                ]
            },
            timeout=15,
        )
        r.raise_for_status()
        if r.json().get("result"):
            found.add(name)
    return found


def _auth_zitadel(cfg: dict[str, Any], username: str) -> None:
    pat = zitadel_pat(cfg)
    r = requests.post(
        f"{cfg['base_url']}/v2/sessions",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={
            "checks": {
                "user": {"loginName": username},
                "password": {"password": MIGRATE_PASSWORD},
            }
        },
        timeout=15,
    )
    if r.status_code != 201:
        raise requests.RequestException(
            f"Zitadel session auth failed ({r.status_code}): {r.text[:200]}"
        )


def _authentik_blueprint_yaml() -> str:
    entries = []
    for name in _usernames():
        suffix = name.split("-")[-1]
        entries.append(
            textwrap.dedent(
                f"""
                - model: authentik_core.user
                  state: present
                  identifiers:
                    username: {name}
                  attrs:
                    username: {name}
                    name: Migrate User {suffix}
                    is_active: true
                    path: users
                    type: internal
                    password: {MIGRATE_PASSWORD}
                """
            ).strip()
        )
    return "version: 1\nmetadata:\n  name: legacy-user-migration\nentries:\n" + "\n".join(entries)


def _bulk_import_authentik(cfg: dict[str, Any], token: str) -> None:
    blueprint = _authentik_blueprint_yaml()
    r = requests.post(
        f"{cfg['base_url']}/api/v3/managed/blueprints/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"legacy-user-migration-{int(time.time())}", "content": blueprint},
        timeout=60,
    )
    if r.status_code >= 400:
        raise requests.RequestException(
            f"Authentik blueprint create failed ({r.status_code}): {r.text[:200]}"
        )
    pk = r.json().get("pk")
    r = requests.post(
        f"{cfg['base_url']}/api/v3/managed/blueprints/{pk}/apply/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    if r.status_code >= 400:
        raise requests.RequestException(
            f"Authentik blueprint apply failed ({r.status_code}): {r.text[:200]}"
        )
    time.sleep(2)


def _list_authentik(cfg: dict[str, Any], token: str) -> set[str]:
    found: set[str] = set()
    for name in _usernames():
        r = requests.get(
            f"{cfg['base_url']}/api/v3/core/users/",
            headers={"Authorization": f"Bearer {token}"},
            params={"username": name},
            timeout=15,
        )
        r.raise_for_status()
        if r.json().get("pagination", {}).get("count", 0) > 0:
            found.add(name)
    return found


def _auth_authentik(cfg: dict[str, Any], username: str) -> None:
    session = requests.Session()
    r = session.get(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        timeout=15,
    )
    r.raise_for_status()
    r = session.post(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        json={"uid_field": username},
        timeout=15,
    )
    r.raise_for_status()
    r = session.post(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        json={"password": MIGRATE_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    if r.json().get("component") != "xak-flow-redirect":
        raise requests.RequestException("Authentik authentication flow did not complete")


def _run_keycloak(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = keycloak_admin_token(cfg)
    _bulk_import_keycloak(cfg, token)
    found = _list_keycloak(cfg, token)
    if len(found) < USER_COUNT:
        missing = set(_usernames()) - found
        return False, f"Only {len(found)}/{USER_COUNT} users found; missing: {', '.join(sorted(missing)[:3])}"
    _auth_keycloak(cfg, _usernames()[0])
    return True, f"Bulk imported {USER_COUNT} users; authenticated as {_usernames()[0]}"


def _run_zitadel(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    pat = zitadel_pat(cfg)
    _bulk_import_zitadel(cfg, pat)
    found = _list_zitadel(cfg, pat)
    if len(found) < USER_COUNT:
        missing = set(_usernames()) - found
        return False, f"Only {len(found)}/{USER_COUNT} users found; missing: {', '.join(sorted(missing)[:3])}"
    _auth_zitadel(cfg, _usernames()[0])
    return True, f"Bulk imported {USER_COUNT} users; authenticated as {_usernames()[0]}"


def _run_authentik(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    token = authentik_token(cfg)
    _bulk_import_authentik(cfg, token)
    found = _list_authentik(cfg, token)
    if len(found) < USER_COUNT:
        missing = set(_usernames()) - found
        return False, f"Only {len(found)}/{USER_COUNT} users found; missing: {', '.join(sorted(missing)[:3])}"
    _auth_authentik(cfg, _usernames()[0])
    return True, f"Bulk imported {USER_COUNT} users; authenticated as {_usernames()[0]}"


def _run_system(system: str, cfg: dict[str, Any]) -> dict[str, Any]:
    runners = {
        "keycloak": _run_keycloak,
        "zitadel": _run_zitadel,
        "authentik": _run_authentik,
    }
    start = time.perf_counter()
    try:
        passed, message = runners[system](cfg)
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(system, LEVEL, CHALLENGE, passed, elapsed, message)
    except requests.RequestException as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(system, LEVEL, CHALLENGE, False, elapsed, str(exc), partial=True)
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - start) * 1000)
        return result(system, LEVEL, CHALLENGE, False, elapsed, str(exc))


def run(system_filter: str | None = None) -> list[dict]:
    targets = [system_filter] if system_filter else list(SYSTEMS)
    return [_run_system(system, get_system_config(system)) for system in targets if system in SYSTEMS]
