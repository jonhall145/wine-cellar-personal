#!/bin/bash
# pg_backup.sh - Back up the Dockerized PostgreSQL database
#
# Usage:
#   ./pg_backup.sh                    # Uses docker-compose.prod.yml
#   ./pg_backup.sh dev                # Uses docker-compose.yml (dev)
#
# Backups are saved to ./backups/ with timestamps.
# Add to cron for automated backups:
#   0 3 * * * cd /root/wine-cellar-personal && ./pg_backup.sh >> /var/log/pg_backup.log 2>&1

set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Determine which compose file to use
if [ "${1:-prod}" = "dev" ]; then
    COMPOSE_FILE="docker-compose.yml"
    ENV_FILE=".env.docker"
else
    COMPOSE_FILE="docker-compose.prod.yml"
    ENV_FILE=".env.docker.prod"
fi

# Load database credentials from env file
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found"
    exit 1
fi

DB_NAME=$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2)
DB_USER=$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2)

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "Error: Could not read POSTGRES_DB or POSTGRES_USER from $ENV_FILE"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "Backing up $DB_NAME from $COMPOSE_FILE..."

# Run pg_dump inside the db container and compress
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
    | gzip > "$BACKUP_FILE"

# Verify the backup is not empty
if [ ! -s "$BACKUP_FILE" ]; then
    echo "Error: Backup file is empty"
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup saved: $BACKUP_FILE ($BACKUP_SIZE)"

# Remove backups older than 30 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete 2>/dev/null || true
echo "Cleaned up backups older than 30 days"
