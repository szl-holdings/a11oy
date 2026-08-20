-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant v0.1 — role/RLS and worker hardening.
-- Apply after 20260811_memory_covenant_v2.sql.
-- PostgreSQL remains authoritative; derived indexes remain rebuildable.

BEGIN;

-- The runtime login is expected to inherit this role. It is deliberately
-- NOBYPASSRLS so tenant + security-domain policies remain effective even when
-- the migration owner itself has provider-level BYPASSRLS privileges.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a11oy_memory_app') THEN
        CREATE ROLE a11oy_memory_app NOLOGIN INHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE a11oy_memory_app NOLOGIN INHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO a11oy_memory_app;
GRANT SELECT, INSERT, UPDATE ON memory_records TO a11oy_memory_app;
GRANT SELECT, INSERT, DELETE ON memory_evidence_refs TO a11oy_memory_app;
GRANT SELECT, INSERT ON memory_receipts TO a11oy_memory_app;
GRANT SELECT, INSERT ON memory_query_audit TO a11oy_memory_app;
GRANT SELECT, INSERT, UPDATE ON memory_index_generations TO a11oy_memory_app;
GRANT SELECT, INSERT ON memory_idempotency TO a11oy_memory_app;
GRANT SELECT, INSERT ON memory_outbox TO a11oy_memory_app;

-- The outbox worker is a separate capability. It receives no table-wide role
-- bypass. Cross-tenant leasing is exposed only through the bounded
-- SECURITY DEFINER function below.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a11oy_memory_worker') THEN
        CREATE ROLE a11oy_memory_worker NOLOGIN INHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE a11oy_memory_worker NOLOGIN INHERIT NOBYPASSRLS;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'Could not create a11oy_memory_worker role; create it before enabling workers.';
END;
$$;

-- The table owner must be able to execute the definer function across tenant
-- partitions, while ordinary application sessions remain RLS-bound.
ALTER TABLE memory_outbox NO FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION memory_lease_outbox(
    p_worker_id text,
    p_limit integer DEFAULT 25,
    p_lease_seconds integer DEFAULT 30
)
RETURNS SETOF memory_outbox
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF p_worker_id IS NULL OR p_worker_id = '' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker id is required';
    END IF;
    IF p_limit < 1 OR p_limit > 500 OR p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker lease bounds are invalid';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='a11oy_memory_worker')
       OR NOT pg_has_role(session_user, 'a11oy_memory_worker', 'member') THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='session user is not an a11oy_memory_worker member';
    END IF;

    RETURN QUERY
    WITH candidates AS (
        SELECT event_id
          FROM memory_outbox
         WHERE status IN ('PENDING','RETRY','LEASED')
           AND available_at <= now()
           AND (lease_expires_at IS NULL OR lease_expires_at <= now())
         ORDER BY available_at, event_id
         FOR UPDATE SKIP LOCKED
         LIMIT p_limit
    )
    UPDATE memory_outbox AS event
       SET status='LEASED',
           attempts=event.attempts + 1,
           lease_owner=p_worker_id,
           lease_expires_at=now() + make_interval(secs => p_lease_seconds),
           updated_at=now()
      FROM candidates
     WHERE event.event_id = candidates.event_id
    RETURNING event.*;
END;
$$;

REVOKE ALL ON FUNCTION memory_lease_outbox(text, integer, integer) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='a11oy_memory_worker') THEN
        GRANT EXECUTE ON FUNCTION memory_lease_outbox(text, integer, integer)
            TO a11oy_memory_worker;
    END IF;
END;
$$;

COMMENT ON FUNCTION memory_lease_outbox(text, integer, integer) IS
    'Bounded cross-tenant lease for dedicated worker role members only.';

COMMIT;
