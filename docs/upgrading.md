# Upgrading Wine Cellar

This guide covers upgrading Wine Cellar to newer versions.

## Before Upgrading

### 1. Back Up Your Data

Always create a backup before upgrading:

```bash
# Database backup
pg_dump -U winecellar winecellar > backup_$(date +%Y%m%d).sql

# Media files backup
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
```

See [backup.md](backup.md) for detailed backup procedures.

### 2. Check Release Notes

Review the [CHANGELOG.md](../CHANGELOG.md) for:
- Breaking changes
- New environment variables
- Database migration notes
- Deprecated features

### 3. Check Python/Node Compatibility

Verify your Python and Node.js versions meet requirements:

```bash
python --version  # Requires 3.10+
node --version    # Requires 20+
```

## Upgrade Procedure

### Standard Upgrade

```bash
# 1. Stop the application
sudo ./run_prod_local.sh stop

# 2. Pull latest changes
git fetch origin
git checkout main
git pull origin main

# 3. Activate virtual environment
source venv/bin/activate

# 4. Update Python dependencies
pip install -r requirements/prod.txt

# 5. Update Node dependencies and rebuild frontend
npm install
npm run build:prod

# 6. Apply database migrations
python manage.py migrate

# 7. Collect static files
python manage.py collectstatic --noinput

# 8. Restart the application
sudo ./run_prod_local.sh start
```

### Docker Upgrade

If using Docker:

```bash
# Pull new image
docker-compose pull

# Restart with new image
docker-compose down
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate
```

## Version-Specific Notes

### Upgrading to 0.3.x

**New Features:**
- Multiple image upload support
- OpenID Connect authentication
- Bottle pricing in stock items

**New Environment Variables:**
- `ANTHROPIC_API_KEY` - For vision-based wine label extraction (optional)

**Database Migrations:**
- New `WineImage` table
- New `price` field on `StorageItem`

```bash
python manage.py migrate
```

### Upgrading to 0.2.x

**New Features:**
- Barcode scanning
- Storage grid view
- Drink-by reminders

**Required:**
- Configure Celery for email reminders (optional)

## Handling Migration Issues

### Migration Conflicts

If you see migration conflicts:

```bash
# Show migration status
python manage.py showmigrations

# Fake a migration if already applied manually
python manage.py migrate --fake app_name migration_name
```

### Failed Migrations

If a migration fails:

1. **Don't panic** - your backup is safe
2. Check the error message
3. Review the migration file
4. Fix any data issues
5. Re-run `python manage.py migrate`

### Rollback Procedure

If you need to rollback:

```bash
# 1. Stop the application
sudo ./run_prod_local.sh stop

# 2. Restore database
dropdb winecellar
createdb winecellar
psql winecellar < backup_20240115.sql

# 3. Restore media files
rm -rf media/
tar -xzf media_backup_20240115.tar.gz

# 4. Checkout previous version
git checkout v0.2.0

# 5. Reinstall dependencies
pip install -r requirements/prod.txt
npm install
npm run build:prod

# 6. Restart
sudo ./run_prod_local.sh start
```

## Post-Upgrade Verification

After upgrading, verify:

1. **Application starts**: Check logs for errors
2. **Login works**: Test authentication
3. **Data intact**: Verify wine list loads
4. **Features work**: Test barcode scanner, image upload
5. **Background tasks**: Check Celery is running (if configured)

```bash
# Check application logs
tail -f /var/log/winecellar/gunicorn.log

# Check Celery logs (if using)
tail -f /var/log/winecellar/celery.log
```

## Troubleshooting

### Static Files Not Loading

```bash
python manage.py collectstatic --clear --noinput
```

### 500 Internal Server Error

Check logs:
```bash
tail -100 /var/log/winecellar/gunicorn.log
```

Common causes:
- Missing environment variables
- Database connection issues
- Missing migrations

### Module Not Found Errors

Reinstall dependencies:
```bash
pip install -r requirements/prod.txt --force-reinstall
```

### JavaScript Errors

Rebuild frontend:
```bash
rm -rf build/
npm run build:prod
```

## Maintaining Multiple Environments

For staging/production workflow:

```bash
# Test upgrade on staging first
ssh staging
cd /opt/winecellar
# Follow upgrade procedure

# Verify staging works, then upgrade production
ssh production
cd /opt/winecellar
# Follow upgrade procedure
```

## Getting Help

If you encounter issues:

1. Check [GitHub Issues](https://github.com/the-broke-sommeliers/wine-cellar/issues)
2. Review error logs
3. Open a new issue with:
   - Version upgrading from/to
   - Error messages
   - Steps to reproduce
