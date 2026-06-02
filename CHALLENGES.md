# IAM Challenge Lab — Reference

Technical reference for the 18 cross-system challenges under `challenges/level1_basic` through `level6_hardening`. Each challenge runs against Keycloak, Zitadel, and Authentik (when up) and records results in `challenges/results.json`.

## Result semantics

| Outcome | `passed` | `partial` | Meaning |
|---------|----------|-----------|---------|
| **Pass** | `true` | `false` | Primary assertion succeeded. |
| **Partial** | `false` | `true` | Endpoint or subsystem responded, but the strict success criterion was not met (common on dev defaults). Counts as non-failing in `verify.py`. |
| **Fail** | `false` | `false` | Assertion failed after one retry (5 s). Requires setup fix or system unavailable. |

Challenges at levels 2–6 use `partial_on_fail=True` unless noted. Informational text may appear in the `error` field even on pass (e.g. Zitadel PAT fallback paths).

**Prerequisites:** `make setup` (realm/client/user bootstrap). Zitadel requires `setup/zitadel/.pat`; Authentik requires `setup/authentik/.token`.

---

## Level 1 — Basic Auth

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `create_user` | Bootstrap user `testuser` exists | User lifecycle / directory | User returned by admin search API | — | Admin REST: `GET /admin/realms/{realm}/users?username=` | gRPC-over-HTTP: `POST /v2/users` (search) with PAT | REST: `GET /api/v3/core/users/?username=` |
| `get_token` | Token or credential path works | OAuth 2.0 / OIDC issuance | Keycloak: client-credentials token; Zitadel: PAT validates user API; Authentik: OAuth2 app registered | — | `POST .../token` (`client_credentials`) | PAT + user search (no OIDC client required in lab) | Application slug `iam-lab-client` exists |
| `verify_token` | Issued credential is usable | Token validation / userinfo | Keycloak: userinfo returns `preferred_username`; Authentik: `/users/me/` returns username | Zitadel: `/debug/ready` when PAT cannot call userinfo | Userinfo with password-grant access token (`scope=openid profile email`) | PAT on `/oauth/v2/userinfo` often 401; falls back to readiness | API token introspection via `/api/v3/core/users/me/` |

**Notable differences:** Keycloak password grant requires `firstName`/`lastName` on the user or returns `invalid_grant` / userinfo 403 without `openid` scope. Zitadel lab uses a login-client PAT, not an OIDC app secret. Authentik `get_token` checks application registration, not end-user OIDC token exchange.

---

## Level 2 — MFA

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `enable_totp` | TOTP policy / stage availability | MFA (TOTP) | Keycloak: realm `otpPolicyType == totp` | Authentik: TOTP stages API 404; Zitadel: login policy API 404 | Realm admin: `GET /admin/realms/{realm}` | `POST /admin/v1/policies/login` or `/v2/features` | `GET /api/v3/stages/authenticator_totp/` |
| `enable_passkey` | WebAuthn / passkey support exposed | MFA (WebAuthn / FIDO2) | Keycloak: `webauthn-authenticator` in provider list | Zitadel / Authentik: API reachable but enrollment not automated | Auth flow providers admin API | Features API probe only | WebAuthn stages endpoint (404 in default install) |
| `brute_force` | Account lockout / failed-login handling | Brute-force mitigation | Zitadel: bad password returns 4xx on token endpoint | Keycloak: `bruteForceProtected=false` on dev realm; Authentik: flow returns 200 on bad creds | Reads `bruteForceProtected` from realm config | Live failed `password` grant | Posts to default authentication flow executor |

**Notable differences:** Keycloak brute-force protection is off in default `start-dev` realms. Zitadel and Authentik tests observe runtime rejection, not policy flags. None of the three enroll TOTP/passkeys in this lab — only policy/API surface checks.

---

## Level 3 — Federation

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `ldap_connect` | LDAP / directory federation API | User federation (LDAP) | All: federation or IdP list API returns 2xx | — | User storage components admin API | `GET /admin/v1/idps` | `GET /api/v3/sources/ldap/` |
| `saml_sp` | SAML SP metadata / provider API | SAML 2.0 SP / IdP | Keycloak: public SAML descriptor contains `EntityDescriptor` | Zitadel: metadata endpoint 404 acceptable if &lt;500 | Unauthenticated `.../protocol/saml/descriptor` | `GET /v2/saml/metadata` with PAT | `GET /api/v3/providers/saml/` |
| `social_login` | Social / OIDC IdP federation API | Social login / external IdP | All: identity-provider or OAuth source list API 2xx | — | `GET .../identity-provider/instances` | `POST /v2/idps` (search) | `GET /api/v3/sources/oauth/` |

**Notable differences:** Keycloak exposes SAML metadata without auth. Zitadel consolidates external IdPs under `/v2/idps`; SAML may need explicit enablement. Authentik splits LDAP (`sources/ldap`) and OAuth (`sources/oauth`) into separate resource types.

---

## Level 4 — Custom Flows

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `step_up_auth` | Step-up / elevated authentication flows | Step-up authentication | Keycloak: browser flow exists; Authentik: flows API 200 | Zitadel: readiness only (login policy in console) | Authentication flows admin API | `/debug/ready` | `GET /api/v3/flows/instances/` |
| `risk_based` | Conditional / risk-based access policies | Risk-based / conditional access | Authentik: expression policies API 200; Zitadel: console reachable | Keycloak: conditional authenticator API reachable only | Conditional credential authenticators endpoint | Console HTTP probe | `GET /api/v3/policies/expression/` |
| `biometric_stub` | Biometric / WebAuthn readiness | Biometric authentication (stub) | Keycloak: OIDC discovery 200; Zitadel: ready | Authentik: validation stages 404 | Discovery document only — no enrollment | Readiness check | Authenticator validate stages API |

**Notable differences:** Authentik models flows as first-class Flow objects with stages. Keycloak uses authentication flow bindings. Zitadel defers custom login policy to console/API not fully exercised in lab.

---

## Level 5 — Authorization

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `abac_test` | Attribute / policy-based authorization API | ABAC / policy engine | Authentik: policies API 200; Keycloak: authz policy endpoint 200 or 404 (no authz enabled) | Zitadel: readiness only — ABAC via project roles | Keycloak Authorization Services per-client | No automated ABAC probe | Unified `/api/v3/policies/all/` |
| `role_hierarchy` | Role model listing | RBAC / role hierarchy | Keycloak: realm roles listed; Authentik: RBAC roles API 200 | Zitadel: project roles search 404 | Realm roles admin API | `POST .../projects/roles/_search` | `GET /api/v3/rbac/roles/` |
| `token_claims` | Access token carries expected claims | Token claims / mappers | Keycloak: userinfo 200 after password grant; Authentik: OIDC metadata 200 | Keycloak partial possible if userinfo 403 without scope | Password grant + userinfo | `/debug/ready` with PAT | `/.well-known/openid-configuration` on app slug |

**Notable differences:** Keycloak Authorization Services (UMA/ABAC) is opt-in per client. Zitadel authorization is project-role-centric. Authentik binds policies to flows, applications, and objects via a single policy API.

---

## Level 6 — Hardening

| Challenge | Tests | IAM concept | Pass | Partial | Keycloak | Zitadel | Authentik |
|-----------|-------|-------------|------|---------|----------|---------|-----------|
| `tenant_isolation` | Multi-tenant boundary primitives | Tenant / org isolation | Keycloak: `iam-lab` realm listed; Zitadel: org search API | Authentik: `/core/tenants/` 404 (single-tenant default) | Realms as isolation boundary | Organizations (`POST /v2/organizations/_search`) | Tenants API (enterprise / multi-tenant) |
| `token_revocation` | Session / token teardown | Token revocation / logout | Keycloak: logout 204 with refresh token; Zitadel: revoke endpoint responds | — | OIDC logout with `refresh_token` | `GET /oauth/v2/revoke` status probe | Session-end URL probe |
| `audit_log` | Security event retrieval | Audit logging | Keycloak + Authentik: events API 200 | Zitadel: events search may return 403 without PAT scope | Realm events admin API | `POST /admin/v1/events/_search` | `GET /api/v3/events/events/` |

**Notable differences:** Keycloak isolates by realm; Zitadel by organization/instance; Authentik single-tenant OSS lacks `/core/tenants/`. Revocation: Keycloak uses RFC 7009-style logout; Authentik uses flow-based session end; Zitadel revoke requires client context.

---

## Execution

```bash
make setup                  # bootstrap all three systems
python3 verify.py           # health check + all challenges + summary
make challenge L=1          # single level
make report                 # terminal table from results.json
```

Challenge modules export `run(system_filter=None) -> list[dict]` returning objects with fields: `system`, `level`, `challenge_name`, `passed`, `response_time_ms`, `error`, `partial`.
