-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant v0.1
-- PostgreSQL is authoritative. Derived indexes are rebuildable.

BEGIN;

-- Never let a caller-controlled current schema redirect covenant objects.
SET LOCAL search_path = pg_catalog, pg_temp;

CREATE TABLE IF NOT EXISTS public.memory_records (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    memory_id text NOT NULL,
    schema_version text NOT NULL CHECK (schema_version = 'szl-memory/2.0'),
    memory_class text NOT NULL CHECK (memory_class IN ('working','evidence','policy','decision','outcome','quarantine')),
    compatibility_type text NOT NULL CHECK (compatibility_type IN ('WORKING','EPISODIC','SEMANTIC','PROCEDURAL','POLICY','PREFERENCE','RESEARCH','OUTCOME','NEGATIVE')),
    classification text NOT NULL CHECK (classification IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','SECRET')),
    lifecycle_state text NOT NULL CHECK (lifecycle_state IN ('ACTIVE','INDEX_PENDING','INDEXED','QUARANTINED','EXPIRED','TOMBSTONED','REINDEX_PENDING','FAILED')),
    legal_hold boolean NOT NULL DEFAULT false,
    expires_at timestamptz,
    active_index_generation text NOT NULL,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    record_sha256 char(64) NOT NULL CHECK (record_sha256 ~ '^[0-9a-f]{64}$'),
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json) = 'object'),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, security_domain, memory_id),
    CHECK (tenant_id <> '' AND security_domain <> '' AND memory_id <> ''),
    CHECK (record_json->>'tenant_id' = tenant_id),
    CHECK (record_json->>'security_domain' = security_domain),
    CHECK (record_json->>'memory_id' = memory_id),
    CHECK (record_json->>'schema_version' = schema_version)
);

CREATE TABLE IF NOT EXISTS public.memory_evidence_refs (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    memory_id text NOT NULL,
    digest char(64) NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    uri text NOT NULL CHECK (uri ~ '^cas://sha256/[0-9a-f]{64}$'),
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 255),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, security_domain, memory_id, digest),
    FOREIGN KEY (tenant_id, security_domain, memory_id)
      REFERENCES public.memory_records (tenant_id, security_domain, memory_id)
      ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS public.memory_outbox (
    event_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    memory_id text NOT NULL,
    generation_id text NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('INDEX_UPSERT','INDEX_DELETE','REINDEX_UPSERT','REINDEX_DELETE')),
    payload_json jsonb NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','LEASED','RETRY','DONE','FAILED')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text,
    lease_expires_at timestamptz,
    last_error text,
    result_json jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (tenant_id <> '' AND security_domain <> '' AND memory_id <> ''),
    CHECK ((status = 'LEASED') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.memory_receipts (
    receipt_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    namespace text NOT NULL,
    seq bigint NOT NULL CHECK (seq > 0),
    prev_digest char(64) NOT NULL CHECK (prev_digest ~ '^[0-9a-f]{64}$'),
    digest char(64) NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    mode text NOT NULL CHECK (mode IN ('UNSIGNED-CONTENT-DIGEST','SIGNED-AND-VERIFIED')),
    operation text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('ALLOW','DENY')),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    receipt_json jsonb NOT NULL CHECK (jsonb_typeof(receipt_json) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (namespace, seq),
    UNIQUE (namespace, digest),
    CONSTRAINT memory_receipts_tenant_domain_receipt_key
      UNIQUE (tenant_id, security_domain, receipt_id),
    CHECK (namespace = tenant_id || ':' || security_domain),
    CHECK (receipt_json->>'receipt_id' = receipt_id),
    CHECK (receipt_json->'integrity'->>'digest' = digest)
);

CREATE TABLE IF NOT EXISTS public.memory_query_audit (
    audit_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    receipt_id text NOT NULL,
    query_digest char(64) NOT NULL CHECK (query_digest ~ '^[0-9a-f]{64}$'),
    result_digest char(64) NOT NULL CHECK (result_digest ~ '^[0-9a-f]{64}$'),
    returned_ids text[] NOT NULL DEFAULT '{}',
    rejected_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(rejected_json) = 'object'),
    audit_json jsonb NOT NULL CHECK (jsonb_typeof(audit_json) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT memory_query_audit_tenant_domain_receipt_fkey
      FOREIGN KEY (tenant_id, security_domain, receipt_id)
      REFERENCES public.memory_receipts (tenant_id, security_domain, receipt_id)
      ON DELETE RESTRICT,
    CHECK (audit_json->>'audit_id' = audit_id),
    CHECK (audit_json->>'query_digest' = query_digest),
    CHECK (audit_json->>'result_digest' = result_digest)
);

CREATE TABLE IF NOT EXISTS public.memory_index_generations (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    generation_id text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    revision text NOT NULL,
    dimension integer NOT NULL CHECK (dimension BETWEEN 1 AND 65536),
    metric text NOT NULL CHECK (metric IN ('cosine','euclidean','dot')),
    normalization text NOT NULL CHECK (normalization IN ('none','l2','provider-defined')),
    identity_digest char(64) NOT NULL CHECK (identity_digest ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('BUILDING','ACTIVE','RETIRED','FAILED')),
    verified_count bigint CHECK (verified_count IS NULL OR verified_count >= 0),
    verified_digest char(64) CHECK (verified_digest IS NULL OR verified_digest ~ '^[0-9a-f]{64}$'),
    generation_json jsonb NOT NULL CHECK (jsonb_typeof(generation_json) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    PRIMARY KEY (tenant_id, security_domain, generation_id),
    UNIQUE (tenant_id, security_domain, identity_digest)
);

CREATE UNIQUE INDEX IF NOT EXISTS memory_one_active_generation
  ON public.memory_index_generations (tenant_id, security_domain)
  WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS public.memory_idempotency (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    operation text NOT NULL,
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    response_json jsonb NOT NULL CHECK (jsonb_typeof(response_json) = 'object'),
    receipt_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, security_domain, operation, idempotency_key),
    CONSTRAINT memory_idempotency_tenant_domain_receipt_fkey
      FOREIGN KEY (tenant_id, security_domain, receipt_id)
      REFERENCES public.memory_receipts (tenant_id, security_domain, receipt_id)
      ON DELETE RESTRICT
);

-- RLS context is accepted only for explicitly bound session principals. Role
-- OIDs are used instead of names so a dropped-and-recreated login cannot
-- inherit a stale tenant/domain binding through name reuse.
CREATE TABLE IF NOT EXISTS public.memory_context_bindings (
    principal_oid oid NOT NULL,
    tenant_id text NOT NULL CHECK (tenant_id <> ''),
    security_domain text NOT NULL CHECK (security_domain <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (principal_oid, tenant_id, security_domain)
);

-- Inspect physical binding rows independently of any stale RLS policy. Owner
-- convergence plus NO FORCE makes the migration principal's scan unfiltered;
-- both ALTERs roll back if the fail-closed preflight rejects a nonempty table.
ALTER TABLE public.memory_context_bindings OWNER TO CURRENT_USER;
ALTER TABLE public.memory_context_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_context_bindings NO FORCE ROW LEVEL SECURITY;

-- This schema has no durable, row-level record of which principal inserted a
-- binding. Current owners, ACLs, and helper source cannot prove historical
-- write provenance: a temporary INSERT grant may already have been revoked.
-- Refuse every nonempty reapplication so an operator must reconcile and
-- reprovision bindings explicitly instead of silently blessing planted data.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN
        RAISE EXCEPTION USING
          ERRCODE = '23514',
          MESSAGE = 'pre-existing memory_context_bindings rows lack durable write provenance';
    END IF;
END;
$$;

-- Ownership is part of the privilege boundary: an old owner has implicit ACLs
-- and can change RLS. Reapplication converges every covenant relation on the
-- trusted migration principal or aborts if that authority is unavailable.
ALTER TABLE public.memory_records OWNER TO CURRENT_USER;
ALTER TABLE public.memory_evidence_refs OWNER TO CURRENT_USER;
ALTER TABLE public.memory_outbox OWNER TO CURRENT_USER;
ALTER TABLE public.memory_receipts OWNER TO CURRENT_USER;
ALTER TABLE public.memory_query_audit OWNER TO CURRENT_USER;
ALTER TABLE public.memory_index_generations OWNER TO CURRENT_USER;
ALTER TABLE public.memory_idempotency OWNER TO CURRENT_USER;

CREATE INDEX IF NOT EXISTS memory_records_searchable_idx
  ON public.memory_records (tenant_id, security_domain, active_index_generation, memory_id)
  WHERE lifecycle_state IN ('ACTIVE','INDEXED');
CREATE INDEX IF NOT EXISTS memory_records_expiry_idx
  ON public.memory_records (expires_at)
  WHERE expires_at IS NOT NULL AND lifecycle_state NOT IN ('EXPIRED','TOMBSTONED');
CREATE INDEX IF NOT EXISTS memory_outbox_ready_idx
  ON public.memory_outbox (available_at, event_id)
  WHERE status IN ('PENDING','RETRY','LEASED');
CREATE INDEX IF NOT EXISTS memory_receipts_namespace_idx
  ON public.memory_receipts (tenant_id, security_domain, seq);
CREATE INDEX IF NOT EXISTS memory_query_audit_time_idx
  ON public.memory_query_audit (tenant_id, security_domain, created_at DESC);

CREATE OR REPLACE FUNCTION public.memory_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;
ALTER FUNCTION public.memory_touch_updated_at() OWNER TO CURRENT_USER;
REVOKE ALL PRIVILEGES ON FUNCTION public.memory_touch_updated_at()
  FROM PUBLIC;

DROP TRIGGER IF EXISTS memory_records_touch_updated_at ON public.memory_records;
CREATE TRIGGER memory_records_touch_updated_at
BEFORE UPDATE ON public.memory_records
FOR EACH ROW EXECUTE FUNCTION public.memory_touch_updated_at();
DROP TRIGGER IF EXISTS memory_outbox_touch_updated_at ON public.memory_outbox;
CREATE TRIGGER memory_outbox_touch_updated_at
BEFORE UPDATE ON public.memory_outbox
FOR EACH ROW EXECUTE FUNCTION public.memory_touch_updated_at();

CREATE OR REPLACE FUNCTION public.memory_reject_mutation()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='55000', MESSAGE=format('%I is append-only', TG_TABLE_NAME);
END;
$$;
ALTER FUNCTION public.memory_reject_mutation() OWNER TO CURRENT_USER;
REVOKE ALL PRIVILEGES ON FUNCTION public.memory_reject_mutation()
  FROM PUBLIC;

DROP TRIGGER IF EXISTS memory_receipts_append_only ON public.memory_receipts;
CREATE TRIGGER memory_receipts_append_only BEFORE UPDATE OR DELETE ON public.memory_receipts
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();
DROP TRIGGER IF EXISTS memory_query_audit_append_only ON public.memory_query_audit;
CREATE TRIGGER memory_query_audit_append_only BEFORE UPDATE OR DELETE ON public.memory_query_audit
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();
DROP TRIGGER IF EXISTS memory_idempotency_append_only ON public.memory_idempotency;
CREATE TRIGGER memory_idempotency_append_only BEFORE UPDATE OR DELETE ON public.memory_idempotency
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();

CREATE OR REPLACE FUNCTION public.a11oy_memory_context_matches(row_tenant text, row_domain text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
  SELECT row_tenant = current_setting('a11oy.tenant_id', true)
     AND row_domain = current_setting('a11oy.security_domain', true)
     AND EXISTS (
         SELECT 1
           FROM public.memory_context_bindings AS binding
          WHERE binding.principal_oid = (
                    SELECT role.oid
                      FROM pg_catalog.pg_roles AS role
                     WHERE role.rolname = session_user
                )
            AND binding.tenant_id = row_tenant
            AND binding.security_domain = row_domain
     )
$$;
ALTER FUNCTION public.a11oy_memory_context_matches(text, text)
  OWNER TO CURRENT_USER;
REVOKE ALL PRIVILEGES ON FUNCTION public.a11oy_memory_context_matches(text, text)
  FROM PUBLIC;

ALTER TABLE public.memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence_refs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_receipts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_query_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_query_audit FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_index_generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_index_generations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_idempotency FORCE ROW LEVEL SECURITY;

-- PostgreSQL OR-combines permissive policies. Remove every pre-existing policy,
-- including stale filters on the owner-only binding table, before installing
-- the single tenant/domain policy required on each application table.
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
               'memory_idempotency',
               'memory_context_bindings'
           )
    LOOP
        EXECUTE format(
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

COMMIT;
