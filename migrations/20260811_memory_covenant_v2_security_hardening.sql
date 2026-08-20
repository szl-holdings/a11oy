-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant v0.1 — role/RLS and worker hardening.
-- Apply after 20260811_memory_covenant_v2.sql.
-- PostgreSQL remains authoritative; derived indexes remain rebuildable.

BEGIN;

SET LOCAL search_path = pg_catalog, pg_temp;

-- The runtime login is expected to inherit this capability role. Existing
-- roles are normalized, not trusted. Any missing authority aborts the entire
-- transaction; a partially hardened role must never be treated as enabled.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_app') THEN
        CREATE ROLE a11oy_memory_app
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE a11oy_memory_app
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    END IF;
END;
$$;

-- The outbox worker receives no table-wide bypass. Cross-tenant leasing is
-- exposed only through the bounded SECURITY DEFINER function below.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_worker') THEN
        CREATE ROLE a11oy_memory_worker
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE a11oy_memory_worker
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    END IF;
END;
$$;

-- Reapplication is subtractive before it is additive. This removes stale
-- excess ACLs from the two capability roles and from PUBLIC before restoring
-- the exact table contract.
REVOKE ALL PRIVILEGES ON SCHEMA public
  FROM a11oy_memory_app, a11oy_memory_worker;
REVOKE ALL PRIVILEGES ON TABLE
    public.memory_records,
    public.memory_evidence_refs,
    public.memory_outbox,
    public.memory_receipts,
    public.memory_query_audit,
    public.memory_index_generations,
    public.memory_idempotency
  FROM PUBLIC, a11oy_memory_app, a11oy_memory_worker;

GRANT USAGE ON SCHEMA public TO a11oy_memory_app, a11oy_memory_worker;
GRANT SELECT, INSERT, UPDATE ON TABLE public.memory_records TO a11oy_memory_app;
GRANT SELECT, INSERT, DELETE ON TABLE public.memory_evidence_refs TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_receipts TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_query_audit TO a11oy_memory_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.memory_index_generations TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_idempotency TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_outbox TO a11oy_memory_app;

-- The table owner must be able to execute the definer function across tenant
-- partitions, while ordinary application sessions remain RLS-bound.
ALTER TABLE public.memory_outbox NO FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.memory_lease_outbox(
    p_worker_id text,
    p_limit integer DEFAULT 25,
    p_lease_seconds integer DEFAULT 30
)
RETURNS SETOF public.memory_outbox
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF p_worker_id IS NULL OR p_worker_id = '' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker id is required';
    END IF;
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 500
       OR p_lease_seconds IS NULL OR p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker lease bounds are invalid';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='a11oy_memory_worker'
    ) OR NOT pg_catalog.pg_has_role(
        session_user,
        'a11oy_memory_worker',
        'member'
    ) THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='session user is not an a11oy_memory_worker member';
    END IF;

    RETURN QUERY
    WITH candidates AS (
        SELECT event_id
          FROM public.memory_outbox
         WHERE status IN ('PENDING','RETRY','LEASED')
           AND available_at <= pg_catalog.now()
           AND (lease_expires_at IS NULL OR lease_expires_at <= pg_catalog.now())
         ORDER BY available_at, event_id
         FOR UPDATE SKIP LOCKED
         LIMIT p_limit
    )
    UPDATE public.memory_outbox AS event
       SET status='LEASED',
           attempts=event.attempts + 1,
           lease_owner=p_worker_id,
           lease_expires_at=pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
           updated_at=pg_catalog.now()
      FROM candidates
     WHERE event.event_id = candidates.event_id
    RETURNING event.*;
END;
$$;

-- CREATE OR REPLACE preserves an existing ACL. First revoke PUBLIC explicitly,
-- then remove every stale non-owner EXECUTE grantee before granting the sole
-- worker capability.
REVOKE ALL PRIVILEGES ON FUNCTION public.memory_lease_outbox(text, integer, integer)
  FROM PUBLIC;
DO $$
DECLARE
    grantee_oid oid;
BEGIN
    FOR grantee_oid IN
        SELECT DISTINCT acl.grantee
          FROM pg_catalog.pg_proc AS p
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
          ) AS acl
         WHERE p.oid = 'public.memory_lease_outbox(text,integer,integer)'::pg_catalog.regprocedure
           AND acl.privilege_type = 'EXECUTE'
           AND acl.grantee <> p.proowner
    LOOP
        IF grantee_oid = 0 THEN
            REVOKE EXECUTE ON FUNCTION public.memory_lease_outbox(text, integer, integer)
              FROM PUBLIC;
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE EXECUTE ON FUNCTION public.memory_lease_outbox(text, integer, integer) FROM %I',
                pg_catalog.pg_get_userbyid(grantee_oid)
            );
        END IF;
    END LOOP;
END;
$$;

GRANT EXECUTE ON FUNCTION public.memory_lease_outbox(text, integer, integer)
  TO a11oy_memory_worker;

COMMENT ON FUNCTION public.memory_lease_outbox(text, integer, integer) IS
    'Bounded cross-tenant lease for dedicated worker role members only.';

COMMIT;
