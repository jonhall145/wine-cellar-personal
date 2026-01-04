# Local Development Setup

The application runs directly from source code.

## Setup Summary

### 1. Environment
- **Python**: 3.11+
- **Virtual Environment**: `venv/`
- **Database**: SQLite (db.sqlite3)
- **Dependencies**: All Python packages installed from requirements.txt

### 2. Configuration
- **Environment File**: `.env.dev`
- **Django Settings**: `wine_cellar.conf.settings`
- **Static Files**: Collected to `static/`

### 3. Admin Access
- **Username**: admin
- **Email**: admin@example.org
- **Password**: change_me
- **URL**: http://127.0.0.1:8000/admin/

## Running the Application

### Quick Start
```bash
./run_local.sh
```

This script will:
1. Activate the virtual environment
2. Load environment variables from `.env.dev`
3. Run database migrations
4. Ensure superuser exists
5. Collect static files
6. Start the development server on http://0.0.0.0:8000

### Manual Start
```bash
# Activate virtual environment
source venv/bin/activate

# Load environment variables
export $(cat .env.dev | grep -v '^#' | xargs)

# Run migrations (if needed)
python manage.py migrate

# Start development server
python manage.py runserver 0.0.0.0:8000
```

## Development Commands

### Run Migrations
```bash
source venv/bin/activate
python manage.py migrate
```

### Create Superuser
```bash
source venv/bin/activate
python manage.py createsuperuser
```

### Collect Static Files
```bash
source venv/bin/activate
python manage.py collectstatic
```

### Run Tests
```bash
source venv/bin/activate
pytest
```

### Django Shell
```bash
source venv/bin/activate
python manage.py shell
```

## Using Make Commands

```bash
make install    # Install all dependencies
make server     # Start dev server
make watch      # Dev server with frontend rebuild
make pytest     # Run tests
make lint       # Run linters
make fixtures   # Load sample data
```

## Notes

### Features Not Available in Local Mode
- **Celery**: Background task processing (requires Redis and Celery worker)
- **Redis**: Caching (uses in-memory cache by default)

## Files

### Key Files
- `venv/` - Python virtual environment
- `run_local.sh` - Development startup script
- `run_prod_local.sh` - Production startup script
- `db.sqlite3` - SQLite database
- `static/` - Collected static files
- `.env.dev` - Development environment variables
