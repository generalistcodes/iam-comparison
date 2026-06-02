"""Level 1: decode JWT manually, verify signature via JWKS, check standard claims."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from config import SYSTEMS, get_system_config
from helpers import keycloak_realm_token
from jwt_decode import (
    check_standard_claims,
    decode_jwt_parts,
    fetch_jwks,
    format_decoded_jwt,
    resolve_jwks_url,
    verify_rs_signature,
)
from lib import result

LEVEL = 1
CHALLENGE = "decode_token"
AUTHENTIK_REDIRECT_URI = "http://localhost:1234/callback"


def _acquire_authentik_token(cfg: dict[str, Any]) -> str:
    session = requests.Session()
    session.get(f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/", timeout=15)
    session.post(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        json={"uid_field": cfg["test_user"]},
        timeout=15,
    ).raise_for_status()
    session.post(
        f"{cfg['base_url']}/api/v3/flows/executor/default-authentication-flow/",
        json={"password": cfg["test_password"]},
        timeout=15,
    ).raise_for_status()
    auth = session.get(
        f"{cfg['base_url']}/application/o/authorize/",
        params={
            "client_id": cfg["client_id"],
            "response_type": "code",
            "redirect_uri": AUTHENTIK_REDIRECT_URI,
            "scope": "openid profile email",
        },
        allow_redirects=False,
        timeout=15,
    )
    location = auth.headers.get("Location", "")
    if auth.status_code not in (302, 303) or "code=" not in location:
        raise requests.RequestException(
            f"Authentik authorize failed ({auth.status_code}): {location[:200]}"
        )
    code = parse_qs(urlparse(location).query).get("code", [""])[0]
    token_resp = requests.post(
        f"{cfg['base_url']}/application/o/token/",
        data={
            "grant_type": "authorization_code",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "redirect_uri": AUTHENTIK_REDIRECT_URI,
        },
        timeout=15,
    )
    if token_resp.status_code != 200:
        raise requests.RequestException(
            f"Authentik token exchange failed ({token_resp.status_code}): {token_resp.text[:200]}"
        )
    token = token_resp.json().get("access_token", "")
    if not token:
        raise requests.RequestException("Empty access token from Authentik")
    return token


def _acquire_token(system: str, cfg: dict[str, Any]) -> str:
    if system == "keycloak":
        return keycloak_realm_token(cfg)

    if system == "zitadel":
        r = requests.post(
            f"{cfg['base_url']}/oauth/v2/token",
            data={
                "grant_type": "password",
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "username": cfg["test_user"],
                "password": cfg["test_password"],
                "scope": "openid profile email urn:zitadel:iam:org:project:id:zitadel:aud",
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise requests.RequestException(
                "Zitadel JWT unavailable — configure OIDC client iam-lab-client via make setup"
            )
        token = r.json().get("access_token", "")
        if not token:
            raise requests.RequestException("Empty access token from Zitadel")
        return token

    return _acquire_authentik_token(cfg)


def _jwks_fallbacks(system: str, cfg: dict[str, Any]) -> list[str]:
    if system == "keycloak":
        return [f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/certs"]
    if system == "zitadel":
        return [f"{cfg['base_url']}/oauth/v2/keys"]
    return [f"{cfg['base_url']}/application/o/{cfg['client_id']}/jwks/"]


def _run_system(system: str, cfg: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    jwks_fetch_ms: int | None = None
    try:
        token = _acquire_token(system, cfg)
        header, payload, signature, signing_input = decode_jwt_parts(token)
        decoded_text = format_decoded_jwt(header, payload)
        print(f"[{system}] decoded JWT:\n{decoded_text}")

        claims_ok, missing = check_standard_claims(payload)
        if not claims_ok:
            elapsed = int((time.perf_counter() - start) * 1000)
            return result(
                system,
                LEVEL,
                CHALLENGE,
                False,
                elapsed,
                f"Missing claims: {', '.join(missing)}",
            )

        issuer = str(payload["iss"])
        jwks_url = resolve_jwks_url(issuer, _jwks_fallbacks(system, cfg))
        jwks, jwks_fetch_ms = fetch_jwks(jwks_url)
        verified, verify_error = verify_rs_signature(header, signing_input, signature, jwks)
        elapsed = int((time.perf_counter() - start) * 1000)

        if verified:
            return result(
                system,
                LEVEL,
                CHALLENGE,
                True,
                elapsed,
                f"jwks_fetch={jwks_fetch_ms}ms; all claims present; signature verified",
                jwks_fetch_ms=jwks_fetch_ms,
            )

        return result(
            system,
            LEVEL,
            CHALLENGE,
            False,
            elapsed,
            f"jwks_fetch={jwks_fetch_ms}ms; claims present; JWKS verification failed: {verify_error}",
            partial=True,
            jwks_fetch_ms=jwks_fetch_ms,
        )
    except requests.RequestException as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        err = str(exc)
        if jwks_fetch_ms is not None:
            err = f"jwks_fetch={jwks_fetch_ms}ms; {err}"
        return result(system, LEVEL, CHALLENGE, False, elapsed, err, jwks_fetch_ms=jwks_fetch_ms)
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - start) * 1000)
        err = str(exc)
        if jwks_fetch_ms is not None:
            err = f"jwks_fetch={jwks_fetch_ms}ms; {err}"
        return result(system, LEVEL, CHALLENGE, False, elapsed, err, jwks_fetch_ms=jwks_fetch_ms)


def run(system_filter: str | None = None) -> list[dict]:
    targets = [system_filter] if system_filter else list(SYSTEMS)
    return [_run_system(system, get_system_config(system)) for system in targets if system in SYSTEMS]
