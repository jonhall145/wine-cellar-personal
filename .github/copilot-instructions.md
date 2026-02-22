# Copilot Instructions

## Build, test, lint
- `make install` (npm install/build, create venv, pip install, migrate)
- `make server` (dev server on :8003) / `make watch` (dev server + webpack watch)
- `make whisky-server` / `make whisky-watch` (whisky mode on :8004)
- `./run_https.sh` (HTTPS dev server for mobile camera testing)
- `npm run build` / `npm run build:prod` (webpack bundles)
- `make lint` (isort/flake8/eslint + migration check), `make lint-quick`
- `make pytest` (pytest --reuse-db), `make pytest-lastfailed`
- Single test: `venv/bin/py.test tests/path/to_test.py::test_name --reuse-db`
- Whisky tests: `CELLAR_APP_TYPE=whisky venv/bin/py.test tests/whisky/path/to_test.py::test_name --reuse-db` or `make whisky-pytest`

## High-level architecture
- Hybrid UI: Django templates render pages, with React components (barcode scanner, maps, storage grid) mounted in templates and bundled via Webpack from `wine_cellar/react` and `wine_cellar/assets`.
- Django app layer with class-based views and django-allauth; core apps live in `wine_cellar/apps` (wine, storage, user, plus hardware/household/whisky modules).
- Data layer uses Django ORM; SQLite in development and PostgreSQL in production.
- Background jobs run through Celery + Redis (drink-by reminders).

## Key conventions
- `CELLAR_APP_TYPE` switches wine vs whisky mode; URL routing includes only one app at runtime, and whisky tests require `CELLAR_APP_TYPE=whisky` set before Django loads.
- UI is mobile-first; verify UI/CSS changes on a mobile viewport and use HTTPS for camera-based scanning.
- JS/TS UI strings should use `django.gettext(...)` / `gettext(...)` for i18n (see `types/django.d.ts`).
- Barcode scanner templates pass kebab-case `data-*` attributes (e.g., `data-scan-url`); React reads them with `dataset['scan-url']`/`dataset['label-scan-url']` instead of underscores.
- Frontend CSS/JS changes require a webpack rebuild (`make watch` or `npm run build`) before templates reflect updates.
