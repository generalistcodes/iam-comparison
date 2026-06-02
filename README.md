[![GitHub stars](https://img.shields.io/github/stars/iamscenarios/iam-opensource?style=social)](https://github.com/iamscenarios/iam-opensource) [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

A systematic comparison of Keycloak, Zitadel, Authentik, and Gluu running as isolated Docker Compose profiles. Each system gets its own PostgreSQL instance. Portainer always runs for visual container management. Designed for engineers evaluating open-source IAM systems side by side — from basic OIDC flows to enterprise hardening. Part of [iamscenarios.com](https://iamscenarios.com).

## Challenge Framework

This lab includes 18 automated challenges across 6 levels — authentication, MFA, federation, custom flows, authorization, and enterprise hardening — tested identically against each system. Run `python3 verify.py` to execute all challenges against the currently running system and generate a comparison report in `challenges/results.json`. Open `dashboard/index.html` to view results visually.

# IAM Open Source Lab

Run **Keycloak**, **Zitadel**, **Authentik**, or **Gluu** one at a time via Docker Compose profiles. Each profile starts only that IAM system and its own dedicated PostgreSQL database. **Portainer** always runs on port 9000.

## Quick start

```bash
cp .env.example .env
make up PROFILE=keycloak
```

Only one IAM profile should run at a time. Stop the current system before starting another:

```bash
make down
make up PROFILE=zitadel
```

## Makefile

| Command | Description |
|---------|-------------|
| `make up PROFILE=keycloak` | Start Portainer + Keycloak + its Postgres |
| `make up PROFILE=zitadel` | Start Portainer + Zitadel + its Postgres |
| `make up PROFILE=authentik` | Start Portainer + Authentik + its Postgres |
| `make up PROFILE=gluu` | Start Portainer + Gluu + its Postgres |
| `make down` | Stop and remove all services |
| `make logs PROFILE=keycloak` | Tail logs for the chosen system |
| `make ps` | Show container status |
| `make setup` | Bootstrap test realm, client, and user on Keycloak, Zitadel, and Authentik |
| `make challenge L=1` | Run level 1 challenges only |
| `make challenge L=all` | Run all 18 challenges across all levels |
| `make dashboard` | Serve `dashboard/index.html` at http://127.0.0.1:8765 |
| `make report` | Print `challenges/results.json` as a terminal table |
| `make reset` | Clear `results.json` for a fresh challenge run |

Valid profiles: `keycloak`, `zitadel`, `authentik`, `gluu`

## Port map

| Service | URL | Profile |
|---------|-----|---------|
| **Portainer** | http://localhost:9000 | always |
| **Keycloak Admin Console** | http://localhost:8080/admin | keycloak |
| **Zitadel Console** | http://localhost:8081/ui/console | zitadel |
| **Zitadel Login UI** | http://localhost:3001/ui/v2/login | zitadel |
| **Authentik Admin UI** | http://localhost:9090 | authentik |
| **Gluu Admin UI** | https://localhost:8443 | gluu |
| **Gluu HTTP** | http://localhost:8083 | gluu |

PostgreSQL databases are internal to each profile and not exposed on the host.

## RAM requirements

Minimum host RAM to run **Portainer + one IAM system**:

| System | Minimum RAM | Recommended RAM | Notes |
|--------|-------------|-----------------|-------|
| **Keycloak** | 1 GB | 2 GB | Lightweight dev mode (`start-dev`) |
| **Zitadel** | 1 GB | 2 GB | First init takes ~1 min |
| **Authentik** | 2 GB | 4 GB | Server + worker + Postgres ([official minimum](https://docs.goauthentik.io/install-config/install/docker-compose)) |
| **Gluu Flex** | 4 GB | 8 GB | Monolith bundles auth-server, config-api, SCIM, FIDO2, Casa, Admin UI |
| **Portainer** | 128 MB | 256 MB | Always running |

## First-login credentials

| System | URL | Username | Password | Notes |
|--------|-----|----------|----------|-------|
| **Keycloak** | http://localhost:8080/admin | `admin` | `admin` | Ready immediately |
| **Zitadel** | http://localhost:8081/ui/console | `zitadel-admin@zitadel.localhost` | `Password1!` | Created on first init |
| **Authentik** | http://localhost:9090/if/flow/initial-setup/ | `akadmin` | *(you choose)* | Run initial setup wizard on first visit |
| **Gluu** | https://localhost:8443 | `admin` | `1t5Fin3#security` | Add `127.0.0.1 demoexample.gluu.org` to `/etc/hosts`; accept self-signed cert |
| **Portainer** | http://localhost:9000 | *(you choose)* | *(you choose)* | Create admin on first visit |

## Gluu setup note

Gluu expects the hostname `demoexample.gluu.org` (configurable via `GLUU_HOSTNAME` in `.env`). Add it to your hosts file:

```bash
echo "127.0.0.1 demoexample.gluu.org" | sudo tee -a /etc/hosts
```

Then open https://demoexample.gluu.org:8443 or https://localhost:8443.

Gluu first boot can take several minutes while the monolith installs and configures all services.

## Architecture

```
make up PROFILE=keycloak
├── portainer          (always, port 9000)
├── keycloak-postgres  (profile: keycloak)
└── keycloak           (profile: keycloak, port 8080)

make up PROFILE=zitadel
├── portainer
├── zitadel-postgres
├── zitadel            (port 8081)
└── zitadel-login      (port 3001)

make up PROFILE=authentik
├── portainer
├── authentik-postgres
├── authentik-server   (port 9090)
└── authentik-worker

make up PROFILE=gluu
├── portainer
├── gluu-postgres
└── gluu               (ports 8083/8443)
```

## Reset data

```bash
make down
docker volume rm iam-opensource_keycloak_postgres_data   # keycloak only
docker volume rm iam-opensource_zitadel_postgres_data iam-opensource_zitadel_data  # zitadel only
docker volume rm iam-opensource_authentik_postgres_data  # authentik only
docker volume rm iam-opensource_gluu_postgres_data       # gluu only
```

## Notes

- For local development only. Change all default passwords before exposing to a network.
- If port **9000** is already in use (e.g. by another Portainer instance), `make up` skips `iam-portainer` automatically and uses the existing one at http://localhost:9000.
- Gluu image `0.0.0-nightly` is for testing only; use [Gluu Helm charts](https://docs.gluu.org/stable/install/helm/) for production.

## Contributing

PRs welcome — new challenge scripts, additional IAM systems, or dashboard improvements. See [CHALLENGES.md](CHALLENGES.md) for the challenge format.
