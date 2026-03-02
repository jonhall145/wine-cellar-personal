VIRTUAL_ENV ?= venv
PYTHON ?= python3.12
NODE_BIN = node_modules/.bin
SOURCE_DIRS = wine_cellar tests
ARGUMENTS=$(filter-out $(firstword $(MAKECMDGOALS)), $(MAKECMDGOALS))
DEV_COMPOSE = docker compose -f docker-compose.yml
PROD_COMPOSE = docker compose -f docker-compose.prod.yml
GHCR_IMAGE ?= ghcr.io/jonhall145/wine-cellar-personal:latest
NODE_RUN = docker run --rm -v "$$(pwd)":/app -v /app/node_modules -w /app node:20-slim

.PHONY: all
all: help

.PHONY: help
help:
	@echo ""
	@echo "  Wine & Whisky Cellar"
	@echo "  ===================="
	@echo ""
	@echo "  Setup"
	@echo "    make install              Build and start Docker dev stack"
	@echo "    make clean                Remove local node/venv artifacts"
	@echo "    make fixtures             Load wine sample data"
	@echo "    make whisky-fixtures      Load whisky sample data"
	@echo ""
	@echo "  Development"
	@echo "    make server               Wine dev server (port 8003)"
	@echo "    make watch                Wine dev server + frontend rebuild"
	@echo "    make whisky-server        Whisky dev server (port 8004)"
	@echo "    make whisky-watch         Whisky dev server + frontend rebuild"
	@echo ""
	@echo "  Testing"
	@echo "    make pytest               Run all tests"
	@echo "    make whisky-pytest        Run whisky tests only"
	@echo "    make pytest-lastfailed    Re-run failed tests"
	@echo "    make pytest-clean         Delete test DB and run all tests"
	@echo "    make coverage             Run tests with coverage report"
	@echo "    make smoke-test           Run smoke test against local server"
	@echo ""
	@echo "  Linting"
	@echo "    make lint                 Run all linters (isort, flake8, eslint, migrations)"
	@echo "    make lint-quick           Quick lint (eslint staged + migrations)"
	@echo "    make lint-js-fix          Auto-fix JS/TS lint errors"
	@echo "    make lint-py [FILES]      Lint Python files (black, isort, flake8)"
	@echo "    make lint-html [FILES]    Lint Django templates"
	@echo "    make lint-html-fix [FILES] Auto-fix template lint errors"
	@echo ""
	@echo "  Deploy (Docker)"
	@echo "    make deploy               Rebuild and redeploy full production stack"
	@echo "    make wine-deploy          Build/deploy wine app and restart nginx"
	@echo "    make whisky-deploy        Build/deploy whisky app and restart nginx"
	@echo "    make ghcr-deploy          Pull/deploy from GitHub Container Registry image"
	@echo ""
	@echo "  Production"
	@echo "    make wine-prod-start      Start wine container"
	@echo "    make wine-prod-stop       Stop wine container"
	@echo "    make wine-prod-restart    Restart wine container"
	@echo "    make wine-prod-status     Show wine container status"
	@echo "    make wine-prod-logs       Tail wine container logs"
	@echo "    make whisky-prod-start    Start whisky container"
	@echo "    make whisky-prod-stop     Stop whisky container"
	@echo "    make whisky-prod-restart  Restart whisky container"
	@echo "    make whisky-prod-status   Show whisky container status"
	@echo "    make whisky-prod-logs     Tail whisky container logs"
	@echo ""

.PHONY: install
install:
	$(DEV_COMPOSE) build web
	$(DEV_COMPOSE) up -d web

.PHONY: clean
clean:
	if [ -f package-lock.json ]; then rm package-lock.json; fi
	if [ -d node_modules ]; then rm -rf node_modules; fi
	if [ -d venv ]; then rm -rf venv; fi

.PHONY: server
server:
	$(DEV_COMPOSE) up web

.PHONY: watch
watch:
	trap 'kill %1' KILL; \
	npm run watch & \
	$(DEV_COMPOSE) up web

.PHONY: fixtures
fixtures:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T web python manage.py loaddata fixtures/user.json
	$(DEV_COMPOSE) exec -T web python manage.py loaddata fixtures/grapes.json
	$(DEV_COMPOSE) exec -T web python manage.py loaddata fixtures/appellations.json
	$(DEV_COMPOSE) exec -T web python manage.py loaddata fixtures/wines.json
	$(DEV_COMPOSE) exec -T web python manage.py loaddata fixtures/stock.json

.PHONY: deploy
deploy:
	$(PROD_COMPOSE) up -d --build --force-recreate

.PHONY: ghcr-deploy
ghcr-deploy:
	docker pull $(GHCR_IMAGE)
	docker tag $(GHCR_IMAGE) wine-cellar:prod
	$(PROD_COMPOSE) up -d --no-build --force-recreate

.PHONY: wine-deploy
wine-deploy:
	$(PROD_COMPOSE) build wine-web
	$(PROD_COMPOSE) up -d wine-web
	$(PROD_COMPOSE) restart nginx

.PHONY: wine-prod-start
wine-prod-start:
	$(PROD_COMPOSE) up -d wine-web

.PHONY: wine-prod-stop
wine-prod-stop:
	$(PROD_COMPOSE) stop wine-web

.PHONY: wine-prod-restart
wine-prod-restart:
	$(PROD_COMPOSE) restart wine-web

.PHONY: wine-prod-status
wine-prod-status:
	$(PROD_COMPOSE) ps wine-web

.PHONY: wine-prod-logs
wine-prod-logs:
	$(PROD_COMPOSE) logs -f wine-web

.PHONY: whisky-fixtures
whisky-fixtures:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T -e CELLAR_APP_TYPE=whisky web python manage.py loaddata fixtures/whisky_regions.json
	$(DEV_COMPOSE) exec -T -e CELLAR_APP_TYPE=whisky web python manage.py loaddata fixtures/distilleries.json
	$(DEV_COMPOSE) exec -T -e CELLAR_APP_TYPE=whisky web python manage.py loaddata fixtures/bottlers.json

.PHONY: whisky-server
whisky-server:
	$(DEV_COMPOSE) run --rm --service-ports -p 8004:8000 -e CELLAR_APP_TYPE=whisky web python manage.py runserver 0.0.0.0:8000

.PHONY: whisky-watch
whisky-watch:
	trap 'kill %1' KILL; \
	npm run watch & \
	$(DEV_COMPOSE) run --rm --service-ports -p 8004:8000 -e CELLAR_APP_TYPE=whisky web python manage.py runserver 0.0.0.0:8000

.PHONY: whisky-pytest
whisky-pytest:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T -e CELLAR_APP_TYPE=whisky web py.test tests/whisky/ --reuse-db

.PHONY: whisky-deploy
whisky-deploy:
	$(PROD_COMPOSE) build wine-web
	$(PROD_COMPOSE) up -d whisky-web
	$(PROD_COMPOSE) restart nginx

.PHONY: whisky-prod-start
whisky-prod-start:
	$(PROD_COMPOSE) up -d whisky-web

.PHONY: whisky-prod-stop
whisky-prod-stop:
	$(PROD_COMPOSE) stop whisky-web

.PHONY: whisky-prod-restart
whisky-prod-restart:
	$(PROD_COMPOSE) restart whisky-web

.PHONY: whisky-prod-status
whisky-prod-status:
	$(PROD_COMPOSE) ps whisky-web

.PHONY: whisky-prod-logs
whisky-prod-logs:
	$(PROD_COMPOSE) logs -f whisky-web

.PHONY: pytest
pytest:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T web py.test --reuse-db

.PHONY: smoke-test
smoke-test:
	@./scripts/smoke_test.sh http://localhost:8003

.PHONY: test
test: pytest

.PHONY: pytest-lastfailed
pytest-lastfailed:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T web py.test --reuse-db --last-failed

.PHONY: pytest-clean
pytest-clean:
	if [ -f test_db.sqlite3 ]; then rm test_db.sqlite3; fi
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T web py.test

.PHONY: coverage
coverage:
	$(DEV_COMPOSE) up -d web
	$(DEV_COMPOSE) exec -T web py.test --reuse-db --cov --cov-report=html

.PHONY: lint
lint:
	EXIT_STATUS=0; \
	$(DEV_COMPOSE) up -d web || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web isort --diff -c $(SOURCE_DIRS) || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web flake8 $(SOURCE_DIRS) --exclude migrations,settings || EXIT_STATUS=$$?; \
	$(NODE_RUN) sh -lc "npm ci --no-audit --no-fund >/dev/null && npm run lint" || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web python manage.py makemigrations --dry-run --check --noinput || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-quick
lint-quick:
	EXIT_STATUS=0; \
	$(DEV_COMPOSE) up -d web || EXIT_STATUS=$$?; \
	npx lint-staged || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web python manage.py makemigrations --dry-run --check --noinput || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-js-fix
lint-js-fix:
	EXIT_STATUS=0; \
	$(NODE_RUN) sh -lc "npm ci --no-audit --no-fund >/dev/null && npm run lint-fix" || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

# Use with caution, the automatic fixing might produce bad results
.PHONY: lint-html-fix
lint-html-fix:
	EXIT_STATUS=0; \
	$(DEV_COMPOSE) up -d web || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web djlint $(ARGUMENTS) --reformat --profile=django --ignore=H030,H031,T002 || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-html
lint-html:
	EXIT_STATUS=0; \
	DOCKER_ARGS="$(patsubst $(CURDIR)/%,%,$(ARGUMENTS))"; \
	$(DEV_COMPOSE) up -d web || EXIT_STATUS=$$?; \
	$(DEV_COMPOSE) exec -T web djlint $${DOCKER_ARGS:-$(ARGUMENTS)} --profile=django --ignore=H030,H031,T002 || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-py
lint-py:
	EXIT_STATUS=0; \
	DOCKER_ARGS="$(patsubst $(CURDIR)/%,%,$(ARGUMENTS))"; \
	if ! docker image inspect wine-cellar:dev >/dev/null 2>&1; then $(DEV_COMPOSE) build web || EXIT_STATUS=$$?; fi; \
	docker run --rm -v "$$(pwd)":/app -w /app -e DOCKER_ARGS="$$DOCKER_ARGS" wine-cellar:dev sh -lc 'black --check $$DOCKER_ARGS' || EXIT_STATUS=$$?; \
	docker run --rm -v "$$(pwd)":/app -w /app -e DOCKER_ARGS="$$DOCKER_ARGS" wine-cellar:dev sh -lc 'isort $$DOCKER_ARGS --check-only' || EXIT_STATUS=$$?; \
	docker run --rm -v "$$(pwd)":/app -w /app -e DOCKER_ARGS="$$DOCKER_ARGS" wine-cellar:dev sh -lc 'flake8 $$DOCKER_ARGS --exclude migrations,settings' || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}
