.DEFAULT_GOAL := help

COMPOSE ?= docker compose
PYTHON ?= python3
NPM ?= npm
WAIT_TIMEOUT ?= 120

.PHONY: help demo up down status logs config smoke verify test frontend-check

help:
	@echo "CurbOps AI | Local workflows"
	@echo "  make demo            Build, start and smoke-check the demo"
	@echo "  make up              Build and start services; wait until ready"
	@echo "  make status          Show service state"
	@echo "  make logs            Show the last 80 lines per service"
	@echo "  make smoke           Check the running API and web entry point"
	@echo "  make verify          Run backend tests, frontend types and production build"
	@echo "  make down            Stop the local stack"

demo: up
	$(MAKE) smoke
	@echo "CurbOps AI is ready at http://localhost:3000"

config:
	$(COMPOSE) config --quiet

up: config
	$(COMPOSE) up --build --wait --wait-timeout $(WAIT_TIMEOUT)

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --tail=80

smoke:
	$(COMPOSE) exec -T api python - http://localhost:8000 --web-url http://web:3000 < scripts/smoke.py

verify: test frontend-check

test:
	cd backend && $(PYTHON) -m pytest -q

frontend-check:
	$(NPM) --prefix frontend run lint
	$(NPM) --prefix frontend run build
