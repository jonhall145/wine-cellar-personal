#!/bin/bash
# migrate_to_postgres.sh
# Migrates data from the local SQLite database into the Dockerized PostgreSQL database.
#
# Prerequisites:
#   - SQLite db.sqlite3 exists in the project root
#   - Docker compose services are configured (docker-compose.yml)
#   - The venv with Django is activated (for dumpdata from SQLite)
#
# Usage:
#   ./migrate_to_postgres.sh
#
# WARNING: This is a one-time migration script. Do NOT run while the web
# container is performing its own initial migrations.

set -euo pipefail

SQLITE_DB="db.sqlite3"
DUMP_FILE="data_dump.json"
BACKUP_DIR="./backups"

# ─── Pre-flight checks ───────────────────────────────────────────────

if [ ! -f "$SQLITE_DB" ]; then
    echo "Error: $SQLITE_DB not found. Nothing to migrate."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Activate your venv first."
    exit 1
fi

# ─── Step 1: Back up SQLite ──────────────────────────────────────────

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${SQLITE_DB}.pre_migration_${TIMESTAMP}"
echo "Backing up SQLite database to $BACKUP_FILE..."
cp "$SQLITE_DB" "$BACKUP_FILE"

# ─── Step 2: Count rows in SQLite for verification ───────────────────

echo ""
echo "SQLite row counts (for verification):"
SQLITE_COUNTS=$(python3 -c "
import sqlite3, json
conn = sqlite3.connect('$SQLITE_DB')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'django_migrations'\")
tables = cursor.fetchall()
total = 0
for (table,) in sorted(tables):
    cursor.execute(f'SELECT COUNT(*) FROM \"{table}\"')
    count = cursor.fetchone()[0]
    if count > 0:
        print(f'  {table}: {count}')
        total += count
print(f'  --- Total: {total}')
conn.close()
")
echo "$SQLITE_COUNTS"

# ─── Step 3: Dump data from SQLite ───────────────────────────────────

echo ""
echo "Dumping data from SQLite..."
python3 manage.py dumpdata \
    --exclude auth.permission \
    --exclude contenttypes \
    --exclude admin.logentry \
    --exclude sessions.session \
    --indent 2 \
    > "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "Dump created: $DUMP_FILE ($DUMP_SIZE)"

# ─── Step 4: Start Docker services ──────────────────────────────────

echo ""
echo "Starting Docker database and web services..."
docker compose up -d db web

echo "Waiting for PostgreSQL to be healthy..."
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -q 2>/dev/null; then
        echo "PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "Error: PostgreSQL did not become ready in time"
        exit 1
    fi
    sleep 1
done

# Wait a bit more for the web container to finish its own migrations
echo "Waiting for web container migrations to complete..."
sleep 10

# ─── Step 5: Load data into PostgreSQL ───────────────────────────────

echo ""
echo "Loading data into PostgreSQL..."
docker compose cp "$DUMP_FILE" web:/app/"$DUMP_FILE"
docker compose exec -T web python manage.py loaddata "$DUMP_FILE"

# ─── Step 6: Verify row counts in PostgreSQL ─────────────────────────

echo ""
echo "PostgreSQL row counts (for verification):"
docker compose exec -T web python manage.py shell -c "
from django.apps import apps
total = 0
for model in sorted(apps.get_models(), key=lambda m: m._meta.db_table):
    count = model.objects.count()
    if count > 0:
        print(f'  {model._meta.db_table}: {count}')
        total += count
print(f'  --- Total: {total}')
"

# ─── Step 7: Cleanup ─────────────────────────────────────────────────

echo ""
echo "Cleaning up dump file..."
rm -f "$DUMP_FILE"
docker compose exec -T web rm -f "/app/$DUMP_FILE" 2>/dev/null || true

echo ""
echo "Migration complete!"
echo "SQLite backup saved at: $BACKUP_FILE"
echo ""
echo "Next steps:"
echo "  1. Compare the row counts above to verify data integrity"
echo "  2. Test the application at http://localhost:8003"
echo "  3. Check media files are accessible (thumbnails, uploads)"
