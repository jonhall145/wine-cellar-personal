#!/bin/bash
set -e
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Wine Cellar - Backup to Cloudflare R2
# Supports both SQLite (bare-metal) and PostgreSQL (Docker) deployments.
#
# Usage:
#   ./backup_to_r2.sh              # Auto-detect: Docker if running, else SQLite
#   ./backup_to_r2.sh sqlite       # Force SQLite backup
#   ./backup_to_r2.sh docker       # Force Docker PostgreSQL backup
#
# Cron (Docker prod):
#   0 3 * * * /root/wine-cellar-personal/backup_to_r2.sh docker >> /var/log/wine_backup.log 2>&1

PROJECT_DIR="/root/wine-cellar-personal"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env.docker.prod"
DB_PATH="${PROJECT_DIR}/db.sqlite3"
MEDIA_PATH="${PROJECT_DIR}/media"
BUCKET="wine-cellar-backups"
R2_ENDPOINT="https://f129ddee08c640885efbc88d7d79c0a0.r2.cloudflarestorage.com"
AWS_PROFILE="r2"
KEEP_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TMP_DIR=$(mktemp -d)

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

# Determine backup mode
MODE="${1:-auto}"
if [ "$MODE" = "auto" ]; then
    if docker compose -f "${PROJECT_DIR}/${COMPOSE_FILE}" ps --status running db 2>/dev/null | grep -q db; then
        MODE="docker"
    else
        MODE="sqlite"
    fi
fi

echo "[$(date)] Starting backup (mode: ${MODE})..."

# ─── Database backup ─────────────────────────────────────────────────

if [ "$MODE" = "docker" ]; then
    # PostgreSQL backup via Docker
    if [ ! -f "$ENV_FILE" ]; then
        echo "Error: $ENV_FILE not found"
        exit 1
    fi

    PG_DB=$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2)
    PG_USER=$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2)

    echo "  Backing up PostgreSQL database (${PG_DB})..."
    docker compose -f "${PROJECT_DIR}/${COMPOSE_FILE}" exec -T db \
        pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-privileges \
        | gzip > "${TMP_DIR}/db_${TIMESTAMP}.pg.sql.gz"

    DB_BACKUP="${TMP_DIR}/db_${TIMESTAMP}.pg.sql.gz"
    R2_DB_PREFIX="db"
else
    # SQLite backup (legacy bare-metal)
    if [ ! -f "$DB_PATH" ]; then
        echo "Error: $DB_PATH not found"
        exit 1
    fi

    echo "  Backing up SQLite database..."
    sqlite3 "$DB_PATH" ".backup ${TMP_DIR}/db_${TIMESTAMP}.sqlite3"
    gzip "${TMP_DIR}/db_${TIMESTAMP}.sqlite3"

    DB_BACKUP="${TMP_DIR}/db_${TIMESTAMP}.sqlite3.gz"
    R2_DB_PREFIX="db"
fi

# Verify backup is not empty
if [ ! -s "$DB_BACKUP" ]; then
    echo "Error: Database backup is empty"
    exit 1
fi

# ─── Media backup ────────────────────────────────────────────────────

if [ "$MODE" = "docker" ]; then
    # Extract media from Docker volume
    echo "  Backing up media files from Docker volume..."
    CONTAINER=$(docker compose -f "${PROJECT_DIR}/${COMPOSE_FILE}" ps -q web 2>/dev/null | head -1)
    if [ -n "$CONTAINER" ]; then
        docker cp "${CONTAINER}:/app/media" "${TMP_DIR}/media" 2>/dev/null || true
        if [ -d "${TMP_DIR}/media" ] && [ "$(ls -A "${TMP_DIR}/media" 2>/dev/null)" ]; then
            tar czf "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" -C "$TMP_DIR" media
        fi
    fi
elif [ -d "$MEDIA_PATH" ]; then
    echo "  Backing up media files..."
    tar czf "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" -C "$(dirname "$MEDIA_PATH")" "$(basename "$MEDIA_PATH")"
fi

# ─── Upload to R2 ────────────────────────────────────────────────────

echo "  Uploading to R2..."
DB_FILENAME=$(basename "$DB_BACKUP")
aws s3 cp "$DB_BACKUP" \
    "s3://${BUCKET}/${R2_DB_PREFIX}/${DB_FILENAME}" \
    --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"

if [ -f "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" ]; then
    aws s3 cp "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" \
        "s3://${BUCKET}/media/media_${TIMESTAMP}.tar.gz" \
        --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"
fi

# ─── Prune old backups ───────────────────────────────────────────────

echo "  Pruning backups older than ${KEEP_DAYS} days..."
cutoff=$(date -d "-${KEEP_DAYS} days" +%Y%m%d 2>/dev/null || date -v-${KEEP_DAYS}d +%Y%m%d)

for prefix in db media; do
    aws s3 ls "s3://${BUCKET}/${prefix}/" \
        --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE" 2>/dev/null \
    | awk '{print $4}' | while read -r file; do
        # Extract date from filename (e.g., db_20260204_030000.pg.sql.gz -> 20260204)
        file_date=$(echo "$file" | grep -oP '\d{8}' | head -1)
        if [ -n "$file_date" ] && [ "$file_date" -lt "$cutoff" ]; then
            echo "    Deleting old backup: ${prefix}/${file}"
            aws s3 rm "s3://${BUCKET}/${prefix}/${file}" \
                --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"
        fi
    done
done

echo "[$(date)] Backup complete: ${TIMESTAMP}"
