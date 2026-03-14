# Docker Consolidation Analysis

**Date:** 2026-02-23
**Context:** Review of the current Docker setup to evaluate whether wine-web and whisky-web should be consolidated, whether Celery is justified, and general containerisation improvements.

---

## 1. Current Architecture

### Container Inventory (7 containers)

| Container | Image | RAM (est.) | Purpose |
|-----------|-------|------------|---------|
| `wine-web` | `wine-cellar:prod` | ~150MB | Gunicorn (2 workers) serving wine app |
| `whisky-web` | `wine-cellar:prod` | ~150MB | Gunicorn (2 workers) serving whisky app |
| `nginx` | `nginx:alpine` | ~10MB | Reverse proxy, SSL, static files |
| `db` | `postgres:16-alpine` | ~100MB | PostgreSQL (shared by both apps) |
| `redis` | `redis:7-alpine` | ~30MB | Cache + Celery broker |
| `celery-worker` | `wine-cellar:prod` | ~100MB | Task execution (concurrency=2) |
| `celery-beat` | `wine-cellar:prod` | ~60MB | Task scheduling (DatabaseScheduler) |
| **Total** | | **~600MB** | **On an 8GB RPi4** |

### What's Actually Shared vs Duplicated

| Component | Shared? | Notes |
|-----------|---------|-------|
| Docker image | **Yes** | Both use `wine-cellar:prod` |
| Codebase | **Yes** | `CELLAR_APP_TYPE` env var switches behavior |
| PostgreSQL | **Yes** | Single `db` container |
| Redis | **Yes** | Single instance |
| Static files | **Yes** | Shared `static_data` volume |
| Media files | **No** | Separate volumes: `media_data` vs `whisky_media_data` |
| Env files | **No** | `.env.docker.prod` vs `.env.whisky.docker.prod` |
| Celery worker | **Wine only** | Uses wine env file; whisky has zero tasks |
| Celery beat | **Wine only** | Schedules wine-only reminder task |
| Backups | **Wine only** | `backup_to_r2.sh` only backs up wine-web media |
| Migrations | **Duplicated** | Both containers run `python manage.py migrate` on startup |
| collectstatic | **Duplicated** | Both containers run `collectstatic` on startup |
| Fixture loading | **Duplicated** | Each loads its own fixtures on startup |

### Key Insight

The **only real differences** between wine-web and whisky-web are:
1. `CELLAR_APP_TYPE` environment variable (`wine` vs `whisky`)
2. Media volume mount (`media_data` vs `whisky_media_data`)
3. Domain/CSRF/allowed-hosts settings
4. Which fixtures get loaded on startup

Both containers run the exact same Docker image, connect to the same database, and share static files. They always start and stop together on the same Pi.

---

## 2. Web Container Consolidation: wine-web + whisky-web

### Option A: Keep Separate Containers (current)

**Pros:**
- Clean mental model: one container = one app
- Isolation: a crash/memory leak in one doesn't directly kill the other
- Independent restarts (e.g., restart wine without touching whisky)
- Each app gets its own gunicorn worker pool
- Simpler Django configuration — one `CELLAR_APP_TYPE` per process

**Cons:**
- ~150MB additional RAM for the duplicate gunicorn process
- Double startup work: both run migrations, collectstatic, fixture loading
- Two env files to maintain with mostly-identical content
- nginx config must define two separate upstreams
- Deploy script rebuilds the image once but restarts containers individually
- Backup blind spot: whisky media is not backed up at all
- Celery only runs under wine env — if whisky ever needs background tasks, it's a gap

### Option B: Consolidate into One Web Container

**Pros:**
- Save ~150MB RAM (significant on RPi4, though manageable on 8GB)
- Migrations, collectstatic, and fixture loading run once
- One env file to maintain
- Simpler compose file and nginx config
- Media backup is easier — one volume to back up (or two mounted in one container)

**Cons:**
- Routing complexity: need to route wine vs whisky requests to the right Django code within a single process
- Shared failure domain: one app crashing takes down both
- Both apps always loaded in memory even if only one receives traffic
- More complex Django configuration (middleware to detect app type from Host header or URL prefix)
- If one app is slow/hanging, it affects the other's worker availability

### How Consolidation Would Work Technically

Two main approaches:

**Approach 1: Host-header middleware**
Django middleware reads the `Host` header and sets `CELLAR_APP_TYPE` per-request. Requires refactoring all code that reads the setting at import-time (which currently happens via `os.environ.get` in `settings.py`). This is a significant change — the app type currently influences `INSTALLED_APPS`, URL routing, and template loading at startup, not per-request.

**Approach 2: URL prefix routing**
Mount wine at `/wine/` and whisky at `/whisky/`. Simpler technically but changes all URLs, breaks existing bookmarks, and feels unnatural for a single-purpose app.

**Approach 3: nginx path routing to shared process**
Keep both domain names via Cloudflare Tunnel but route to a single gunicorn. The challenge remains the same — Django needs to know which app to serve per-request, which conflicts with the current startup-time configuration model.

### Recommendation: Keep Separate (for now)

The 150MB saving is worthwhile but not critical on 8GB. The routing refactoring is non-trivial because `CELLAR_APP_TYPE` is deeply embedded as a startup-time setting (it controls `INSTALLED_APPS`, URL includes, template loading). Making it per-request would require significant architectural changes.

**Instead, focus on the higher-value, lower-effort wins below.**

---

## 3. Celery Review: 2 Containers for 1 Daily Task

### Current State

The **entire Celery infrastructure** exists for a single task:

```python
# wine_cellar/apps/wine/tasks.py
@shared_task(name="drink_by_reminder")
def drink_by_reminder():
    """Send reminders for wines in their final drinking year."""
```

This task:
- Runs once per day
- Only applies to wine (whisky has no celery tasks)
- Sends email reminders for wines in their final drinking year
- Is scheduled via `django-celery-beat` with a `DatabaseScheduler`

### What This Costs

| Component | RAM | Always running? |
|-----------|-----|-----------------|
| `celery-worker` (concurrency=2) | ~100MB | Yes, 24/7 |
| `celery-beat` | ~60MB | Yes, 24/7 |
| Redis (partial — also used for cache) | ~15MB | Yes, but needed anyway |
| `django-celery-beat` migrations/admin | complexity | N/A |
| **Total overhead** | **~160MB** | **For ~1 second of work per day** |

That's 2% of your 8GB RPi4's RAM running 24/7 for a task that executes for about 1 second once daily.

### Is Celery Beat Required?

**No.** Celery Beat's value is:
- Dynamic schedule management via Django admin (not being used — schedule is hardcoded)
- Sub-minute scheduling precision (not needed — daily task)
- Distributed task execution (not needed — single Pi)
- Task retry/failure handling (a simple email retry is trivial without it)

None of these justify the infrastructure cost here.

### Alternative: Management Command + Cron

Convert the task to a Django management command and schedule via the host's crontab:

```python
# wine_cellar/apps/wine/management/commands/send_drink_reminders.py
from django.core.management.base import BaseCommand
# ... same logic as drink_by_reminder()
```

```crontab
# Host crontab (runs inside the wine-web container)
0 9 * * * docker compose -f /root/wine-cellar-personal/docker-compose.prod.yml \
    exec -T wine-web python manage.py send_drink_reminders \
    >> /mnt/usb/logs/drink_reminders.log 2>&1
```

### What Gets Removed

| Item | Action |
|------|--------|
| `celery-worker` service | Remove from both compose files |
| `celery-beat` service | Remove from both compose files |
| `celery` Python package | Remove from `requirements/base.txt` |
| `django-celery-beat` package | Remove from `requirements/base.txt` |
| `django_celery_beat` in INSTALLED_APPS | Remove from `settings.py` |
| `wine_cellar/conf/celery.py` | Delete |
| CELERY_* settings in `docker_settings.py` | Remove |
| `wine_cellar/apps/wine/tasks.py` | Convert to management command |

### What Stays

| Item | Why |
|------|-----|
| Redis | Still needed for Django cache (`CACHES` setting) |
| Redis container in compose | Required for caching |

### Future-Proofing

If you later need background tasks (e.g., price tracking, image processing), you can:
1. Re-add Celery — it's a pip install and a compose service away
2. Use Django-Q2 (lighter weight alternative, uses the existing DB as broker)
3. Use `subprocess` + management commands for simple one-off tasks
4. Use `django-huey` (minimal Redis-based task queue, much lighter than Celery)

The Celery infrastructure can be re-added in ~30 minutes if needed. Keeping it running 24/7 "just in case" costs 160MB of RAM permanently.

### Recommendation: Remove Celery, Use Cron

**Estimated savings: ~160MB RAM, 2 fewer containers, simpler dependency tree.**

---

## 4. Dockerfile Consolidation

### Current State

Two files exist:
- `Dockerfile` — standard x86-64
- `Dockerfile.rpi4` — ARM64 for Raspberry Pi

They are **100% identical** except for two lines:

```dockerfile
# Dockerfile.rpi4 has:
FROM --platform=linux/arm64 node:20-slim AS frontend-builder
FROM --platform=linux/arm64 python:3.12-slim

# Dockerfile has:
FROM node:20-slim AS frontend-builder
FROM python:3.12-slim
```

### The Problem

This is unnecessary duplication. Docker Buildx (which the GitHub Actions workflow already uses) handles platform selection automatically. The `--platform` directives in `Dockerfile.rpi4` are redundant when building with:

```yaml
# .github/workflows/rpi-docker.yml already does this:
- uses: docker/build-push-action@v6
  with:
    platforms: linux/arm64   # <-- buildx handles platform selection
    file: Dockerfile.rpi4    # <-- unnecessary, Dockerfile would work
```

### Recommendation: Delete Dockerfile.rpi4

1. Delete `Dockerfile.rpi4`
2. Update `.github/workflows/rpi-docker.yml` to use `Dockerfile`:
   ```yaml
   file: Dockerfile  # was: Dockerfile.rpi4
   ```
3. Buildx will automatically pull the correct `linux/arm64` base images

This is a zero-risk change — buildx already handles multi-platform builds.

---

## 5. Backup Gap (Critical)

### Current State

`backup_to_r2.sh` (line 88) only backs up wine media:

```bash
CONTAINER=$(docker compose ... ps -q wine-web ...)
docker cp "${CONTAINER}:/app/media" "${TMP_DIR}/media"
```

**Whisky media (`whisky_media_data` volume) is never backed up.**

Since the whisky app is actively used with real data, this is a data loss risk.

### What's at Risk

Whisky bottle images and any uploaded media. If the SD card or Docker volume is corrupted, this data is gone.

### Recommendation: Add Whisky Media Backup

Add a second media backup block to `backup_to_r2.sh`:

```bash
# Whisky media backup
WHISKY_CONTAINER=$(docker compose ... ps -q whisky-web ...)
if [ -n "$WHISKY_CONTAINER" ]; then
    docker cp "${WHISKY_CONTAINER}:/app/media" "${TMP_DIR}/whisky_media"
    tar czf "${TMP_DIR}/whisky_media_${TIMESTAMP}.tar.gz" -C "$TMP_DIR" whisky_media
    aws s3 cp "${TMP_DIR}/whisky_media_${TIMESTAMP}.tar.gz" \
        "s3://${BUCKET}/whisky_media/whisky_media_${TIMESTAMP}.tar.gz" ...
fi
```

Also add `whisky_media` to the R2 pruning loop.

**Priority: HIGH** — this is a live data loss risk.

---

## 6. Other Observations

### 6a. Startup Race Condition

Both `wine-web` and `whisky-web` run `python manage.py migrate` in the entrypoint. If they start simultaneously (which docker compose does by default), there's a potential race condition where both try to apply migrations at the same time. This is generally safe with PostgreSQL (it uses advisory locks for migrations), but could cause transient errors in logs.

**Minor fix:** Add a `depends_on` so whisky-web waits for wine-web to be healthy before starting, or move migrations to an init container.

### 6b. Celery Worker Only Uses Wine Env

The `celery-worker` service uses `.env.docker.prod` which sets `CELLAR_APP_TYPE=wine` (or doesn't set it, defaulting to wine). If whisky ever adds celery tasks, they would not be discovered because `autodiscover_tasks()` wouldn't find them without the whisky app in `INSTALLED_APPS`.

This is fine today but would be a gotcha if whisky tasks are added later.

### 6c. Redis Persistence

Redis is configured with `--appendonly yes` (AOF persistence). This is appropriate for a cache + broker role. However, since the only Celery task is a daily reminder (not mission-critical), AOF persistence for the broker is overkill. If Celery is removed and Redis is only used for caching, you could disable AOF to reduce disk I/O on the SD card:

```yaml
redis:
  command: redis-server --save ""  # disable RDB
  # remove --appendonly yes
```

### 6d. Gunicorn Worker Count

Both web containers run `--workers 2`. On a 4-core RPi4, this is reasonable. The typical formula is `2 * CPU_cores + 1`, but for a home server with low traffic, 2 workers per app is fine. If you consolidate to one web container, you could bump to 3-4 workers since they'd be shared.

### 6e. nginx vs Whitenoise

Whitenoise is already installed and configured (`whitenoise.middleware.WhiteNoiseMiddleware` in `MIDDLEWARE`). It handles static files directly from Django. The nginx container adds:
- Proper caching headers for static/media files
- SSL termination for meshnet HTTPS access
- Reverse proxy with `X-Forwarded-*` headers

Since Cloudflare Tunnel handles external SSL, and meshnet access needs the self-signed cert, nginx is still useful. Worth keeping.

### 6f. docker-celery-beat Is Pinned to a Git Commit

```
django-celery-beat@ git+https://github.com/celery/django-celery-beat.git@5cec89f66fd594572b28758416f8a9869f46bfdd
```

This pins to a specific commit rather than a release. If you keep Celery, pin to a stable release. If you remove Celery, this goes away entirely.

---

## 7. Recommended Changes (Priority Order)

### P1: Fix Whisky Backup (High impact, low effort, urgent)

**Risk:** Active data with no backup.

- Modify `backup_to_r2.sh` to back up whisky media to R2
- Add `whisky_media` prefix to R2 pruning
- Estimated effort: 30 minutes

### P2: Remove Celery (High impact, moderate effort)

**Savings:** ~160MB RAM, 2 fewer containers, fewer dependencies.

Files to modify:
- `docker-compose.prod.yml` — remove celery-worker and celery-beat services
- `docker-compose.yml` — remove celery-worker and celery-beat services (dev)
- `wine_cellar/apps/wine/tasks.py` — convert to management command
- `requirements/base.txt` — remove celery, django-celery-beat
- `wine_cellar/conf/settings.py` — remove `django_celery_beat` from INSTALLED_APPS
- `wine_cellar/conf/celery.py` — delete file
- `wine_cellar/conf/__init__.py` — remove celery app import if present
- `wine_cellar/conf/docker_settings.py` — remove CELERY_* settings
- `wine_cellar/conf/test.py` — remove CELERY_TASK_ALWAYS_EAGER
- Add: `wine_cellar/apps/wine/management/commands/send_drink_reminders.py`
- Add: host crontab entry documentation

Estimated effort: 2-3 hours including testing

### ~~P3: Delete Dockerfile.rpi4 (Low effort, reduces maintenance)~~ ✅ DONE

Consolidated into a single `Dockerfile` with multi-stage targets (`local` and `cloud`).
- `local` target: installs gosu, runs as root (entrypoint drops to django)
- `cloud` target: `USER django` directive, no gosu
- GHCR workflow uses `target: cloud`; docker-compose uses `target: local`

### P4: Web Container Consolidation (Medium impact, high effort) — DEFER

- Requires refactoring `CELLAR_APP_TYPE` from startup-time to per-request
- Routing middleware development and testing
- 150MB savings don't justify the complexity yet
- Revisit if RAM becomes tight or if a natural refactoring opportunity arises

---

## 8. After These Changes: Projected State

### Container Count: 5 → potentially 4

| Container | RAM (est.) | Purpose |
|-----------|------------|---------|
| `wine-web` | ~150MB | Wine app |
| `whisky-web` | ~150MB | Whisky app |
| `nginx` | ~10MB | Reverse proxy |
| `db` | ~100MB | PostgreSQL |
| `redis` | ~20MB | Cache only (no broker duties) |
| **Total** | **~430MB** | **Down from ~600MB (28% reduction)** |

### Dependency Reduction

Removed packages: `celery`, `django-celery-beat`, `kombu`, `billiard`, `vine`, `amqp`, `click`, `click-didyoumean`, `click-repl`, `click-plugins`, `python-crontab`, `cron-descriptor`, `django-timezone-field`

That's 13 fewer Python packages, a smaller Docker image, and a simpler dependency tree.

---

## 9. Open Questions

1. **Database separation:** Do wine-web and whisky-web use the same PostgreSQL database, or separate databases within the same PostgreSQL instance? (Check `.env.whisky.docker.prod` for `SQL_DATABASE` value.) If separate databases, this is further evidence they should stay as separate containers.

2. **Drink reminder schedule:** What time of day should the cron job run? The current Celery Beat schedule may be configured in the Django admin — check the `django_celery_beat_periodictask` table for the configured schedule before removing it.

3. **Email configuration:** Does the drink reminder task actually work end-to-end? If email isn't configured (no SMTP settings visible in the env samples), the task may be running silently without sending anything, which would make removing Celery even more straightforward.

4. **Redis without Celery:** With Celery removed, Redis is only used for Django caching. Consider whether `LocMemCache` (in-memory, no external service) would suffice. It wouldn't share cache between wine-web and whisky-web, but since they're separate apps with separate data, that may be fine. This could eliminate the Redis container entirely (saving ~30MB more).

5. **Monitoring:** Are you monitoring container health or resource usage? If the Pi is running fine at ~600MB, the optimisations are nice-to-have. If it's under memory pressure, they become more urgent.
