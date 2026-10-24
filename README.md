# Wine & Whisky Cellar

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 6.0](https://img.shields.io/badge/django-6.0-green.svg)](https://www.djangoproject.com/)
[![React 19](https://img.shields.io/badge/react-19-61DAFB.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/docker-deployed-2496ED.svg)](https://www.docker.com/)

A self-hosted collection manager for wine and whisky enthusiasts. Track bottles, store tasting notes, manage inventory, and share your cellar with your household. Built with Django and React, deployable anywhere via Docker.

<img src="https://github.com/user-attachments/assets/f6230c75-e538-4128-83c3-bdaf54ef1107" height="150" alt="Screenshot of the landing page showing different statistics about your wines">
<img src="https://github.com/user-attachments/assets/f7c899dc-0540-432a-951c-2146136c67f9" height="150" alt="Screenshot of the wine list view showing all wines in the database">
<img src="https://github.com/user-attachments/assets/4edd4a02-fe52-405a-9552-1af6788d4e06" height="150" alt="Screenshot of the wine detail view showing a picture of a wine and it's attributes">
<img src="https://github.com/user-attachments/assets/ccc049d0-f534-4536-844b-73d7eace3dd0" height="150" alt="Screenshot of the wine map view showing markers on the world map">
<img src="https://github.com/user-attachments/assets/cfa0e3f1-3207-4256-b049-dbf220fc9b03" height="150" alt="Screenshot of the wine barcode scanner page">
<img src="https://github.com/user-attachments/assets/268c1bc8-8d15-4036-a9ed-00b41c977cc8" height="150" alt="Screenshot of the wine shelf list page">

## Features

### Collection Management
- **Wine Tracking** - Record wines with vintage, appellation, grape varieties, region, and country
- **Whisky Tracking** - Track whiskies with distillery, region, cask type, age, and peat level
- **Tasting Notes** - Save aroma, flavor, and experience details for each bottle
- **Ratings** - Rate bottles to track your preferences over time
- **Food Pairings** - Add recommended food pairings to wines

### Inventory & Storage
- **Bottle Inventory** - Monitor stock levels with purchase price and drink-by dates
- **Shelf Management** - Organise bottles by physical storage location with drag-and-drop
- **Bottle History** - Track when bottles are added, moved, opened, and finished
- **Barcode Scanning** - Quickly add or remove bottles by scanning their barcode via camera

### Smart Features
- **Vision AI** - Snap a photo of a wine label and let Claude extract the details automatically
- **Drink-By Reminders** - Email notifications before bottles pass their optimal drinking window
- **Map View** - Visualise your collection's origins on an interactive world map
- **Progressive Web App** - Install on your phone's home screen for a native app experience
- **Push Notifications** - Browser-based push notifications for reminders and updates

### Multi-User & Sharing
- **Households** - Share a cellar with family or friends under one household
- **Per-User Settings** - Each user configures their own currency, date format, and preferences
- **Configurable Signup** - Enable or disable public registration

### Self-Hosted
- **Your Data, Your Server** - Full control with no cloud dependency
- **Docker Deployment** - Single image serves both wine and whisky apps
- **Raspberry Pi Ready** - Runs on a Pi 4 with 4GB+ RAM
- **Automated Backups** - Scheduled database and media backups to Cloudflare R2

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 6.0, Python 3.12+ |
| Frontend | React 19, TypeScript, Webpack 5 |
| Database | PostgreSQL 16 (production), SQLite (development) |
| Cache | Redis 7 |
| Server | Gunicorn, Nginx |
| Infrastructure | Docker, Cloudflare Tunnel, Cloudflare R2 |
| Monitoring | Sentry |
| Auth | django-allauth with OIDC support |
| Maps | Leaflet with MapLibre GL |
| AI | Anthropic Claude API (vision label extraction) |

## Quick Start

### With Docker (recommended)

```bash
git clone https://github.com/jonhall145/wine-cellar-personal.git
cd wine-cellar-personal

# Build and start the dev stack (Django + PostgreSQL + Redis)
make install

# Load sample data (optional)
make fixtures          # Wine data
make whisky-fixtures   # Whisky data

# Start the wine dev server
make server
# Visit http://localhost:8003
```

### Without Docker

```bash
git clone https://github.com/jonhall145/wine-cellar-personal.git
cd wine-cellar-personal

# Create a virtual environment and install dependencies
make venv

# Run migrations
python manage.py migrate

# Start the dev server
python manage.py runserver 8003
```

The whisky app runs as a separate instance on port 8004:

```bash
make whisky-server
# Visit http://localhost:8004
```

## Architecture

The project uses a **dual-app architecture**: a single Django codebase serves both wine and whisky applications, switched via the `CELLAR_APP_TYPE` environment variable. In production, each app runs as its own Docker container behind an Nginx reverse proxy.

```
                    ┌──────────┐
                    │  Nginx   │
                    │ :80/:443 │
                    └────┬─────┘
                   ┌─────┴─────┐
            ┌──────┴──┐   ┌────┴─────┐
            │Wine App │   │Whisky App│
            │  :8000  │   │  :8004   │
            └────┬────┘   └────┬─────┘
                 │             │
          ┌──────┴─────────────┴──────┐
          │      PostgreSQL 16        │
          └───────────┬───────────────┘
                      │
               ┌──────┴──────┐
               │   Redis 7   │
               └─────────────┘
```

### Django Apps

| App | Purpose |
|-----|---------|
| `core` | Shared views, forms, filters, PWA manifest, push notifications |
| `wine` | Wine models, views, and templates |
| `whisky` | Whisky models, distilleries, regions, bottlers |
| `storage` | Shelves, inventory items, bottle tracking |
| `household` | Multi-user household management and permissions |
| `user` | User settings and preferences |
| `api` | REST API endpoints |
| `hardware` | Hardware integrations |

## Development

### Available Commands

Run `make help` for the full list. Key targets:

| Command | Description |
|---------|-------------|
| **Setup** | |
| `make install` | Build and start Docker dev stack |
| `make venv` | Create venv and install dev dependencies |
| `make fixtures` | Load wine sample data |
| `make whisky-fixtures` | Load whisky sample data |
| **Servers** | |
| `make server` | Wine dev server (port 8003) |
| `make whisky-server` | Whisky dev server (port 8004) |
| `make watch` | Wine dev server + frontend hot reload |
| **Testing** | |
| `make pytest` | Run all tests |
| `make whisky-pytest` | Run whisky tests only |
| `make coverage` | Tests with coverage report |
| `make smoke-test` | Smoke test against local server |
| **Linting** | |
| `make lint` | Run all linters (Black, isort, flake8, ESLint) |
| `make lint-quick` | Quick lint (staged JS + migrations) |
| **Deployment** | |
| `make ghcr-deploy` | Pull and deploy the GHCR `latest` image |
| `make ghcr-deploy-next` | Pull and deploy the GHCR `next` image |
| `make deploy` | Rebuild and redeploy full production stack |
| **Versioning** | |
| `make version` | Print current version |
| `make release PART=minor` | Bump version, tag, and update changelog |

### Code Style

- **Python**: Black, isort, flake8
- **JavaScript/TypeScript**: ESLint with neostandard
- **Templates**: djLint
- **CSS**: Stylelint with Sass
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/)

### Running Tests

```bash
# All tests
make pytest

# With coverage
make coverage

# Re-run only previously failed tests
make pytest-lastfailed

# Whisky tests only
make whisky-pytest
```

Tests use pytest with pytest-django. End-to-end tests use Playwright and auto-skip when browsers aren't installed.

## Deployment

Production deployment uses Docker with images published to GitHub Container Registry.

```bash
# Pull latest release image and redeploy all containers
make ghcr-deploy

# Pull the next-branch image and redeploy all containers
make ghcr-deploy-next
```

The production stack includes:
- **Gunicorn** with 2 workers per app
- **Nginx** as reverse proxy with SSL termination
- **PostgreSQL 16** shared database
- **Redis 7** with AOF persistence
- **Cloudflare Tunnel** for external access and SSL

For full deployment instructions, see the [Deployment Guide](docs/deployment.md).

## Documentation

Full documentation lives in [docs/](docs/).

| Guide | Description |
|-------|-------------|
| [Setup](docs/setup.md) | Installation and getting started |
| [Deployment](docs/deployment.md) | Development and production deployment |
| [Docker](docs/docker.md) | Docker configuration and usage |
| [Environment Variables](docs/environment.md) | Configuration reference |
| [Architecture](docs/architecture.md) | System design and structure |
| [Models](docs/models.md) | Database schema documentation |
| [API Reference](docs/api.md) | REST API endpoints |
| [Storage](docs/storage.md) | Shelf and inventory system |
| [Vision AI](docs/vision-wine-entry.md) | AI-powered label extraction |
| [Testing](docs/testing.md) | Running tests and coverage |
| [Upgrading](docs/upgrading.md) | Version upgrade procedures |
| [Backup & Restore](docs/backup.md) | Data backup procedures |

## FAQ

**Q: Can I run this on a Raspberry Pi?**
A: Yes. It runs well on a Raspberry Pi 4 with 4GB+ RAM using Docker.

**Q: How do I switch between wine and whisky modes?**
A: Set `CELLAR_APP_TYPE=wine` or `CELLAR_APP_TYPE=whisky` in your environment. In production, each runs as a separate container from the same image.

**Q: How do I enable user registration?**
A: Set `ENABLE_SIGNUP=True` in your environment file.

**Q: What database should I use?**
A: SQLite works for development. Use PostgreSQL for production.

**Q: Can I import wines from Vivino or other apps?**
A: Not directly, but you can use the barcode scanner or the Vision AI feature (snap a label photo) to quickly add wines.

**Q: Is there a mobile app?**
A: No dedicated app, but the web interface is a Progressive Web App -- install it to your home screen for a native feel, with camera-based barcode scanning.

**Q: How does the Vision AI feature work?**
A: Take a photo of a wine label and the app sends it to the Anthropic Claude API to extract wine details (name, vintage, region, grape varieties, etc.) automatically. Requires an `ANTHROPIC_API_KEY` in your environment.

## Troubleshooting

### Server won't start
- Check if the port is in use: `lsof -i :8003` (wine) or `lsof -i :8004` (whisky)
- Ensure Docker containers are running: `docker compose ps`

### Database errors
- Run migrations: `python manage.py migrate`
- Check database connection in your environment file

### Frontend not loading
- Rebuild assets: `npm run build`
- Clear browser cache or use incognito mode

### Barcode scanner not working
- Camera requires HTTPS on mobile devices (use `./run_https.sh`)
- Check browser permissions for camera access

### Docker issues
- Rebuild images: `docker compose build --no-cache`
- Check container logs: `make wine-prod-logs` or `make whisky-prod-logs`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

This project is licensed under the [AGPL-3.0 License](LICENSE).

