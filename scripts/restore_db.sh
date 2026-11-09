#!/usr/bin/env bash
# ==============================================================================
# SmartDist AI - Production Database Restore Script
# Restores a custom-format dump using pg_restore.
# ==============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.dump> [target_database]"
    echo "Example: $0 ./backups/smartdist_db_backup_20261109_120000.dump smartdist_backup_test"
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="${2:-${POSTGRES_DB:-smartdist_db}}"
POSTGRES_HOST="${POSTGRES_SERVER:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5435}"
POSTGRES_USER="${POSTGRES_USER:-smartdist_user}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

# 1. Verify SHA256 checksum if exists
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "[$(date -Iseconds)] Verifying checksum..."
    sha256sum -c "${BACKUP_FILE}.sha256"
fi

# 2. Safety guard: Do not restore over active database without explicit confirmation
if [ "${TARGET_DB}" = "smartdist_db" ] && [ "${ALLOW_PRODUCTION_OVERWRITE:-0}" != "1" ]; then
    echo "SAFETY ERROR: Attempting to restore over primary database '${TARGET_DB}'!" >&2
    echo "To explicitly confirm overwrite of the primary database, set ALLOW_PRODUCTION_OVERWRITE=1" >&2
    exit 1
fi

DOCKER_CONTAINER="${DOCKER_CONTAINER:-smartdist_postgres}"

echo "[$(date -Iseconds)] Restoring '${BACKUP_FILE}' into '${TARGET_DB}'..."

if command -v pg_restore >/dev/null 2>&1; then
    PGPASSWORD="${POSTGRES_PASSWORD:-smartdist_secure_password}" pg_restore \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${TARGET_DB}" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        "${BACKUP_FILE}" || true
elif docker ps --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
    cat "${BACKUP_FILE}" | docker exec -i \
        -e PGPASSWORD="${POSTGRES_PASSWORD:-smartdist_secure_password}" \
        "${DOCKER_CONTAINER}" pg_restore \
        -U "${POSTGRES_USER}" \
        -d "${TARGET_DB}" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists || true
else
    echo "Error: Neither pg_restore nor running container '${DOCKER_CONTAINER}' found." >&2
    exit 1
fi

echo "[$(date -Iseconds)] Restore to '${TARGET_DB}' completed."
