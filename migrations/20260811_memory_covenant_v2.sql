-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant v0.1
-- PostgreSQL is authoritative. Derived indexes are rebuildable.

BEGIN;

CREATE TABLE IF NOT EXISTS memory_records (
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

CREATE TABLE IF NOT EXISTS memory_evidence_refs (
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
      REFERENCES memory_records (tenant_id, security_domain, memory_id)
      ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS memory_outbox (
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

CREATE TABLE IF NOT EXISTS memory_receipts (
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
    CHECK (namespace = tenant_id || ':' || security_domain),
    CHECK (receipt_json->>'receipt_id' = receipt_id),
    CHECK (receipt_json->'integrity'->>'digest' = digest)
);

CREATE TABLE IF NOT EXISTS memory_query_audit (
    audit_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    receipt_id text NOT NULL REFERENCES memory_receipts(receipt_id) ON DELETE RESTRICT,
    query_digest char(64) NOT NULL CHECK (query_digest ~ '^[0-9a-f]{64}$'),
    result_digest char(64) NOT NULL CHECK (result_digest ~ '^[0-9a-f]{64}$'),
    returned_ids text[] NOT NULL DEFAULT '{}',
    rejected_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(rejected_json) = 'object'),
    audit_json jsonb NOT NULL CHECK (jsonb_typeof(audit_json) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (audit_json->>'audit_id' = audit_id),
    CHECK (audit_json->>'query_digest' = query_digest),
    CHECK (audit_json->>'result_digest' = result_digest)
);

CREATE TABLE IF NOT EXISTS memory_index_generations (
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
  ON memory_index_generations (tenant_id, security_domain)
  WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS memory_idempotency (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    operation text NOT NULL,
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    response_json jsonb NOT NULL CHECK (jsonb_typeof(response_json) = 'object'),
    receipt_id text NOT NULL REFERENCES memory_receipts(receipt_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, security_domain, operation, idempotency_key)
);

CREATE INDEX IF NOT EXISTS memory_records_searchable_idx
  ON memory_records (tenant_id, security_domain, active_index_generation, memory_id)
  WHERE lifecycle_state IN ('ACTIVE','INDEXED');
CREATE INDEX IF NOT EXISTS memory_records_expiry_idx
  ON memory_records (expires_at)
  WHERE expires_at IS NOT NULL AND lifecycle_state NOT IN ('EXPIRED','TOMBSTONED');
CREATE INDEX IF NOT EXISTS memory_outbox_ready_idx
  ON memory_outbox (available_at, event_id)
  WHERE status IN ('PENDING','RETRY','LEASED');
CREATE INDEX IF NOT EXISTS memory_receipts_namespace_idx
  ON memory_receipts (tenant_id, security_domain, seq);
CREATE INDEX IF NOT EXISTS memory_query_audit_time_idx
  ON memory_query_audit (tenant_id, security_domain, created_at DESC);

CREATE OR REPLACE FUNCTION memory_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS memory_records_touch_updated_at ON memory_records;
CREATE TRIGGER memory_records_touch_updated_at
BEFORE UPDATE ON memory_records
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();
DROP TRIGGER IF EXISTS memory_outbox_touch_updated_at ON memory_outbox;
CREATE TRIGGER memory_outbox_touch_updated_at
BEFORE UPDATE ON memory_outbox
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

CREATE OR REPLACE FUNCTION memory_reject_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='55000', MESSAGE=format('%I is append-only', TG_TABLE_NAME);
END;
$$;

DROP TRIGGER IF EXISTS memory_receipts_append_only ON memory_receipts;
CREATE TRIGGER memory_receipts_append_only BEFORE UPDATE OR DELETE ON memory_receipts
FOR EACH ROW EXECUTE FUNCTION memory_reject_mutation();
DROP TRIGGER IF EXISTS memory_query_audit_append_only ON memory_query_audit;
CREATE TRIGGER memory_query_audit_append_only BEFORE UPDATE OR DELETE ON memory_query_audit
FOR EACH ROW EXECUTE FUNCTION memory_reject_mutation();
DROP TRIGGER IF EXISTS memory_idempotency_append_only ON memory_idempotency;
CREATE TRIGGER memory_idempotency_append_only BEFORE UPDATE OR DELETE ON memory_idempotency
FOR EACH ROW EXECUTE FUNCTION memory_reject_mutation();

CREATE OR REPLACE FUNCTION a11oy_memory_context_matches(row_tenant text, row_domain text)
RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT row_tenant = current_setting('a11oy.tenant_id', true)
     AND row_domain = current_setting('a11oy.security_domain', true)
$$;

ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_records FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_evidence_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_evidence_refs FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_receipts FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_query_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_query_audit FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_index_generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_index_generations FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_idempotency FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_records_isolation ON memory_records;
CREATE POLICY memory_records_isolation ON memory_records
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_evidence_refs_isolation ON memory_evidence_refs;
CREATE POLICY memory_evidence_refs_isolation ON memory_evidence_refs
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_outbox_isolation ON memory_outbox;
CREATE POLICY memory_outbox_isolation ON memory_outbox
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_receipts_isolation ON memory_receipts;
CREATE POLICY memory_receipts_isolation ON memory_receipts
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_query_audit_isolation ON memory_query_audit;
CREATE POLICY memory_query_audit_isolation ON memory_query_audit
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_index_generations_isolation ON memory_index_generations;
CREATE POLICY memory_index_generations_isolation ON memory_index_generations
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));
DROP POLICY IF EXISTS memory_idempotency_isolation ON memory_idempotency;
CREATE POLICY memory_idempotency_isolation ON memory_idempotency
USING (a11oy_memory_context_matches(tenant_id, security_domain))
WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));

COMMIT;
