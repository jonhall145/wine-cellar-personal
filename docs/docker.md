# Docker Guide

Quick reference for developing and running Wine Cellar with Docker.

## Key Concepts

**Image** — a built snapshot of the app (code + dependencies). Built from the `Dockerfile`.
**Container** — a running instance of an image. Like a lightweight VM.
**Volume** — persistent storage that survives container restarts. Where your database and media live.
**Compose** — tool that runs multiple containers together (web, db, redis, etc.) from a YAML file.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | How to build the app image (installs Python, Node, system libs) |
| `docker-compose.yml` | Dev setup (mounts source code for hot-reload) |
| `docker-compose.prod.yml` | Prod setup (nginx, gunicorn, SSL, all ports) |
| `docker-entrypoint.sh` | Runs on container start (migrations, collectstatic, superuser) |
| `.env.docker` | Dev environment variables |
| `.env.docker.prod` | Prod environment variables (not in git) |
| `nginx/default.conf` | Nginx config for serving static files + SSL termination |

## Daily Commands

### Start / stop

```bash
# Start production (what's running now)
docker compose -f docker-compose.prod.yml up -d

# Stop (keeps data)
docker compose -f docker-compose.prod.yml down

# Stop AND DELETE ALL DATA (volumes) — be very careful
docker compose -f docker-compose.prod.yml down -v    # ← DESTROYS DATABASE + MEDIA
```

### Check status

```bash
# Container status + health
docker compose -f docker-compose.prod.yml ps

# Logs (all services)
docker compose -f docker-compose.prod.yml logs --tail=50

# Logs (one service, live follow)
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f celery-worker
```

### Restart after code changes

```bash
# Rebuild image and restart (after changing Python code, templates, etc.)
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d

# Just restart without rebuilding (e.g. after changing .env)
docker compose -f docker-compose.prod.yml restart web
```

### Run commands inside a container

```bash
# Django shell
docker compose -f docker-compose.prod.yml exec web python manage.py shell

# Run migrations manually
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create a superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Open a bash shell inside the web container
docker compose -f docker-compose.prod.yml exec web bash
```

### Database

```bash
# PostgreSQL shell
docker compose -f docker-compose.prod.yml exec db psql -U wine_cellar_user -d wine_cellar_prod

# Backup (to R2 — runs automatically at 3am via cron)
./backup_to_r2.sh docker

# Local backup
./pg_backup.sh

# Restore from backup
gunzip -c backups/wine_cellar_prod_XXXXXX.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U wine_cellar_user -d wine_cellar_prod
```

## Architecture (Production)

```
Internet → Cloudflare Tunnel → :8000 ─┐
LAN ──────────────────────────→ :80  ──┤→ nginx → gunicorn (Django)
Meshnet (HTTPS) ──────────────→ :443 ──┘     ↕
                                          PostgreSQL
                                          Redis
                                          Celery worker + beat
```

All services run as Docker containers. Nginx handles SSL and serves static/media files directly.

## Common Scenarios

### "I changed Python code / templates"

```bash
docker compose -f docker-compose.prod.yml build web && \
docker compose -f docker-compose.prod.yml up -d
```

### "I changed frontend code (JS/CSS/React)"

Same as above — the Dockerfile builds frontend assets during image build.

### "I changed nginx config"

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

### "I changed .env.docker.prod"

```bash
docker compose -f docker-compose.prod.yml up -d   # recreates containers with new env
```

### "I added a new Python package"

Add it to `requirements/`, then rebuild:

```bash
docker compose -f docker-compose.prod.yml build web && \
docker compose -f docker-compose.prod.yml up -d
```

### "Something is broken, I need to see what's happening"

```bash
# Check all container health
docker compose -f docker-compose.prod.yml ps

# Check recent logs for errors
docker compose -f docker-compose.prod.yml logs --tail=100 web

# Health endpoint
curl http://localhost:8000/health/

# Get inside the container and poke around
docker compose -f docker-compose.prod.yml exec web bash
```

### "Disk is full"

```bash
# See what Docker is using
docker system df

# Remove unused images, stopped containers, build cache
docker system prune

# Remove unused images too (more aggressive)
docker system prune -a
```

## Things to Remember

1. **`down` vs `down -v`** — `down` stops containers. `down -v` stops containers AND deletes volumes (your database, media, redis data). Never use `-v` unless you mean it.

2. **Data lives in volumes** — the database, media uploads, and redis data persist in Docker volumes. They survive `down` and `up` cycles. Check them with `docker volume ls`.

3. **Rebuilding is needed for code changes** — unlike dev mode, production doesn't mount your source code. You need to `build` a new image after code changes.

4. **Entrypoint runs setup automatically** — migrations, collectstatic, and superuser creation all happen on container start. You don't need to run them manually.

5. **Backups run at 3am** — the cron job (`backup_to_r2.sh`) auto-detects Docker and backs up PostgreSQL + media to Cloudflare R2.
