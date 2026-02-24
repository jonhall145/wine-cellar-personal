VIRTUAL_ENV ?= venv
PYTHON ?= python3.12
NODE_BIN = node_modules/.bin
SOURCE_DIRS = wine_cellar tests
ARGUMENTS=$(filter-out $(firstword $(MAKECMDGOALS)), $(MAKECMDGOALS))

.PHONY: all
all: help

.PHONY: help
help:
	@echo ""
	@echo "  Wine & Whisky Cellar"
	@echo "  ===================="
	@echo ""
	@echo "  Setup"
	@echo "    make install              Install deps, build frontend, run migrations"
	@echo "    make clean                Remove node_modules, venv, and lockfile"
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
	npm install --no-save
	npm run build
	if [ ! -f $(VIRTUAL_ENV)/bin/python3 ]; then $(PYTHON) -m venv $(VIRTUAL_ENV); fi
	$(VIRTUAL_ENV)/bin/python3 -m pip install --upgrade -r requirements.txt
	$(VIRTUAL_ENV)/bin/python3 manage.py migrate

.PHONY: clean
clean:
	if [ -f package-lock.json ]; then rm package-lock.json; fi
	if [ -d node_modules ]; then rm -rf node_modules; fi
	if [ -d venv ]; then rm -rf venv; fi

.PHONY: server
server:
	$(VIRTUAL_ENV)/bin/python3 manage.py runserver 8003

.PHONY: watch
watch:
	trap 'kill %1' KILL; \
	npm run watch & \
	$(VIRTUAL_ENV)/bin/python3 manage.py runserver 8003

.PHONY: fixtures
fixtures:
	$(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/user.json
	$(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/grapes.json
	$(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/appellations.json
	$(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/wines.json
	$(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/stock.json

.PHONY: deploy
deploy:
	docker compose -f docker-compose.prod.yml up -d --build --force-recreate

.PHONY: wine-deploy
wine-deploy:
	docker compose -f docker-compose.prod.yml build wine-web
	docker compose -f docker-compose.prod.yml up -d wine-web
	docker compose -f docker-compose.prod.yml restart nginx

.PHONY: wine-prod-start
wine-prod-start:
	docker compose -f docker-compose.prod.yml up -d wine-web

.PHONY: wine-prod-stop
wine-prod-stop:
	docker compose -f docker-compose.prod.yml stop wine-web

.PHONY: wine-prod-restart
wine-prod-restart:
	docker compose -f docker-compose.prod.yml restart wine-web

.PHONY: wine-prod-status
wine-prod-status:
	docker compose -f docker-compose.prod.yml ps wine-web

.PHONY: wine-prod-logs
wine-prod-logs:
	docker compose -f docker-compose.prod.yml logs -f wine-web

.PHONY: whisky-fixtures
whisky-fixtures:
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/whisky_regions.json
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/distilleries.json
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/python3 manage.py loaddata fixtures/bottlers.json

.PHONY: whisky-server
whisky-server:
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/python3 manage.py runserver 8004

.PHONY: whisky-watch
whisky-watch:
	trap 'kill %1' KILL; \
	npm run watch & \
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/python3 manage.py runserver 8004

.PHONY: whisky-pytest
whisky-pytest:
	CELLAR_APP_TYPE=whisky $(VIRTUAL_ENV)/bin/py.test tests/whisky/ --reuse-db

.PHONY: whisky-deploy
whisky-deploy:
	docker compose -f docker-compose.prod.yml build whisky-web
	docker compose -f docker-compose.prod.yml up -d whisky-web
	docker compose -f docker-compose.prod.yml restart nginx

.PHONY: whisky-prod-start
whisky-prod-start:
	docker compose -f docker-compose.prod.yml up -d whisky-web

.PHONY: whisky-prod-stop
whisky-prod-stop:
	docker compose -f docker-compose.prod.yml stop whisky-web

.PHONY: whisky-prod-restart
whisky-prod-restart:
	docker compose -f docker-compose.prod.yml restart whisky-web

.PHONY: whisky-prod-status
whisky-prod-status:
	docker compose -f docker-compose.prod.yml ps whisky-web

.PHONY: whisky-prod-logs
whisky-prod-logs:
	docker compose -f docker-compose.prod.yml logs -f whisky-web

.PHONY: pytest
pytest:
	$(VIRTUAL_ENV)/bin/py.test --reuse-db

.PHONY: smoke-test
smoke-test:
	@./scripts/smoke_test.sh http://localhost:8003

.PHONY: test
test: pytest

.PHONY: pytest-lastfailed
pytest-lastfailed:
	$(VIRTUAL_ENV)/bin/py.test --reuse-db --last-failed

.PHONY: pytest-clean
pytest-clean:
	if [ -f test_db.sqlite3 ]; then rm test_db.sqlite3; fi
	$(VIRTUAL_ENV)/bin/py.test

.PHONY: coverage
coverage:
	$(VIRTUAL_ENV)/bin/py.test --reuse-db --cov --cov-report=html

.PHONY: lint
lint:
	EXIT_STATUS=0; \
	$(VIRTUAL_ENV)/bin/isort --diff -c $(SOURCE_DIRS) ||  EXIT_STATUS=$$?; \
	$(VIRTUAL_ENV)/bin/flake8 $(SOURCE_DIRS) --exclude migrations,settings ||  EXIT_STATUS=$$?; \
	npm run lint ||  EXIT_STATUS=$$?; \
	$(VIRTUAL_ENV)/bin/python manage.py makemigrations --dry-run --check --noinput || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-quick
lint-quick:
	EXIT_STATUS=0; \
	npm run lint-staged ||  EXIT_STATUS=$$?; \
	$(VIRTUAL_ENV)/bin/python manage.py makemigrations --dry-run --check --noinput || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-js-fix
lint-js-fix:
	EXIT_STATUS=0; \
	npm run lint-fix || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

# Use with caution, the automatic fixing might produce bad results
.PHONY: lint-html-fix
lint-html-fix:
	EXIT_STATUS=0; \
	$(VIRTUAL_ENV)/bin/djlint $(ARGUMENTS) --reformat --profile=django --ignore=H030,H031,T002 || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-html
lint-html:
	EXIT_STATUS=0; \
	$(VIRTUAL_ENV)/bin/djlint $(ARGUMENTS) --profile=django --ignore=H030,H031,T002 || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}

.PHONY: lint-py
lint-py:
	EXIT_STATUS=0; \
	$(VIRTUAL_ENV)/bin/black $(ARGUMENTS) || EXIT_STATUS=$$?; \
	$(VIRTUAL_ENV)/bin/isort $(ARGUMENTS) --filter-files || EXIT_STATUS=$$?; \
	$(VIRTUAL_ENV)/bin/flake8 $(ARGUMENTS) || EXIT_STATUS=$$?; \
	exit $${EXIT_STATUS}
