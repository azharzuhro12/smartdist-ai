# SmartDist AI — Production Deployment Guide

## 1. Prerequisites

- Host OS: Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9 recommended).
- Docker Engine: 24.0+ and Docker Compose v2.20+.
- Domain name with TLS termination configured (or Cloudflare / Nginx reverse proxy).
- Minimum hardware requirements: 4 vCPUs, 8 GB RAM, 50 GB NVMe SSD.

---

## 2. Configuration Setup

1. Clone the repository to the production server:
   ```bash
   git clone <repo_url> /opt/smartdist-ai
   cd /opt/smartdist-ai
   ```

2. Generate production secrets:
   ```bash
   # Generate a 64-character hex secret key for JWT
   openssl rand -hex 32
   
   # Generate strong passwords for DB roles and Redis
   openssl rand -base64 24
   ```

3. Create the production environment file:
   ```bash
   cp .env.production.example .env.production
   chmod 600 .env.production
   ```
   Edit `.env.production` and paste your generated secrets:
   - Set `SECRET_KEY` (must be $\ge 32$ characters, no placeholder words).
   - Set `POSTGRES_OWNER_PASSWORD`, `POSTGRES_APP_PASSWORD`, `POSTGRES_READONLY_PASSWORD`.
   - Set `REDIS_PASSWORD`.
   - Set `CORS_ORIGINS=["https://smartdist.yourcompany.com"]`.

---

## 3. Database Initialization & Migration

1. Start database and cache services:
   ```bash
   PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml up -d postgres redis
   ```

2. Wait for health checks to pass:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```

3. Execute schema migrations under the `smartdist_owner` role:
   ```bash
   PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml run --rm backend \
       alembic upgrade head
   ```

4. Verify least-privilege roles provisioning:
   ```bash
   docker exec -i smartdist_prod_postgres psql -U smartdist_owner -d smartdist_db < scripts/provision_db_roles.sql
   ```

---

## 4. Full Application Launch

Start all application services (Backend, Celery Worker, Frontend):
```bash
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml up -d --build
```

Verify service status:
```bash
docker compose -f docker-compose.prod.yml ps
```

Expected output:
```text
NAME                         IMAGE               COMMAND                  SERVICE             STATUS
smartdist_prod_backend       ...                 "uvicorn backend.app..." backend             healthy (up)
smartdist_prod_celery_worker ...                 "celery -A backend.a..." celery_worker       up
smartdist_prod_frontend      ...                 "npm start"              frontend            healthy (up)
smartdist_prod_postgres      postgres:16-alpine  "docker-entrypoint.s..." postgres            healthy (up)
smartdist_prod_redis         redis:7-alpine      "docker-entrypoint.s..." redis               healthy (up)
```

---

## 5. Reverse Proxy Configuration (NGINX Example)

```nginx
server {
    listen 443 ssl http2;
    server_name smartdist.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/smartdist.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/smartdist.yourcompany.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Forward frontend and client requests
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 6. Zero-Downtime Rolling Update Procedure

```bash
# 1. Pull new codebase
git pull origin master

# 2. Rebuild images
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml build

# 3. Run migrations
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 4. Restart services sequentially
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml up -d --no-deps backend
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml up -d --no-deps celery_worker
PROD_ENV_FILE=.env.production docker compose -f docker-compose.prod.yml up -d --no-deps frontend
```

