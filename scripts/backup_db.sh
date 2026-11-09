#!/usr/bin/env bash
# ==============================================================================
# SmartDist AI - Production Database Backup Script
# Creates a compressed, custom-format PostgreSQL dump using pg_dump -Fc.
# ==============================================================================

set -euo pipefail

# Configuration parameters with sensible defaults
BACKUP_DIR="${BACKUP_DIR:-./backups}"
POSTGRES_HOST="${POSTGRES_SERVER:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5435}"
POSTGRES_DB="${POSTGRES_DB:-smartdist_db}"
POSTGRES_USER="${POSTGRES_USER:-smartdist_user}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}_backup_${TIMESTAMP}.dump"

# Ensure target directory exists
mkdir -p "${BACKUP_DIR}"

DOCKER_CONTAINER="${DOCKER_CONTAINER:-smartdist_postgres}"

echo "[$(date -Iseconds)] Starting database backup for '${POSTGRES_DB}'..."

if command -v pg_dump >/dev/null 2>&1; then
    PGPASSWORD="${POSTGRES_PASSWORD:-smartdist_secure_password}" pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        -Fc \
        -f "${BACKUP_FILE}"
elif docker ps --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
    docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-smartdist_secure_password}" \
        "${DOCKER_CONTAINER}" pg_dump \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        -Fc > "${BACKUP_FILE}"
else
    echo "Error: Neither pg_dump nor running container '${DOCKER_CONTAINER}' found." >&2
    exit 1
fi

# Generate SHA256 integrity checksum
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"

BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
echo "[$(date -Iseconds)] Backup completed successfully."
echo "Backup File: ${BACKUP_FILE} (${BACKUP_SIZE})"
echo "Checksum:    $(cat "${BACKUP_FILE}.sha256")"
