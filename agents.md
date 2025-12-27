# Wine Cellar - Project Summary

## Overview

**Wine Cellar** is a self-hosted wine management application built with Django, designed for wine enthusiasts to track wines, store tasting notes, rate wines, and manage inventory. The project provides a comprehensive solution for both casual drinkers and connoisseurs to organize their wine collections.

**Version:** 0.3.0-rc.0  
**License:** AGPL-3.0  
**Repository:** https://github.com/the-broke-sommeliers/wine-cellar

## Key Features

- **Wine Tracking**: Record and review wines you've tasted
- **Inventory Management**: Monitor bottle stock levels with pricing support
- **Multi-User Support**: Host for yourself and your friends
- **Barcode Scanning**: Easy adding and removing of known wines by scanning barcodes
- **Tasting Notes**: Save detailed aroma, flavor, and experience notes
- **Wine Ratings**: Rate wines to track preferences
- **Food Pairings**: Add recommended food pairing suggestions
- **Map Visualization**: Interactive map showing wine origins
- **Image Management**: Upload multiple images (front, back, label front/back)
- **Drink By Reminder**: Email notifications to drink bottles before they expire
- **Sorting & Filtering**: Sort wines by average price, vintage, rating, etc.
- **Self-hosted**: Full control over your data with Docker deployment support

## Technology Stack

### Backend
- **Framework**: Django 5.2.9
- **Language**: Python 3.8+
- **Database**: PostgreSQL 16 (production), SQLite (development)
- **Task Queue**: Celery 5.6.0 with django-celery-beat
- **Authentication**: django-allauth 65.13.1 with OpenID Connect support
- **Image Processing**: Pillow 12.0.0
- **API/Utilities**: requests, pycountry, django-filter, django-widget-tweaks

### Frontend
- **JavaScript Framework**: React 19.2.3
- **Mapping**: Leaflet 1.9.4, react-leaflet 5.0.0, MapLibre GL
- **Barcode Scanning**: barcode-detector 3.0.8, react-barcode-scanner 4.0.0
- **UI Components**: Tom Select 2.4.3, FontAwesome 7.1.0
- **Build Tools**: Webpack 5, Babel 7.28.5
- **CSS**: Custom CSS (no preprocessor framework)

### Development Tools
- **Testing**: pytest 9.0.2, pytest-django, pytest-cov, factory-boy
- **Linting**: 
  - Python: flake8, black, isort
  - JavaScript: ESLint 9.39.2, Prettier 3.7.4
  - Templates: djlint
- **Code Quality**: Coverage tracking, lint-staged with husky
- **Documentation**: MkDocs with Material theme
- **Version Control**: Commitizen for conventional commits

### Deployment
- **Containerization**: Docker with docker-compose
- **Static Files**: Whitenoise with Brotli compression
- **Reverse Proxy**: Caddy (configured in production)

## Project Structure

```
wine-cellar-personal/
├── wine_cellar/                 # Main Django application
│   ├── apps/                    # Django apps
│   │   ├── wine/               # Wine tracking and management
│   │   ├── storage/            # Storage and inventory management
│   │   └── user/               # User management and settings
│   ├── assets/                 # Frontend assets (CSS, JS, images)
│   ├── react/                  # React components
│   │   ├── react_bar_code.tsx  # Barcode scanner component
│   │   └── maps/               # Map visualization component
│   ├── templates/              # Django templates
│   └── conf/                   # Django settings and configuration
├── tests/                      # Test suite (16 test files)
├── fixtures/                   # Sample data (grapes, wines, stock, users)
├── docs/                       # MkDocs documentation
├── requirements/               # Python dependencies (base, dev, prod)
├── docker-compose.yml          # Development Docker setup
├── docker-compose.prod.yml     # Production Docker setup
├── Makefile                    # Development commands
└── package.json                # Node.js dependencies
```

## Core Django Apps

### 1. Wine App (`wine_cellar/apps/wine/`)
Handles all wine-related functionality:
- **Models**: Wine, WineImage, WineType, Category
- **Views**: Wine list (filterable), detail, create, edit, delete
- **Features**: 
  - Multi-image upload support
  - Barcode integration
  - Country/region tracking
  - Vintage management
  - Rating system
  - Food pairing recommendations
  - Drink-by date tracking
- **Files**: ~1918 lines across models, views, forms, filters, fields, tasks, signals

### 2. Storage App (`wine_cellar/apps/storage/`)
Manages wine inventory and storage locations:
- **Models**: StorageItem, Shelf
- **Features**:
  - Stock level tracking
  - Bottle pricing
  - Location/shelf organization
  - Barcode-based stock management
  - Deletion tracking (soft delete)

### 3. User App (`wine_cellar/apps/user/`)
User management and preferences:
- **Models**: UserSettings
- **Features**:
  - Multi-user support
  - User preferences (currency, date format)
  - django-allauth integration
  - OpenID Connect authentication
  - Configurable signup (disabled by default)

## Key Workflows

### Development Workflow
1. **Setup**: `make install` - Installs npm packages, Python deps, runs migrations
2. **Run Server**: `make server` - Starts Django dev server on port 8003
3. **Watch Mode**: `make watch` - Auto-rebuilds frontend and runs server
4. **Testing**: `make pytest` - Runs backend tests
5. **Linting**: `make lint` - Runs Python and JavaScript linters
6. **Load Data**: `make fixtures` - Loads sample wines, grapes, stock

### Deployment Workflow
1. **Development**: `docker compose up` with `.env.dev`
2. **Production**: `docker compose -f docker-compose.prod.yml up` with `.env.prod`
3. **Email Setup**: Configure SMTP settings in `.env.prod` for notifications

## Database Schema Highlights

- **Wine Table**: Core wine information (name, vintage, country, type, rating, ABV)
- **WineImage Table**: Multiple images per wine with type classification
- **StorageItem Table**: Inventory tracking with pricing and location
- **UserSettings Table**: Per-user preferences
- **Relationships**: 
  - Wine → User (ForeignKey)
  - WineImage → Wine (ForeignKey)
  - StorageItem → Wine (ForeignKey)
  - StorageItem → User (ForeignKey)

## API Endpoints

The application primarily uses Django's template-based views, with some AJAX endpoints:
- Wine CRUD operations
- Barcode lookup/search
- Storage management
- User settings
- Map data (JSON response for wine locations)

## Testing

- **Test Framework**: pytest with pytest-django
- **Test Coverage**: Tracked with pytest-cov and Coveralls
- **Test Types**: 
  - Model tests (wine model, fields)
  - View tests (wine, storage, user views)
  - Integration tests (drink-by functionality)
- **Factory Pattern**: Uses factory-boy for test data generation
- **Coverage Badge**: Displayed on GitHub README

## Localization

- **i18n Support**: Django internationalization framework
- **Languages**: English (default), with German locale files present
- **Translation Files**: `.po` files in `locale/` directory
- **Commands**: `make po` (extract), `make mo` (compile)

## Build System

### Frontend Build
- **Webpack Configuration**: Separate dev and prod configs
- **Loaders**: Babel (JS/JSX/TS/TSX), CSS, SASS, PostCSS
- **Plugins**: MiniCssExtractPlugin, CopyWebpackPlugin
- **Output**: Bundles to `build/` directory

### Backend Build
- **Python Package**: setuptools-based build system
- **Version Management**: Commitizen with semver2
- **Changelog**: Automated with Commitizen (CHANGELOG.md)

## Version Control & CI/CD

- **Commit Convention**: Conventional Commits (enforced via husky)
- **Pre-commit Hooks**: lint-staged runs linters on staged files
- **Versioning**: Semantic versioning with commitizen
- **Changelog**: Auto-generated from conventional commits
- **Renovate**: Automated dependency updates configured

## Configuration

### Environment Variables
Key settings in `.env` files:
- **Database**: PostgreSQL connection strings
- **Django**: SECRET_KEY, DEBUG, ALLOWED_HOSTS
- **Email**: SMTP configuration for notifications
- **Storage**: MEDIA_ROOT, STATIC_ROOT
- **Auth**: ENABLE_SIGNUP flag, OAuth settings

### Feature Flags
- `ENABLE_SIGNUP`: Controls whether new user registration is allowed (default: False)

## Documentation

Comprehensive documentation available in `docs/` directory:
- **setup.md**: Installation and getting started
- **deployment.md**: Docker deployment guide (dev & prod)
- **testing.md**: How to run tests
- **wine.md**: Wine management features
- **storage.md**: Inventory management
- **README.md**: General overview

Documentation site built with MkDocs Material theme.

## Notable Design Patterns

1. **Class-Based Views**: Extensive use of Django's generic views (DetailView, FormView, DeleteView, FilterView)
2. **Abstract Base Models**: UserContentModel for common fields (user, created, modified)
3. **Multi-step Forms**: Wine creation uses form steps
4. **Signals**: Post-save hooks for storage and wine updates
5. **Celery Tasks**: Asynchronous email sending for drink-by reminders
6. **React Integration**: Selective use of React for complex UI (barcode scanner, maps)
7. **Custom Model Fields**: DecimalField subclass for percentage validation

## Security Considerations

- **Authentication Required**: Most views require login (@login_required)
- **User Data Isolation**: Queries filtered by request.user
- **CSRF Protection**: Django's built-in CSRF middleware
- **SQL Injection**: Django ORM prevents SQL injection
- **Static Files**: Whitenoise for secure static file serving
- **Environment Variables**: Secrets stored in .env files (gitignored)

## Performance Optimizations

- **Database Indexing**: Implicit on ForeignKey fields
- **Query Optimization**: Use of select_related, prefetch_related
- **Static File Compression**: Whitenoise with Brotli
- **Frontend Bundling**: Webpack minification in production
- **Caching**: Django's caching framework (configuration needed)

## Known Limitations

1. Single FIXME comment in `wine_cellar/apps/wine/views.py`: "hacky workaround to increase form_step field"
2. Production setup noted as "under development" in deployment docs
3. Email backend requires manual SMTP configuration
4. No automated backup system documented
5. Limited API documentation (primarily template-based)

## Project Maintenance

- **Active Development**: Recent commits show ongoing maintenance
- **Dependency Updates**: Automated via Renovate
- **Test Coverage**: Tracked via Coveralls
- **Code Quality**: Multiple linters enforced
- **Documentation**: Maintained in docs/ directory

## Community & Support

- **Source Code**: GitHub repository
- **Issue Tracking**: GitHub Issues
- **Discussions**: GitHub Discussions
- **License**: AGPL-3.0 (requires source disclosure for derivative works)

## Recent Changes (v0.3.0-rc.0)

- Added sorting by average price
- Total value statistic on homepage
- Bottle price tracking in stock items
- Multiple image upload support
- django-allauth authentication integration
- Email and password change views
- OpenID Connect support
- Configurable signup flag

---

*This summary was generated on 2025-12-27 and reflects the state of the project at version 0.3.0-rc.0.*
