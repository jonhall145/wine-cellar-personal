# Backup and Restore

This guide covers backup and restore procedures for Wine Cellar data.

## What to Back Up

Wine Cellar stores data in two locations:

1. **Database** - All wine records, user accounts, settings, and inventory
2. **Media files** - Uploaded wine images (stored in `media/` directory)

## Database Backup

### PostgreSQL (Production)

#### Manual Backup

```bash
# Create a backup
pg_dump -U winecellar -h localhost winecellar > backup_$(date +%Y%m%d_%H%M%S).sql

# With compression
pg_dump -U winecellar -h localhost winecellar | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

#### Automated Backup Script

Create `/opt/winecellar/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/winecellar"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -U winecellar winecellar | gzip > "$BACKUP_DIR/db_$TIMESTAMP.sql.gz"

# Media files backup
tar -czf "$BACKUP_DIR/media_$TIMESTAMP.tar.gz" -C /path/to/winecellar media/

# Remove backups older than retention period
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $TIMESTAMP"
```

Add to crontab for daily backups:

```bash
# Run daily at 2:00 AM
0 2 * * * /opt/winecellar/backup.sh >> /var/log/winecellar-backup.log 2>&1
```

### SQLite (Development)

```bash
# Simple file copy
cp db.sqlite3 backup_$(date +%Y%m%d_%H%M%S).sqlite3

# With compression
gzip -c db.sqlite3 > backup_$(date +%Y%m%d_%H%M%S).sqlite3.gz
```

## Media Files Backup

Wine images are stored in the `media/` directory:

```bash
# Create archive
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz media/

# Sync to remote storage (example with rsync)
rsync -avz media/ user@backup-server:/backups/winecellar/media/
```

## Restore Procedures

### PostgreSQL Database

```bash
# Drop and recreate database (caution: destroys existing data)
dropdb -U winecellar winecellar
createdb -U winecellar winecellar

# Restore from backup
gunzip -c backup_20240115_120000.sql.gz | psql -U winecellar winecellar

# Or from uncompressed backup
psql -U winecellar winecellar < backup_20240115_120000.sql
```

### SQLite Database

```bash
# Stop the application first
# Replace database file
gunzip -c backup_20240115_120000.sqlite3.gz > db.sqlite3

# Or copy directly
cp backup_20240115_120000.sqlite3 db.sqlite3
```

### Media Files

```bash
# Extract media archive
tar -xzf media_backup_20240115_120000.tar.gz

# Ensure correct permissions
chown -R www-data:www-data media/
```

## Full Restore Procedure

1. **Stop the application**
   ```bash
   sudo ./run_prod_local.sh stop
   ```

2. **Restore database**
   ```bash
   gunzip -c backup.sql.gz | psql -U winecellar winecellar
   ```

3. **Restore media files**
   ```bash
   tar -xzf media_backup.tar.gz
   ```

4. **Run migrations** (if restoring to a newer version)
   ```bash
   source venv/bin/activate
   python manage.py migrate
   ```

5. **Restart the application**
   ```bash
   sudo ./run_prod_local.sh start
   ```

## Recommended Backup Schedule

| Data Type | Frequency | Retention |
|-----------|-----------|-----------|
| Database | Daily | 30 days |
| Media files | Weekly | 90 days |
| Full backup | Monthly | 1 year |

## Cloud Storage Options

Consider syncing backups to cloud storage:

- **AWS S3**: `aws s3 sync /var/backups/winecellar s3://your-bucket/winecellar/`
- **Backblaze B2**: `b2 sync /var/backups/winecellar b2://your-bucket/winecellar/`
- **Google Cloud**: `gsutil rsync -r /var/backups/winecellar gs://your-bucket/winecellar/`

## Testing Backups

Regularly test your backups by restoring to a test environment:

1. Set up a separate test instance
2. Restore the latest backup
3. Verify data integrity
4. Document the restore time

## Troubleshooting

### Permission Errors

```bash
# Fix database permissions
sudo chown postgres:postgres backup.sql

# Fix media permissions
sudo chown -R www-data:www-data media/
```

### Disk Space

Monitor backup disk usage:

```bash
du -sh /var/backups/winecellar/
```

### Verify Backup Integrity

```bash
# Check PostgreSQL backup
gunzip -t backup.sql.gz && echo "Backup OK"

# Check tar archive
tar -tzf media_backup.tar.gz > /dev/null && echo "Archive OK"
```
