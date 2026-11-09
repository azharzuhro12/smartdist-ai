# SmartDist AI — Phase 5.1: Security Configuration & Deployment Guide

> **Document Status**: Production Security Operations & Configuration Reference  
> **Milestone**: Phase 5.1 — Security Foundation  
> **Target Date**: November 2026  
> **Repository**: `~/Documents/smartdist-ai`  

---

## 1. Environment Variable Reference

All sensitive parameters, signing secrets, and connection URIs are managed via environment variables and loaded through `backend.app.core.config.Settings`:

| Variable Name | Default Value (Dev) | Production Requirement | Description |
|---|---|---|---|
| `SECRET_KEY` | `smartdist_dev_secret_key_...` | **REQUIRED** (Random >=256 bits) | Secret key used to sign and verify HMAC-SHA256 JWT access tokens. |
| `ALGORITHM` | `HS256` | `HS256` | JWT cryptographic signature algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | `15` to `30` | Access token lifespan in minutes. |
| `POSTGRES_SERVER` | `localhost` / `postgres` | Target DB Host | PostgreSQL server host. |
| `POSTGRES_PORT` | `5435` (Docker: `5432`) | `5432` | PostgreSQL listening port. |
| `POSTGRES_DB` | `smartdist_db` | Production DB Name | Database name. |
| `POSTGRES_USER` | `smartdist_app` | Runtime DB Role | Non-owner application runtime user. |
| `POSTGRES_PASSWORD` | `***` | **REQUIRED** | Password for runtime role. |
| `POSTGRES_MIGRATION_URL` | None (defaults to owner) | Owner Connection URI | Connection string for Alembic schema migrations. |
| `POSTGRES_READONLY_URL` | None (defaults to readonly) | Readonly URI | Connection string for AI Assistant least-privilege executor. |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `5` | `5` | Maximum failed login requests per client IP per minute before HTTP 429. |
| `RATE_LIMIT_ASSISTANT_PER_MINUTE` | `30` | `30` | Maximum AI queries per user per minute. |
| `INITIAL_ADMIN_USERNAME` | `admin` | Custom Admin Handle | Default administrator handle seeded on first startup. |
| `INITIAL_ADMIN_EMAIL` | `admin@smartdist.ai` | Admin Email | Default administrator email address. |
| `INITIAL_ADMIN_PASSWORD` | `Admin@SmartDist2026!` | Strong Password | Default administrator password seeded on first startup. |
| `CORS_ORIGINS` | `["http://localhost:3000", ...]` | Explicit FQDNs | Pinned origins permitted for CORS requests. |

---

## 2. Local Development & Provisioning Quickstart

### Step 1: Start Infrastructure
```bash
docker compose up -d postgres redis
```

### Step 2: Apply Database Migrations (Owner Role)
```bash
PYTHONPATH=. .venv/bin/alembic -c backend/alembic.ini upgrade head
```

### Step 3: Provision PostgreSQL Least-Privilege Roles
```bash
python -c "
import psycopg2
from backend.app.core.config import settings

with open('scripts/provision_db_roles.sql') as f:
    sql = f.read()

conn = psycopg2.connect(
    host=settings.POSTGRES_SERVER,
    port=settings.POSTGRES_PORT,
    dbname=settings.POSTGRES_DB,
    user=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(sql)
conn.close()
print('Least-privilege database roles successfully provisioned.')
"
```

### Step 4: Seed Initial Admin User
```bash
PYTHONPATH=. .venv/bin/python -c "
from backend.app.db.session import SessionLocal
from backend.app.db.init_db import init_db
with SessionLocal() as db:
    init_db(db)
"
```

### Step 5: Start Backend API
```bash
PYTHONPATH=. .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 6: Start Next.js Frontend Dashboard
```bash
cd frontend && npm run dev
```

---

## 3. Security Quality Gates & Verification

Execute the full regression verification suite:

```bash
# 1. Full Backend Test Suite (215 tests)
PYTHONPATH=. .venv/bin/python -m pytest -v

# 2. Frontend Static Type Check
cd frontend && npx tsc --noEmit

# 3. Frontend ESLint Check
cd frontend && npm run lint

# 4. Frontend Production Build Compilation
cd frontend && npm run build
```

