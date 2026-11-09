# SmartDist AI — Security Operations & Threat Model

## 1. Authentication Lifecycle & Credential Management

### Password Hashing
- Algorithm: **Argon2id** (`argon2-cffi`).
- Salt length: 16 bytes. Time cost: 3 iterations. Memory cost: 65,536 KiB (64 MiB). Parallelism: 4 threads.
- Constant-time verification prevents side-channel timing attacks.

### Token Expiration & Revocation
- JWT signature algorithm: **HS256**.
- Access token lifespan: **30 minutes**.
- Revocation mechanism:
  - On user logout (`POST /api/v1/auth/logout`), the token's JTI / raw signature is written to Redis key `revoked_token:<token>` with TTL equal to the token's remaining validity duration.
  - Every authenticated request verifies token presence against Redis. If revoked, HTTP 401 Unauthorized is immediately returned.

---

## 2. Double-Submit CSRF & Origin Verification

SmartDist AI enforces defense-in-depth CSRF protection:
1. **Origin & Referer Validation**:
   - For all cookie-authenticated mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`), the `Origin` or `Referer` header is inspected against `settings.CORS_ORIGINS`.
   - Disallowed origins are rejected with HTTP 403 Forbidden.
2. **Double-Submit CSRF Cookie**:
   - On successful authentication, the backend issues an un-hashed random hex cookie: `csrf_token` (`samesite=lax`, `secure` in production).
   - The frontend API client extracts this cookie and includes it in the `X-CSRF-Token` HTTP header.
   - The backend `ObservabilityAndSecurityMiddleware` performs constant-time validation (`secrets.compare_digest`) between the cookie value and header value. Requests failing this match are rejected with HTTP 403 Forbidden.
   - Non-browser API clients authenticating strictly via `Authorization: Bearer <token>` without ambient cookies are exempt.

---

## 3. Rate Limiting & Fail-Closed Security Policy

- Distributed rate limiter tracks request frequencies via Redis sliding windows:
  - **Login Route**: 5 attempts per minute per IP.
  - **AI Assistant**: 30 requests per minute per IP / user.
- **Fail-Closed Policy**:
  - In authentication and security-critical endpoints, `fail_closed=True` is mandated.
  - If Redis fails or network connectivity is severed, the system rejects attempts with `HTTP 503 Service Unavailable` rather than silently opening the door to brute-force attacks.

---

## 4. PostgreSQL Least-Privilege Role Hardening

| Role | Classification | Permissions | Denied Actions |
| :--- | :--- | :--- | :--- |
| `smartdist_owner` | Schema Owner | Migration execution, DDL, table creation, index management | `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION` |
| `smartdist_app` | Runtime App | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on operational tables | `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`, DDL |
| `smartdist_readonly` | AI Agent & BI | `SELECT` on business entities (`products`, `branches`, `daily_sales`, `inventory`) | `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, DDL, and `users` table access |

### Live Verification Evidence:
```sql
SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication 
FROM pg_roles WHERE rolname = 'smartdist_owner';
-- Result: rolsuper=f, rolcreatedb=f, rolcreaterole=f, rolreplication=f
```
Direct attempts by `smartdist_readonly` to access `users` table:
`psycopg2.errors.InsufficientPrivilege: permission denied for table users`.

---

## 5. Security Incident Response & Audit Checklist

1. **Suspected Compromised User**:
   - Run `PATCH /api/v1/users/{id}` with `is_active=false`. The JWT dependency checks `user.is_active` on every request.
2. **Credential Rotation Procedure**:
   - Rotate database passwords using `ALTER ROLE ... WITH PASSWORD ...`.
   - Update `.env.production` and run `docker compose -f docker-compose.prod.yml restart backend celery_worker`.
3. **Secret Leakage Prevention**:
   - `Settings` validator enforces that `SECRET_KEY` cannot contain development markers (`dev`, `example`, `change_in_production`) and must have $\ge 32$ characters in production environments.

