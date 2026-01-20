# Wine Cellar

[![Coverage Status](https://coveralls.io/repos/github/the-broke-sommeliers/wine-cellar/badge.svg?branch=main)](https://coveralls.io/github/the-broke-sommeliers/wine-cellar?branch=main)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)

**Wine Cellar** is a self-hosted wine management app built with Django, designed for wine enthusiasts to track wines, store tasting notes, rate wines, and manage inventory. Whether you're a casual drinker or a connoisseur, this app helps organize your collection.

<img src="https://github.com/user-attachments/assets/f6230c75-e538-4128-83c3-bdaf54ef1107" height="150" alt="Screenshot of the landing page showing different statistics about your wines">
<img src="https://github.com/user-attachments/assets/f7c899dc-0540-432a-951c-2146136c67f9" height="150" alt="Screenshot of the wine list view showing all wines in the database">
<img src="https://github.com/user-attachments/assets/4edd4a02-fe52-405a-9552-1af6788d4e06" height="150" alt="Screenshot of the wine detail view showing a picture of a wine and it's attributes">
<img src="https://github.com/user-attachments/assets/ccc049d0-f534-4536-844b-73d7eace3dd0" height="150" alt="Screenshot of the wine map view showing markers on the world map">
<img src="https://github.com/user-attachments/assets/cfa0e3f1-3207-4256-b049-dbf220fc9b03" height="150" alt="Screenshot of the wine barcode scanner page">
<img src="https://github.com/user-attachments/assets/268c1bc8-8d15-4036-a9ed-00b41c977cc8" height="150" alt="Screenshot of the wine shelf list page">

## Features

- **Wine Tracking**: Record and review wines you've tasted.
- **Inventory Management**: Monitor bottle stock levels.
- **Multi-User Support**: Host for yourself and your friends.
- **Barcode Scanning**: Easy adding and removing known wines by scanning their
barcode.
- **Tasting Notes**: Save aroma, flavor, and experience details.
- **Wine Ratings**: Rate wines to track preferences.
- **Food Pairings**: Add recommended food pairings.
- **Self-hosted**: Full control over your data.
- **Drink By Reminder**: Email reminder to drink a bottle before it goes off.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/the-broke-sommeliers/wine-cellar.git
cd wine-cellar

# Install dependencies and set up database
make install

# Load sample data (optional)
make fixtures

# Start development server
make server
# Visit http://localhost:8003
```

For production deployment, see the [deployment guide](docs/deployment.md).

## Documentation

Find the full documentation in the [docs/](docs/) directory or online at [the-broke-sommeliers.github.io/wine-cellar](https://the-broke-sommeliers.github.io/wine-cellar/)

**Quick Links:**
- [Setup Guide](docs/setup.md) - Installation and getting started
- [Deployment Guide](docs/deployment.md) - Development and production deployment
- [Environment Variables](docs/environment.md) - Configuration reference
- [Architecture](docs/architecture.md) - System design and structure
- [Testing](docs/testing.md) - Running tests and coverage
- [Backup & Restore](docs/backup.md) - Data backup procedures

## Development

This project uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for all commit messages.

### Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies and set up database |
| `make server` | Start dev server on port 8003 |
| `make watch` | Dev server with frontend hot reload |
| `make pytest` | Run backend tests |
| `make lint` | Run all linters |
| `make fixtures` | Load sample data |

## FAQ

**Q: Can I run this on a Raspberry Pi?**
A: Yes! Wine Cellar runs well on Raspberry Pi 4 with 4GB+ RAM.

**Q: How do I enable user registration?**
A: Set `ENABLE_SIGNUP=True` in your environment file.

**Q: What database should I use?**
A: SQLite works for development. Use PostgreSQL for production.

**Q: Can I import wines from Vivino or other apps?**
A: Not directly, but you can use the barcode scanner to quickly add wines.

**Q: Is there a mobile app?**
A: No dedicated app, but the web interface is mobile-responsive with camera-based barcode scanning.

## Troubleshooting

### Server won't start
- Check if port 8003 is already in use: `lsof -i :8003`
- Ensure virtual environment is activated: `source venv/bin/activate`

### Database errors
- Run migrations: `python manage.py migrate`
- Check database connection in `.env.dev`

### Frontend not loading
- Rebuild assets: `npm run build`
- Clear browser cache

### Barcode scanner not working
- Camera requires HTTPS on mobile (use `./run_https.sh`)
- Check browser permissions for camera access

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

This project is licensed under the [AGPL-3.0 License](LICENSE).
