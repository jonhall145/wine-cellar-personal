# Deploy to Production

This document describes the process for deploying code changes to production.

## Overview

When you make changes to source files, the following steps are required to push them through to production:

1. **Run tests** - Ensure no regressions
2. **Run linting** - Code quality checks
3. **Build frontend assets** - Compile JS/CSS for production
4. **Collect static files** - Gather and compress for serving
5. **Restart production server** - Apply changes

## Quick Deploy

Use the automated deployment script:

```bash
./deploy-to-prod.sh
```

This script runs all steps in the correct order with proper error handling.

### Script Options

```bash
./deploy-to-prod.sh              # Full deployment (tests, lint, build, restart)
./deploy-to-prod.sh --skip-tests # Skip tests (for hotfixes)
./deploy-to-prod.sh --build-only # Only build assets, don't restart server
```

## Manual Steps

### 1. Run Tests

```bash
make pytest
```

Ensure all tests pass before deploying.

### 2. Run Linting

```bash
make lint
```

Fix any linting errors before proceeding.

### 3. Build Frontend Assets

```bash
npm run build:prod
```

This compiles TypeScript, JavaScript, and CSS into optimized production bundles.

**Note:** This step can take several minutes.

### 4. Collect Static Files

```bash
./collect_static.sh --force
```

This gathers all static files (CSS, JS, images) into the `staticfiles/` directory and creates compressed versions for efficient serving.

**Note:** This step can take several minutes.

### 5. Restart Production Server

```bash
./run_prod_https.sh restart
```

This applies database migrations and restarts Gunicorn with the new code.

## File Types and Their Build Requirements

| Change Type | Build Required | Static Collection | Server Restart |
|-------------|----------------|-------------------|----------------|
| Python code (.py) | No | No | Yes |
| Django templates (.html) | No | No | Yes |
| JavaScript/TypeScript | Yes | Yes | Yes |
| CSS/SCSS | Yes | Yes | Yes |
| Static images | No | Yes | Yes |
| Database migrations | No | No | Yes |

## Troubleshooting

### Build fails with memory errors

The webpack production build can be memory-intensive. If it fails:

```bash
# Increase Node.js memory limit
NODE_OPTIONS="--max-old-space-size=4096" npm run build:prod
```

### Static files not updating

Force a rebuild:

```bash
rm -rf staticfiles/
./collect_static.sh --force
```

### Server won't restart

Check for existing processes:

```bash
./run_prod_https.sh status
./run_prod_https.sh stop
./run_prod_https.sh start
```

Check logs:

```bash
./run_prod_https.sh logs
```
