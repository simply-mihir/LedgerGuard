-- Initialization script for PostgreSQL instances in LedgerGuard
-- Creates application runtime user and read-only reporting user

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        CREATE ROLE ledgerguard_app WITH LOGIN PASSWORD 'ledgerguard_app_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        CREATE ROLE ledgerguard_reporter WITH LOGIN PASSWORD 'ledgerguard_reporter_secret';
    END IF;
END
$$;
