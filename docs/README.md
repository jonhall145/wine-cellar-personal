# Wine Cellar Documentation

Welcome to the Wine Cellar documentation. This guide will help you install, configure, and use Wine Cellar for managing your wine collection.

## Quick Links

- **[Setup Guide](setup.md)** - Installation and getting started
- **[Deployment](deployment.md)** - Production deployment options
- **[Environment Variables](environment.md)** - Configuration reference
- **[Architecture](architecture.md)** - System design and structure
- **[API Reference](api.md)** - API endpoints and usage
- **[Testing](testing.md)** - Running tests and coverage
- **[Backup & Restore](backup.md)** - Data backup procedures

## About Wine Cellar

Wine Cellar is a self-hosted wine management application built with Django and React. It helps wine enthusiasts track their collection, manage inventory, and discover new wines.

### Key Features

- Wine tracking with tasting notes and ratings
- Inventory management with storage locations
- Barcode scanning for quick wine lookup
- Interactive map of wine origins
- Multi-user support
- Email reminders for drink-by dates
- Mobile-responsive interface with camera access

### Technology Stack

- **Backend:** Django 5.2, Python 3.11+, PostgreSQL/SQLite
- **Frontend:** React 19, TypeScript, Webpack
- **Testing:** pytest, factory-boy, coverage
- **Deployment:** Gunicorn, Whitenoise, optional Caddy/Nginx

## Getting Started

1. Follow the [Setup Guide](setup.md) to install dependencies
2. Configure your [Environment Variables](environment.md)
3. Read the [Deployment Guide](deployment.md) for production setup
4. Explore the [Architecture](architecture.md) to understand the codebase

## Contributing

For information on contributing to Wine Cellar, see [CONTRIBUTING.md](../CONTRIBUTING.md) in the project root.

## License

This project is licensed under the [AGPL-3.0 License](../LICENSE).
