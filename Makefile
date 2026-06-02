COMPOSE := docker compose --env-file .env
PROFILES := --profile keycloak --profile zitadel --profile authentik --profile gluu
VALID_PROFILES := keycloak zitadel authentik gluu

.PHONY: help up down logs ps

help:
	@echo "IAM Open Source Lab"
	@echo ""
	@echo "Usage:"
	@echo "  make up PROFILE=<name>    Start Portainer + chosen IAM system"
	@echo "  make down                 Stop and remove all services"
	@echo "  make logs PROFILE=<name>  Tail logs for the chosen system"
	@echo "  make ps                   Show container status"
	@echo ""
	@echo "Profiles: $(VALID_PROFILES)"

up:
ifndef PROFILE
	$(error PROFILE is required. Example: make up PROFILE=keycloak)
endif
	@test -n "$(filter $(PROFILE),$(VALID_PROFILES))" || \
		(echo "Invalid PROFILE '$(PROFILE)'. Valid: $(VALID_PROFILES)" && exit 1)
	@if ss -tln | grep -q ':9000 '; then \
		echo "Port 9000 already in use — skipping iam-portainer (use existing Portainer at http://localhost:9000)"; \
		$(COMPOSE) --profile $(PROFILE) up -d --scale portainer=0; \
	else \
		$(COMPOSE) --profile $(PROFILE) up -d; \
	fi

down:
	$(COMPOSE) $(PROFILES) down --remove-orphans

logs:
ifndef PROFILE
	$(error PROFILE is required. Example: make logs PROFILE=keycloak)
endif
	@test -n "$(filter $(PROFILE),$(VALID_PROFILES))" || \
		(echo "Invalid PROFILE '$(PROFILE)'. Valid: $(VALID_PROFILES)" && exit 1)
	$(COMPOSE) --profile $(PROFILE) logs -f $(LOGS_$(PROFILE))

ps:
	$(COMPOSE) $(PROFILES) ps -a

LOGS_keycloak := keycloak-postgres keycloak
LOGS_zitadel := zitadel-postgres zitadel zitadel-login
LOGS_authentik := authentik-postgres authentik-server authentik-worker
LOGS_gluu := gluu-postgres gluu

# ---------------------------------------------------------------------------
# Challenge lab targets (appended — existing targets above stay intact)
# ---------------------------------------------------------------------------

.PHONY: setup challenge dashboard reset report

setup:
	python3 setup/keycloak/init.py
	python3 setup/zitadel/init.py
	python3 setup/authentik/init.py

challenge:
ifndef L
	$(error L is required. Example: make challenge L=1 or L=all)
endif
	@python3 challenges/runner.py --level $(L) \
		$(if $(SYSTEM),--system $(SYSTEM),) \
		$(if $(CHALLENGE),--challenge $(CHALLENGE),)

dashboard:
	@echo "Dashboard: http://127.0.0.1:8765/dashboard/"
	@python3 -m http.server 8765 --bind 127.0.0.1

reset:
	rm -f challenges/results.json
	@echo "[]" > challenges/results.json
	@echo "Results cleared. Run: make setup && make challenge L=all"

report:
	@python3 challenges/report.py
