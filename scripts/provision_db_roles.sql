-- ============================================================================
-- SmartDist AI — PostgreSQL Least-Privilege Role Provisioning Script
-- Idempotent setup for:
-- 1. smartdist_owner   (Alembic Migrations & Schema Owner - NOSUPERUSER)
-- 2. smartdist_app     (Application Runtime - Operational DML only)
-- 3. smartdist_readonly(SQL Assistant Engine - SELECT only on approved business tables)
-- ============================================================================

DO $$
BEGIN
    -- 1. Create smartdist_owner if not exists (Strictly non-superuser, no cluster or DB creation rights)
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'smartdist_owner') THEN
        CREATE ROLE smartdist_owner WITH LOGIN PASSWORD 'smartdist_owner_secure_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSE
        ALTER ROLE smartdist_owner WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;

    -- 2. Create smartdist_app if not exists (Application runtime: DML only, no schema modification rights)
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'smartdist_app') THEN
        CREATE ROLE smartdist_app WITH LOGIN PASSWORD 'smartdist_app_secure_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSE
        ALTER ROLE smartdist_app WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;

    -- 3. Create smartdist_readonly if not exists (AI SQL Assistant: SELECT only on approved business tables)
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'smartdist_readonly') THEN
        CREATE ROLE smartdist_readonly WITH LOGIN PASSWORD 'smartdist_readonly_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSE
        ALTER ROLE smartdist_readonly WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END $$;

-- Database level connections
GRANT CONNECT ON DATABASE smartdist_db TO smartdist_app;
GRANT CONNECT ON DATABASE smartdist_db TO smartdist_readonly;

-- Schema usage
GRANT USAGE ON SCHEMA public TO smartdist_app;
GRANT USAGE ON SCHEMA public TO smartdist_readonly;

-- ----------------------------------------------------------------------------
-- Grants for Application Runtime Role (smartdist_app)
-- ----------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartdist_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartdist_app;

-- Default privileges for future tables created by owner
ALTER DEFAULT PRIVILEGES FOR ROLE smartdist_owner IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartdist_app;

ALTER DEFAULT PRIVILEGES FOR ROLE smartdist_owner IN SCHEMA public 
    GRANT USAGE, SELECT ON SEQUENCES TO smartdist_app;

-- ----------------------------------------------------------------------------
-- Grants for SQL Assistant Read-Only Role (smartdist_readonly)
-- ----------------------------------------------------------------------------
-- Explicit SELECT only on approved business domain tables
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'products') THEN
        GRANT SELECT ON TABLE public.products TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'categories') THEN
        GRANT SELECT ON TABLE public.categories TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'branches') THEN
        GRANT SELECT ON TABLE public.branches TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'daily_sales') THEN
        GRANT SELECT ON TABLE public.daily_sales TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'inventories') THEN
        GRANT SELECT ON TABLE public.inventories TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'inventory_transactions') THEN
        GRANT SELECT ON TABLE public.inventory_transactions TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'sales_anomalies') THEN
        GRANT SELECT ON TABLE public.sales_anomalies TO smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'anomaly_detection_runs') THEN
        GRANT SELECT ON TABLE public.anomaly_detection_runs TO smartdist_readonly;
    END IF;
END $$;

-- Explicitly REVOKE access to sensitive security & audit tables
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users') THEN
        REVOKE ALL ON TABLE public.users FROM smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'data_import_logs') THEN
        REVOKE ALL ON TABLE public.data_import_logs FROM smartdist_readonly;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version') THEN
        REVOKE ALL ON TABLE public.alembic_version FROM smartdist_readonly;
    END IF;
END $$;

-- Safety defaults enforced at database role level for smartdist_readonly
ALTER ROLE smartdist_readonly SET default_transaction_read_only = on;
ALTER ROLE smartdist_readonly SET statement_timeout = '5000ms';

