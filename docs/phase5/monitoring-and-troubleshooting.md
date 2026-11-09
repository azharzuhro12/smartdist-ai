# SmartDist AI — Monitoring & Troubleshooting Guide

## 1. Observability Architecture

SmartDist AI incorporates lightweight, zero-dependency production observability:
1. **Correlation / Request ID**:
   - Inbound `X-Request-ID` or `X-Correlation-ID` is extracted or assigned via UUIDv4.
   - Stored in an async-safe `ContextVar` (`backend.app.core.middleware.correlation_id_ctx`).
   - Attached to all log entries and returned in response headers (`X-Request-ID`).
2. **Structured Logging**:
   - JSON-formatted logs in production (`LOG_FORMAT=json`).
   - Request latency tracking in milliseconds for all API requests.
   - Credentials, passwords, tokens, and sensitive query strings are filtered out from log emitters.
3. **Deep Health Checks**:
   - Root Health (`GET /health`): Process responsiveness check.
   - Deep Readiness Check (`GET /api/v1/health`): Upstream dependency health (PostgreSQL, Redis, Celery worker ping).

---

## 2. Health & Readiness Endpoint Reference

### Request: `GET /api/v1/health`
```json
{
  "status": "healthy",
  "app_name": "SmartDist AI",
  "version": "0.1.0",
  "environment": "production",
  "timestamp": "2026-11-09T13:30:00.000000+00:00",
  "services": {
    "database": "connected",
    "redis": "connected",
    "celery": "active (4 workers)"
  }
}
```

### Status Definitions:
- **`healthy`**: PostgreSQL and Redis are both online, Celery workers responding.
- **`degraded`**: One auxiliary component is impaired (e.g. Redis offline, Celery unavailable), but database is intact.
- **`unhealthy`**: Core database is disconnected or unreachable.

---

## 3. Production Troubleshooting Playbook

### Scenario A: Authentication Fails with HTTP 503
- **Symptoms**: Users receive `503 Service Unavailable` on `/api/v1/auth/login`.
- **Cause**: Redis rate limiter storage is unreachable. Under the Phase 5 fail-closed policy, logins are blocked to prevent brute-force exploitation.
- **Troubleshooting**:
  ```bash
  # Check Redis container status
  docker compose -f docker-compose.prod.yml ps redis
  
  # Inspect Redis logs
  docker compose -f docker-compose.prod.yml logs --tail=50 redis
  
  # Test Redis ping manually
  docker exec smartdist_prod_redis redis-cli -a <password> ping
  ```

### Scenario B: AI Assistant Query Fails with Database Error
- **Symptoms**: AI Assistant displays `Database execution failed: permission denied for table users`.
- **Cause**: Expected behavior. The SQL Assistant is bound to the `smartdist_readonly` PostgreSQL role. It is strictly denied access to sensitive user and authentication entities.
- **Remediation**: Advise user that queries regarding user credentials, passwords, or system administrative tables are restricted by security policy.

### Scenario C: Celery Background Job Stalled or Not Consumed
- **Symptoms**: Long-running ingestion or anomaly runs remain in `PENDING` status.
- **Troubleshooting**:
  ```bash
  # Check Celery worker container status
  docker compose -f docker-compose.prod.yml ps celery_worker
  
  # Review worker logs
  docker compose -f docker-compose.prod.yml logs --tail=100 celery_worker
  
  # Check Redis queue length
  docker exec smartdist_prod_redis redis-cli -a <password> llen celery
  ```

### Scenario D: High Memory or Container Crash
- **Symptoms**: Next.js frontend or Uvicorn backend terminates with OOM (Exit code 137).
- **Troubleshooting**:
  ```bash
  # Check Docker resource usage
  docker stats --no-stream
  
  # If required, adjust memory allocations in docker-compose.prod.yml
  # under deploy.resources.limits.memory
  ```

