# SmartDist AI — Database Backup & Restore Standard Operating Procedure

## 1. Overview & Strategy

Database resilience for SmartDist AI uses PostgreSQL's native custom-format archiving (`pg_dump -Fc`), featuring:
- **Consistent snapshots** using MVCC transactions with zero table locking.
- **Zstandard / gzip compression** minimizing disk storage footprint by ~70–80%.
- **Cryptographic integrity validation** with automatic SHA256 checksum generation.
- **Least-privilege isolation**: Backups can be taken under `smartdist_app` or `smartdist_owner` without requiring database superuser privileges.
- **Fail-safe restoration**: Protection against accidental overwriting of active databases.

---

## 2. Backup Procedure (`scripts/backup_db.sh`)

The backup script automatically detects whether `pg_dump` is available locally or via Docker container:

```bash
# Execute standard backup
./scripts/backup_db.sh
```

### Environment Overrides:
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `BACKUP_DIR` | `./backups` | Target directory for dump and checksum files |
| `POSTGRES_SERVER` | `localhost` | Database host |
| `POSTGRES_PORT` | `5435` | Database port |
| `POSTGRES_DB` | `smartdist_db`| Source database name |
| `POSTGRES_USER` | `smartdist_user` | PostgreSQL connection user |
| `DOCKER_CONTAINER`| `smartdist_postgres`| Container name if running containerized |

### Execution Output Example:
```text
[2026-11-09T20:25:48+07:00] Starting database backup for 'smartdist_db'...
[2026-11-09T20:25:53+07:00] Backup completed successfully.
Backup File: ./backups/smartdist_db_backup_20261109_202548.dump (9.2M)
Checksum:    b84f9739264c91fd3a558b335a6ff7d8a89b0194aeb0feda6813152c6b4c7b9c
```

---

## 3. Scheduled Automated Backups (Cron)

To establish automated daily backups at 02:00 AM UTC:
```bash
# Open crontab editor
crontab -e

# Add scheduled backup job
0 2 * * * cd /opt/smartdist-ai && ./scripts/backup_db.sh >> /var/log/smartdist_backup.log 2>&1

# Add weekly retention cleanup (retain 14 days of backups)
0 3 * * 0 find /opt/smartdist-ai/backups/ -type f -name "*.dump*" -mtime +14 -delete
```

---

## 4. Disaster Recovery & Restoration Procedure (`scripts/restore_db.sh`)

### Safe Testing Against an Isolated Temporary Database:
```bash
# 1. Create temporary database
docker exec smartdist_postgres psql -U smartdist_user -d postgres -c "CREATE DATABASE smartdist_backup_test;"

# 2. Run restore script pointing to the temporary database
./scripts/restore_db.sh ./backups/smartdist_db_backup_20261109_202548.dump smartdist_backup_test

# 3. Verify restored tables and row counts
docker exec smartdist_postgres psql -U smartdist_user -d smartdist_backup_test -c "
SELECT 'users' as tbl, count(*) FROM users
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'branches', count(*) FROM branches
UNION ALL SELECT 'inventory', count(*) FROM inventory
UNION ALL SELECT 'daily_sales', count(*) FROM daily_sales;
"

# 4. Clean up temporary test database
docker exec smartdist_postgres psql -U smartdist_user -d postgres -c "DROP DATABASE smartdist_backup_test;"
```

### Live Production Restoration Guard:
If restoration against `smartdist_db` is attempted, the script actively halts with an error:
```text
SAFETY ERROR: Attempting to restore over primary database 'smartdist_db'!
To explicitly confirm overwrite of the primary database, set ALLOW_PRODUCTION_OVERWRITE=1
```
To proceed in a true disaster recovery scenario:
```bash
ALLOW_PRODUCTION_OVERWRITE=1 ./scripts/restore_db.sh ./backups/smartdist_db_backup_20261109_202548.dump smartdist_db
```

