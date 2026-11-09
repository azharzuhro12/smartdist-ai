# SmartDist AI — Production Architecture Specification

## 1. System Overview

SmartDist AI is an enterprise-grade intelligent distribution and retail management platform. The Phase 5 production architecture enforces strict defense-in-depth security, non-root container isolation, least-privilege role segregation across data tiers, and automated operational resilience.

```mermaid
graph TD
    User["End User / Browser"] --> |HTTPS / Port 3000| Frontend["Next.js 14 Dashboard<br/>(Non-root: nextjs:1001)"]
    Frontend --> |Internal Network / HTTP 8000| Backend["FastAPI REST Application<br/>(Non-root: smartdist:smartdist)"]
    Backend --> |PostgreSQL 5432<br/>Role: smartdist_app (DML Only)| Postgres[(PostgreSQL 16 Engine<br/>Non-exposed Host Port)]
    Backend --> |Redis 6379 (Auth Token & Rate Limits)| Redis[(Redis 7 Cluster<br/>Non-exposed Host Port)]
    Backend --> |Enqueue Celery Jobs| Redis
    Redis --> |Broker / Result Backend| Worker["Celery Worker Fleet<br/>(Non-root: smartdist:smartdist)"]
    Worker --> |Batch Processing / Anomaly Runs| Postgres
    Backend --> |Read-Only SQL Agent Queries<br/>Role: smartdist_readonly| Postgres
```

---

## 2. Infrastructure Architecture & Service Topology

| Component | Technology | Network Exposure | Execution User | Resource Limits |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | Next.js 14 (App Router) | Port 3000 (Host/Proxy) | `nextjs` (UID 1001) | 1.5 CPUs, 1536MB RAM |
| **Backend API** | FastAPI + Uvicorn (4 Workers) | Internal Docker Network | `smartdist` (system nologin) | 2.0 CPUs, 2048MB RAM |
| **Worker Engine** | Celery 5.4.0 (Redis Broker) | Internal Docker Network | `smartdist` (system nologin) | 1.5 CPUs, 1536MB RAM |
| **Database** | PostgreSQL 16 Alpine | Internal Docker Network only | `postgres` (Least-Privilege Roles) | 2.0 CPUs, 2048MB RAM |
| **In-Memory Store**| Redis 7 Alpine | Internal Docker Network only | `redis` (Password-authenticated) | 1.0 CPUs, 1024MB RAM |

---

## 3. Network Isolation and Port Security

1. **Host Boundary**:
   - In production (`docker-compose.prod.yml`), database (5432) and Redis (6379) ports are **NOT** bound to host network interfaces.
   - Traffic between Frontend, Backend, Redis, and PostgreSQL flows exclusively through the bridge network `smartdist_prod_network`.
2. **Reverse Proxy & Entry Points**:
   - Only the frontend dashboard (port 3000) or an external NGINX / Cloudflare reverse proxy is publicly reachable.
   - API traffic is forwarded through Next.js route rewrites or internal ingress.

---

## 4. Multi-Stage Non-Root Container Builds

- **Backend (`Dockerfile.backend`)**:
  - Python 3.12 slim base with separate dependency installation layer.
  - Dedicated unprivileged system user `smartdist` (`useradd -r -s /sbin/nologin`).
  - Strict filesystem ownership (`chown -R smartdist:smartdist /app`).
  - Native health checks (`curl -f http://localhost:8000/health`).
- **Frontend (`Dockerfile.frontend`)**:
  - Multi-stage Node.js build (`deps` -> `builder` -> `runner`).
  - Standalone Next.js production build executed as `nextjs:nodejs` (`UID 1001`).
  - Embedded container healthcheck (`wget -q -O - http://127.0.0.1:3000/login`).

---

## 5. Security & Isolation Matrix

| Layer | Mechanism | Implementation Detail |
| :--- | :--- | :--- |
| **Transport Security** | Headers & CSP | Strict CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff |
| **Authentication** | Argon2id + HS256 JWT | 30-min expiration, Redis revocation token blocklist |
| **Session Cookies** | Secure Flags | `HttpOnly`, `SameSite=Lax`, `Secure` in production |
| **CSRF Defense** | Double-Submit Token | Read-only `csrf_token` cookie + `X-CSRF-Token` header on mutating methods |
| **Rate Limiting** | Sliding Window | Redis-backed with Fail-Closed policy on authentication (HTTP 503) |
| **Database Access** | Role Segregation | `smartdist_owner` (Alembic DDL), `smartdist_app` (DML), `smartdist_readonly` (BI/AI) |

