#!/bin/bash
set -e

# Wine Cellar - Backup to Cloudflare R2
# Usage: ./backup_to_r2.sh
# Cron:  0 3 * * * /root/wine-cellar-personal/backup_to_r2.sh >> /var/log/wine_backup.log 2>&1

DB_PATH="/root/wine-cellar-personal/db.sqlite3"
MEDIA_PATH="/root/wine-cellar-personal/media"
BUCKET="wine-cellar-backups"
R2_ENDPOINT="https://f129ddee08c640885efbc88d7d79c0a0.r2.cloudflarestorage.com"
AWS_PROFILE="r2"
KEEP_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TMP_DIR=$(mktemp -d)

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

echo "[$(date)] Starting backup..."

# 1. Safe hot-copy of SQLite database (avoids corruption from open connections)
echo "  Backing up database..."
sqlite3 "$DB_PATH" ".backup ${TMP_DIR}/db_${TIMESTAMP}.sqlite3"

# 2. Compress it
gzip "${TMP_DIR}/db_${TIMESTAMP}.sqlite3"

# 3. Tar the media directory (wine images, uploaded files)
if [ -d "$MEDIA_PATH" ]; then
    echo "  Backing up media files..."
    tar czf "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" -C "$(dirname "$MEDIA_PATH")" "$(basename "$MEDIA_PATH")"
fi

# 4. Upload to R2
echo "  Uploading to R2..."
aws s3 cp "${TMP_DIR}/db_${TIMESTAMP}.sqlite3.gz" \
    "s3://${BUCKET}/db/db_${TIMESTAMP}.sqlite3.gz" \
    --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"

if [ -f "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" ]; then
    aws s3 cp "${TMP_DIR}/media_${TIMESTAMP}.tar.gz" \
        "s3://${BUCKET}/media/media_${TIMESTAMP}.tar.gz" \
        --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"
fi

# 5. Prune old backups (keep last N days)
echo "  Pruning backups older than ${KEEP_DAYS} days..."
cutoff=$(date -d "-${KEEP_DAYS} days" +%Y%m%d 2>/dev/null || date -v-${KEEP_DAYS}d +%Y%m%d)

for prefix in db media; do
    aws s3 ls "s3://${BUCKET}/${prefix}/" \
        --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE" 2>/dev/null \
    | awk '{print $4}' | while read -r file; do
        # Extract date from filename (e.g., db_20260204_030000.sqlite3.gz -> 20260204)
        file_date=$(echo "$file" | grep -oP '\d{8}' | head -1)
        if [ -n "$file_date" ] && [ "$file_date" -lt "$cutoff" ]; then
            echo "    Deleting old backup: ${prefix}/${file}"
            aws s3 rm "s3://${BUCKET}/${prefix}/${file}" \
                --endpoint-url "$R2_ENDPOINT" --profile "$AWS_PROFILE"
        fi
    done
done

echo "[$(date)] Backup complete: ${TIMESTAMP}"
