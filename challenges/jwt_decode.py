"""Manual JWT parsing and JWKS signature verification (no JWT library)."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import requests
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.hashes import SHA256, SHA384, SHA512

STANDARD_CLAIMS = ("iss", "aud", "exp", "iat", "sub")


def b64url_decode(data: str) -> bytes:
    padding_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * padding_len))


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode_jwt_parts(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT must have header.payload.signature")
    header = json.loads(b64url_decode(parts[0]))
    payload = json.loads(b64url_decode(parts[1]))
    signature = b64url_decode(parts[2])
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    return header, payload, signature, signing_input


def format_decoded_jwt(header: dict[str, Any], payload: dict[str, Any]) -> str:
    return json.dumps({"header": header, "payload": payload}, indent=2, sort_keys=True)


def check_standard_claims(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = [claim for claim in STANDARD_CLAIMS if claim not in payload or payload[claim] in (None, "")]
    return not missing, missing


def _int_from_b64url(value: str) -> int:
    return int.from_bytes(b64url_decode(value), byteorder="big", signed=False)


def jwk_to_public_key(jwk: dict[str, Any]) -> RSAPublicKey:
    if jwk.get("kty") != "RSA":
        raise ValueError(f"Unsupported key type: {jwk.get('kty')}")
    numbers = rsa.RSAPublicNumbers(_int_from_b64url(jwk["e"]), _int_from_b64url(jwk["n"]))
    return numbers.public_key()


def _hash_for_alg(alg: str):
    if alg in ("RS256", "PS256"):
        return SHA256()
    if alg in ("RS384", "PS384"):
        return SHA384()
    if alg in ("RS512", "PS512"):
        return SHA512()
    raise ValueError(f"Unsupported algorithm: {alg}")


def verify_rs_signature(
    header: dict[str, Any],
    signing_input: bytes,
    signature: bytes,
    jwks: dict[str, Any],
) -> tuple[bool, str | None]:
    alg = header.get("alg", "")
    if not alg.startswith(("RS", "PS")):
        return False, f"Unsupported JWT alg: {alg}"

    kid = header.get("kid")
    keys = jwks.get("keys") or []
    candidates = [k for k in keys if kid is None or k.get("kid") == kid]
    if not candidates and keys:
        candidates = keys

    errors: list[str] = []
    for jwk in candidates:
        try:
            public_key = jwk_to_public_key(jwk)
            if alg.startswith("RS"):
                public_key.verify(
                    signature,
                    signing_input,
                    padding.PKCS1v15(),
                    _hash_for_alg(alg),
                )
            elif alg.startswith("PS"):
                public_key.verify(
                    signature,
                    signing_input,
                    padding.PSS(
                        mgf=padding.MGF1(_hash_for_alg(alg)),
                        salt_length=_hash_for_alg(alg).digest_size,
                    ),
                    _hash_for_alg(alg),
                )
            else:
                return False, f"Unsupported JWT alg: {alg}"
            return True, None
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    if not candidates:
        return False, "No matching JWK found"
    return False, errors[0] if errors else "Signature verification failed"


def fetch_jwks(jwks_url: str, timeout: int = 15) -> tuple[dict[str, Any], int]:
    start = time.perf_counter()
    r = requests.get(jwks_url, timeout=timeout)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    r.raise_for_status()
    return r.json(), elapsed_ms


def resolve_jwks_url(issuer: str, fallback_urls: list[str]) -> str:
    well_known = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        r = requests.get(well_known, timeout=10)
        if r.status_code == 200:
            jwks_uri = r.json().get("jwks_uri")
            if jwks_uri:
                return jwks_uri
    except requests.RequestException:
        pass
    return fallback_urls[0]
