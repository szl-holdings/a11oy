-- SPDX-License-Identifier: Apache-2.0
-- Forward-only corrective migration for Memory Covenant v2 installations.
-- Apply after both 20260811 migrations. This source migration does not claim
-- that any production database has been altered.

BEGIN;

SET LOCAL search_path = pg_catalog, pg_temp;

-- Historical schemas allowed audit/idempotency rows to reference a receipt by
-- globally unique receipt_id alone. Refuse to mask any cross-domain data before
-- replacing those relationships with tenant/domain-bound foreign keys.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.memory_query_audit AS audit
          JOIN public.memory_receipts AS receipt
            ON receipt.receipt_id = audit.receipt_id
         WHERE (audit.tenant_id, audit.security_domain)
               IS DISTINCT FROM
               (receipt.tenant_id, receipt.security_domain)
    ) THEN
        RAISE EXCEPTION USING
          ERRCODE = '23503',
          MESSAGE = 'memory_query_audit contains a cross-domain receipt reference';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM public.memory_idempotency AS idem
          JOIN public.memory_receipts AS receipt
            ON receipt.receipt_id = idem.receipt_id
         WHERE (idem.tenant_id, idem.security_domain)
               IS DISTINCT FROM
               (receipt.tenant_id, receipt.security_domain)
    ) THEN
        RAISE EXCEPTION USING
          ERRCODE = '23503',
          MESSAGE = 'memory_idempotency contains a cross-domain receipt reference';
    END IF;
END;
$$;

-- Remove every historical receipt foreign key on the two child tables. This
-- includes the original receipt_id-only keys and any stale variants.
DO $$
DECLARE
    relationship record;
BEGIN
    FOR relationship IN
        SELECT child.relname AS table_name, constraint_row.conname
          FROM pg_catalog.pg_constraint AS constraint_row
          JOIN pg_catalog.pg_class AS child ON child.oid = constraint_row.conrelid
          JOIN pg_catalog.pg_namespace AS child_namespace
            ON child_namespace.oid = child.relnamespace
         WHERE constraint_row.contype = 'f'
           AND constraint_row.confrelid = 'public.memory_receipts'::pg_catalog.regclass
           AND child_namespace.nspname = 'public'
           AND child.relname IN ('memory_query_audit', 'memory_idempotency')
    LOOP
        EXECUTE pg_catalog.format(
            'ALTER TABLE public.%I DROP CONSTRAINT %I',
            relationship.table_name,
            relationship.conname
        );
    END LOOP;
END;
$$;

ALTER TABLE public.memory_receipts
  DROP CONSTRAINT IF EXISTS memory_receipts_tenant_domain_receipt_key;
ALTER TABLE public.memory_receipts
  ADD CONSTRAINT memory_receipts_tenant_domain_receipt_key
  UNIQUE (tenant_id, security_domain, receipt_id);
ALTER TABLE public.memory_query_audit
  ADD CONSTRAINT memory_query_audit_tenant_domain_receipt_fkey
  FOREIGN KEY (tenant_id, security_domain, receipt_id)
  REFERENCES public.memory_receipts (tenant_id, security_domain, receipt_id)
  ON DELETE RESTRICT;
ALTER TABLE public.memory_idempotency
  ADD CONSTRAINT memory_idempotency_tenant_domain_receipt_fkey
  FOREIGN KEY (tenant_id, security_domain, receipt_id)
  REFERENCES public.memory_receipts (tenant_id, security_domain, receipt_id)
  ON DELETE RESTRICT;

-- PostgreSQL OR-combines permissive policies. Delete every stale policy and
-- reinstall exactly one tenant/domain policy per covenant table.
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT c.relname AS table_name, p.polname AS policy_name
          FROM pg_catalog.pg_policy AS p
          JOIN pg_catalog.pg_class AS c ON c.oid = p.polrelid
          JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency'
           )
    LOOP
        EXECUTE pg_catalog.format(
            'DROP POLICY %I ON public.%I',
            policy_row.policy_name,
            policy_row.table_name
        );
    END LOOP;
END;
$$;

CREATE POLICY memory_records_isolation ON public.memory_records
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_evidence_refs_isolation ON public.memory_evidence_refs
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_outbox_isolation ON public.memory_outbox
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_receipts_isolation ON public.memory_receipts
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_query_audit_isolation ON public.memory_query_audit
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_index_generations_isolation ON public.memory_index_generations
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));
CREATE POLICY memory_idempotency_isolation ON public.memory_idempotency
USING (public.a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));

-- Normalize both pre-existing capability roles. Lacking CREATE ROLE or ALTER
-- ROLE authority aborts this transaction; there is no notice-only fallback.
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

-- Revoke first so reapplication converges from stale additive ACLs.
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
