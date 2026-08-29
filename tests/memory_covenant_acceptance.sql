\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    major_version integer := current_setting('server_version_num')::integer / 10000;
BEGIN
    IF major_version <> 18 THEN
        RAISE EXCEPTION 'Memory Covenant acceptance requires PostgreSQL 18, observed %',
            current_setting('server_version');
    END IF;
END;
$$;

DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'memory_context_bindings',
        'memory_evidence_refs',
        'memory_idempotency',
        'memory_index_generations',
        'memory_outbox',
        'memory_query_audit',
        'memory_receipts',
        'memory_records'
    ];
    observed_tables text[];
BEGIN
    SELECT array_agg(c.relname ORDER BY c.relname)
      INTO observed_tables
      FROM pg_class AS c
      JOIN pg_namespace AS n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND c.relname = ANY(expected_tables);
    IF observed_tables IS DISTINCT FROM expected_tables THEN
        RAISE EXCEPTION 'Memory Covenant table set mismatch: expected %, observed %',
            expected_tables, observed_tables;
    END IF;
END;
$$;

DO $$
DECLARE
    expected_owner oid := (
        SELECT relowner
          FROM pg_class
         WHERE oid = 'public.memory_context_bindings'::regclass
    );
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency',
               'memory_context_bindings'
           )
           AND relation.relowner IS DISTINCT FROM expected_owner
    ) THEN
        RAISE EXCEPTION 'Covenant relation ownership did not converge';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_proc AS procedure
         WHERE procedure.oid IN (
                   'memory_touch_updated_at()'::regprocedure,
                   'memory_reject_mutation()'::regprocedure,
                   'a11oy_memory_context_matches(text,text)'::regprocedure,
                   'memory_lease_outbox(text,integer,integer)'::regprocedure
               )
           AND procedure.proowner IS DISTINCT FROM expected_owner
    ) THEN
        RAISE EXCEPTION 'Covenant function ownership did not converge';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'a11oy_memory_stale_owner'
           AND oid = expected_owner
    ) THEN
        RAISE EXCEPTION 'Seeded stale owner retained the covenant boundary';
    END IF;
END;
$$;

DO $$
DECLARE
    expected_triggers text[] := ARRAY[
        'memory_idempotency.memory_idempotency_append_only',
        'memory_outbox.memory_outbox_touch_updated_at',
        'memory_query_audit.memory_query_audit_append_only',
        'memory_receipts.memory_receipts_append_only',
        'memory_records.memory_records_touch_updated_at'
    ];
    observed_triggers text[];
BEGIN
    SELECT pg_catalog.array_agg(
               relation.relname || '.' || trigger.tgname
               ORDER BY relation.relname, trigger.tgname
           )
      INTO observed_triggers
      FROM pg_catalog.pg_trigger AS trigger
      JOIN pg_catalog.pg_class AS relation
        ON relation.oid = trigger.tgrelid
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'public'
       AND relation.relname LIKE 'memory_%'
       AND NOT trigger.tgisinternal;
    IF observed_triggers IS DISTINCT FROM expected_triggers THEN
        RAISE EXCEPTION
          'Memory Covenant trigger set mismatch: expected %, observed %',
          expected_triggers,
          observed_triggers;
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_rewrite AS rewrite
          JOIN pg_class AS relation ON relation.oid = rewrite.ev_class
          JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency',
               'memory_context_bindings'
           )
           AND rewrite.rulename <> '_RETURN'
    ) THEN
        RAISE EXCEPTION 'Memory Covenant relation retained a user rewrite rule';
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (
               rolsuper
               OR rolcreatedb
               OR rolcreaterole
               OR rolreplication
               OR NOT rolinherit
               OR rolbypassrls
               OR rolcanlogin
           )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant roles retain a privileged role attribute';
    END IF;
    IF (
        SELECT count(*)
          FROM pg_roles
         WHERE rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    ) <> 2 THEN
        RAISE EXCEPTION 'Memory Covenant roles are missing';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.member IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability role retained an inherited parent';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.roleid IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
           AND edge.admin_option
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability membership retained ADMIN OPTION';
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
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
           AND NOT c.relrowsecurity
    ) THEN
        RAISE EXCEPTION 'Every Memory Covenant table must have RLS enabled';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency'
           )
           AND NOT c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'Tenant-scoped Memory Covenant tables must FORCE RLS';
    END IF;

    IF (
        SELECT c.relforcerowsecurity
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname = 'memory_outbox'
    ) THEN
        RAISE EXCEPTION 'memory_outbox must remain NO FORCE RLS for bounded definer leasing';
    END IF;

    IF (
        SELECT c.relforcerowsecurity
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = 'memory_context_bindings'
    ) THEN
        RAISE EXCEPTION 'memory_context_bindings must remain NO FORCE RLS for owner-unfiltered provenance checks';
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT c.relname
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
          LEFT JOIN pg_policy AS p ON p.polrelid = c.oid
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
         GROUP BY c.relname
        HAVING count(p.polname) <> 1
            OR min(p.polname) <> c.relname || '_isolation'
    ) THEN
        RAISE EXCEPTION 'Every Memory Covenant table must have exactly its single isolation policy';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_policy AS p
         WHERE p.polrelid = 'public.memory_context_bindings'::regclass
    ) THEN
        RAISE EXCEPTION 'memory_context_bindings retained a stale RLS policy';
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'memory_attacker'
           AND c.relname LIKE 'memory_%'
    ) THEN
        RAISE EXCEPTION 'Memory Covenant objects followed a caller-controlled current schema';
    END IF;
END;
$$;

DO $$
DECLARE
    receipt_key_definition text;
    audit_fk_definition text;
    idempotency_fk_definition text;
BEGIN
    SELECT pg_get_constraintdef(oid, true)
      INTO receipt_key_definition
      FROM pg_constraint
     WHERE conrelid = 'public.memory_receipts'::regclass
       AND conname = 'memory_receipts_tenant_domain_receipt_key';
    SELECT pg_get_constraintdef(oid, true)
      INTO audit_fk_definition
      FROM pg_constraint
     WHERE conrelid = 'public.memory_query_audit'::regclass
       AND conname = 'memory_query_audit_tenant_domain_receipt_fkey';
    SELECT pg_get_constraintdef(oid, true)
      INTO idempotency_fk_definition
      FROM pg_constraint
     WHERE conrelid = 'public.memory_idempotency'::regclass
       AND conname = 'memory_idempotency_tenant_domain_receipt_fkey';

    IF receipt_key_definition IS DISTINCT FROM
       'UNIQUE (tenant_id, security_domain, receipt_id)' THEN
        RAISE EXCEPTION 'tenant/domain receipt key mismatch: %', receipt_key_definition;
    END IF;
    IF audit_fk_definition IS DISTINCT FROM
       'FOREIGN KEY (tenant_id, security_domain, receipt_id) REFERENCES memory_receipts(tenant_id, security_domain, receipt_id) ON DELETE RESTRICT' THEN
        RAISE EXCEPTION 'audit receipt relationship is not tenant/domain-bound: %', audit_fk_definition;
    END IF;
    IF idempotency_fk_definition IS DISTINCT FROM
       'FOREIGN KEY (tenant_id, security_domain, receipt_id) REFERENCES memory_receipts(tenant_id, security_domain, receipt_id) ON DELETE RESTRICT' THEN
        RAISE EXCEPTION 'idempotency receipt relationship is not tenant/domain-bound: %', idempotency_fk_definition;
    END IF;
    IF (
        SELECT count(*)
          FROM pg_constraint
         WHERE contype = 'f'
           AND confrelid = 'public.memory_receipts'::regclass
           AND conrelid IN (
               'public.memory_query_audit'::regclass,
               'public.memory_idempotency'::regclass
           )
    ) <> 2 THEN
        RAISE EXCEPTION 'stale receipt relationships remain';
    END IF;
END;
$$;

DO $$
DECLARE
    privilege_diff text;
BEGIN
    WITH expected(table_name, privilege_type) AS (
        VALUES
            ('memory_records', 'SELECT'),
            ('memory_records', 'INSERT'),
            ('memory_records', 'UPDATE'),
            ('memory_evidence_refs', 'SELECT'),
            ('memory_evidence_refs', 'INSERT'),
            ('memory_evidence_refs', 'DELETE'),
            ('memory_outbox', 'SELECT'),
            ('memory_outbox', 'INSERT'),
            ('memory_receipts', 'SELECT'),
            ('memory_receipts', 'INSERT'),
            ('memory_query_audit', 'SELECT'),
            ('memory_query_audit', 'INSERT'),
            ('memory_index_generations', 'SELECT'),
            ('memory_index_generations', 'INSERT'),
            ('memory_index_generations', 'UPDATE'),
            ('memory_idempotency', 'SELECT'),
            ('memory_idempotency', 'INSERT')
    ), observed AS (
        SELECT table_name, privilege_type
          FROM information_schema.role_table_grants
         WHERE grantee = 'a11oy_memory_app'
           AND table_schema = 'public'
           AND table_name LIKE 'memory_%'
    ), delta AS (
        (SELECT * FROM expected EXCEPT SELECT * FROM observed)
        UNION ALL
        (SELECT * FROM observed EXCEPT SELECT * FROM expected)
    )
    SELECT string_agg(table_name || ':' || privilege_type, ', ' ORDER BY table_name, privilege_type)
      INTO privilege_diff
      FROM delta;
    IF privilege_diff IS NOT NULL THEN
        RAISE EXCEPTION 'a11oy_memory_app privilege mismatch: %', privilege_diff;
    END IF;

    IF NOT has_schema_privilege('a11oy_memory_app', 'public', 'USAGE') THEN
        RAISE EXCEPTION 'a11oy_memory_app lacks public schema USAGE';
    END IF;
    IF NOT has_schema_privilege('a11oy_memory_worker', 'public', 'USAGE') THEN
        RAISE EXCEPTION 'a11oy_memory_worker lacks public schema USAGE';
    END IF;
    IF has_schema_privilege('a11oy_memory_app', 'public', 'CREATE')
       OR has_schema_privilege('a11oy_memory_worker', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Memory Covenant capability role retained schema CREATE';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_namespace AS namespace,
               LATERAL aclexplode(
                   COALESCE(namespace.nspacl, acldefault('n', namespace.nspowner))
               ) AS acl
         WHERE namespace.nspname = 'public'
           AND acl.privilege_type = 'CREATE'
           AND acl.grantee <> namespace.nspowner
    ) THEN
        RAISE EXCEPTION 'A non-owner retained public-schema CREATE';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.role_table_grants
         WHERE grantee = 'a11oy_memory_worker'
           AND table_schema = 'public'
           AND table_name LIKE 'memory_%'
    ) THEN
        RAISE EXCEPTION 'a11oy_memory_worker must not have direct memory-table privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.role_table_grants
         WHERE grantee = 'PUBLIC'
           AND table_schema = 'public'
           AND table_name LIKE 'memory_%'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not have memory-table privileges';
    END IF;

    IF has_table_privilege(
        'a11oy_memory_app',
        'public.memory_context_bindings',
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
    ) OR has_table_privilege(
        'a11oy_memory_worker',
        'public.memory_context_bindings',
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
    ) THEN
        RAISE EXCEPTION 'Capability role can mutate owner-only context bindings';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace,
               LATERAL aclexplode(
                   COALESCE(relation.relacl, acldefault('r', relation.relowner))
               ) AS acl
         WHERE namespace.nspname = 'public'
           AND relation.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency',
               'memory_context_bindings'
           )
           AND acl.grantee <> relation.relowner
           AND acl.grantee <> 'a11oy_memory_app'::regrole
    ) THEN
        RAISE EXCEPTION 'A stale non-owner covenant table ACL remains';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
          JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid,
               LATERAL aclexplode(attribute.attacl) AS acl
         WHERE namespace.nspname = 'public'
           AND relation.relname IN (
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency',
               'memory_context_bindings'
           )
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
           AND attribute.attacl IS NOT NULL
           AND acl.grantee <> relation.relowner
    ) THEN
        RAISE EXCEPTION 'A stale non-owner covenant column ACL remains';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'a11oy_memory_stale_grantee'
    ) THEN
        -- PostgreSQL 16+ pg_has_role(..., 'MEMBER') means SET ROLE, not the
        -- membership row. Delegated members keep the row with INHERIT/SET false.
        IF (
            SELECT count(*)
              FROM pg_auth_members AS edge
             WHERE edge.roleid IN (
                 'a11oy_memory_app'::regrole,
                 'a11oy_memory_worker'::regrole
             )
               AND edge.member = 'a11oy_memory_stale_grantee'::regrole
               AND NOT edge.admin_option
        ) <> 2 THEN
            RAISE EXCEPTION 'Seeded inbound capability membership was not preserved';
        END IF;
    END IF;
END;
$$;

DO $$
DECLARE
    lease_oid oid := 'memory_lease_outbox(text,integer,integer)'::regprocedure;
    is_security_definer boolean;
    function_config text[];
BEGIN
    SELECT prosecdef, proconfig
      INTO is_security_definer, function_config
      FROM pg_proc
     WHERE oid = lease_oid;
    IF NOT is_security_definer THEN
        RAISE EXCEPTION 'memory_lease_outbox must be SECURITY DEFINER';
    END IF;
    IF function_config IS NULL OR NOT ('search_path=pg_catalog, pg_temp' = ANY(function_config)) THEN
        RAISE EXCEPTION 'memory_lease_outbox must pin search_path to pg_catalog, pg_temp';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_proc AS p,
               LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) AS acl
         WHERE p.oid = lease_oid
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not execute memory_lease_outbox';
    END IF;
    IF NOT has_function_privilege(
        'a11oy_memory_worker',
        'memory_lease_outbox(text,integer,integer)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'worker role lacks bounded lease function EXECUTE';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_proc AS p,
               LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) AS acl
         WHERE p.oid = lease_oid
           AND acl.grantee <> p.proowner
           AND (
               acl.grantee <> 'a11oy_memory_worker'::regrole
               OR acl.privilege_type <> 'EXECUTE'
               OR acl.is_grantable
           )
    ) THEN
        RAISE EXCEPTION 'stale non-owner lease function ACL remains';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'a11oy_memory_stale_grantee'
    ) THEN
        IF has_function_privilege(
            'a11oy_memory_stale_grantee',
            'memory_lease_outbox(text,integer,integer)',
            'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'seeded stale lease grantee retained EXECUTE';
        END IF;
    END IF;
END;
$$;

DO $$
DECLARE
    context_oid oid := 'a11oy_memory_context_matches(text,text)'::regprocedure;
    is_security_definer boolean;
    function_config text[];
BEGIN
    SELECT prosecdef, proconfig
      INTO is_security_definer, function_config
      FROM pg_proc
     WHERE oid = context_oid;
    IF NOT is_security_definer THEN
        RAISE EXCEPTION 'a11oy_memory_context_matches must be SECURITY DEFINER';
    END IF;
    IF function_config IS NULL OR NOT ('search_path=pg_catalog, pg_temp' = ANY(function_config)) THEN
        RAISE EXCEPTION 'a11oy_memory_context_matches must pin search_path to pg_catalog, pg_temp';
    END IF;
    IF NOT has_function_privilege(
        'a11oy_memory_app',
        'a11oy_memory_context_matches(text,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'application role lacks bound context-function EXECUTE';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_proc AS procedure,
               LATERAL aclexplode(
                   COALESCE(procedure.proacl, acldefault('f', procedure.proowner))
               ) AS acl
         WHERE procedure.oid IN (
                   'memory_touch_updated_at()'::regprocedure,
                   'memory_reject_mutation()'::regprocedure,
                   context_oid,
                   'memory_lease_outbox(text,integer,integer)'::regprocedure
               )
           AND acl.grantee <> procedure.proowner
           AND NOT (
               procedure.oid = context_oid
               AND acl.grantee = 'a11oy_memory_app'::regrole
               AND acl.privilege_type = 'EXECUTE'
               AND NOT acl.is_grantable
           )
           AND NOT (
               procedure.oid = 'memory_lease_outbox(text,integer,integer)'::regprocedure
               AND acl.grantee = 'a11oy_memory_worker'::regrole
               AND acl.privilege_type = 'EXECUTE'
               AND NOT acl.is_grantable
           )
    ) THEN
        RAISE EXCEPTION 'A stale non-owner covenant function ACL remains';
    END IF;
END;
$$;

CREATE ROLE a11oy_memory_acceptance_app
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
  NOREPLICATION INHERIT NOBYPASSRLS;
CREATE ROLE a11oy_memory_acceptance_worker
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
  NOREPLICATION INHERIT NOBYPASSRLS;
GRANT a11oy_memory_app TO a11oy_memory_acceptance_app;
GRANT a11oy_memory_worker TO a11oy_memory_acceptance_worker;
INSERT INTO memory_context_bindings (
    principal_oid,
    tenant_id,
    security_domain
) VALUES (
    'a11oy_memory_acceptance_app'::regrole,
    'acceptance-tenant-a',
    'acceptance-domain-a'
);

SET SESSION AUTHORIZATION a11oy_memory_acceptance_app;
SELECT set_config('a11oy.tenant_id', 'acceptance-tenant-a', true);
SELECT set_config('a11oy.security_domain', 'acceptance-domain-a', true);

INSERT INTO memory_records (
    tenant_id,
    security_domain,
    memory_id,
    schema_version,
    memory_class,
    compatibility_type,
    classification,
    lifecycle_state,
    active_index_generation,
    content_sha256,
    record_sha256,
    record_json
) VALUES (
    'acceptance-tenant-a',
    'acceptance-domain-a',
    'acceptance-memory-20260820',
    'szl-memory/2.0',
    'evidence',
    'EPISODIC',
    'INTERNAL',
    'ACTIVE',
    'acceptance-generation',
    repeat('a', 64),
    repeat('b', 64),
    jsonb_build_object(
        'tenant_id', 'acceptance-tenant-a',
        'security_domain', 'acceptance-domain-a',
        'memory_id', 'acceptance-memory-20260820',
        'schema_version', 'szl-memory/2.0'
    )
);

DO $$
DECLARE
    visible integer;
BEGIN
    SELECT count(*) INTO visible
      FROM memory_records
     WHERE memory_id = 'acceptance-memory-20260820';
    IF visible <> 1 THEN
        RAISE EXCEPTION 'same-domain visibility expected 1, observed %', visible;
    END IF;
END;
$$;

SELECT set_config('a11oy.security_domain', 'acceptance-domain-b', true);

DO $$
DECLARE
    visible integer;
    rejected boolean := false;
    impersonation_rejected boolean := false;
BEGIN
    SELECT count(*) INTO visible
      FROM memory_records
     WHERE memory_id = 'acceptance-memory-20260820';
    IF visible <> 0 THEN
        RAISE EXCEPTION 'cross-domain visibility expected 0, observed %', visible;
    END IF;

    BEGIN
        INSERT INTO memory_records (
            tenant_id,
            security_domain,
            memory_id,
            schema_version,
            memory_class,
            compatibility_type,
            classification,
            lifecycle_state,
            active_index_generation,
            content_sha256,
            record_sha256,
            record_json
        ) VALUES (
            'acceptance-tenant-a',
            'acceptance-domain-a',
            'acceptance-cross-domain-denied',
            'szl-memory/2.0',
            'evidence',
            'EPISODIC',
            'INTERNAL',
            'ACTIVE',
            'acceptance-generation',
            repeat('c', 64),
            repeat('d', 64),
            jsonb_build_object(
                'tenant_id', 'acceptance-tenant-a',
                'security_domain', 'acceptance-domain-a',
                'memory_id', 'acceptance-cross-domain-denied',
                'schema_version', 'szl-memory/2.0'
            )
        );
    EXCEPTION
        WHEN insufficient_privilege THEN
            rejected := true;
    END;
    IF NOT rejected THEN
        RAISE EXCEPTION 'cross-domain insert was not rejected';
    END IF;

    BEGIN
        INSERT INTO memory_records (
            tenant_id,
            security_domain,
            memory_id,
            schema_version,
            memory_class,
            compatibility_type,
            classification,
            lifecycle_state,
            active_index_generation,
            content_sha256,
            record_sha256,
            record_json
        ) VALUES (
            'acceptance-tenant-a',
            'acceptance-domain-b',
            'acceptance-unbound-context-denied',
            'szl-memory/2.0',
            'evidence',
            'EPISODIC',
            'INTERNAL',
            'ACTIVE',
            'acceptance-generation',
            repeat('8', 64),
            repeat('9', 64),
            jsonb_build_object(
                'tenant_id', 'acceptance-tenant-a',
                'security_domain', 'acceptance-domain-b',
                'memory_id', 'acceptance-unbound-context-denied',
                'schema_version', 'szl-memory/2.0'
            )
        );
    EXCEPTION
        WHEN insufficient_privilege THEN
            impersonation_rejected := true;
    END;
    IF NOT impersonation_rejected THEN
        RAISE EXCEPTION 'user-settable custom GUC impersonated an unbound domain';
    END IF;
END;
$$;

SET SESSION AUTHORIZATION postgres;

INSERT INTO memory_receipts (
    receipt_id,
    tenant_id,
    security_domain,
    namespace,
    seq,
    prev_digest,
    digest,
    mode,
    operation,
    decision,
    request_digest,
    receipt_json
) VALUES (
    'acceptance-receipt-20260820',
    'acceptance-tenant-a',
    'acceptance-domain-a',
    'acceptance-tenant-a:acceptance-domain-a',
    9223372036854770000,
    repeat('0', 64),
    repeat('e', 64),
    'UNSIGNED-CONTENT-DIGEST',
    'acceptance',
    'ALLOW',
    repeat('f', 64),
    jsonb_build_object(
        'receipt_id', 'acceptance-receipt-20260820',
        'integrity', jsonb_build_object('digest', repeat('e', 64))
    )
);

DO $$
DECLARE
    update_rejected boolean := false;
    delete_rejected boolean := false;
BEGIN
    BEGIN
        UPDATE memory_receipts
           SET operation = 'tampered'
         WHERE receipt_id = 'acceptance-receipt-20260820';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            update_rejected := true;
    END;
    BEGIN
        DELETE FROM memory_receipts
         WHERE receipt_id = 'acceptance-receipt-20260820';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            delete_rejected := true;
    END;
    IF NOT update_rejected OR NOT delete_rejected THEN
        RAISE EXCEPTION 'append-only receipt mutation was not rejected with SQLSTATE 55000';
    END IF;
END;
$$;

INSERT INTO memory_query_audit (
    audit_id,
    tenant_id,
    security_domain,
    receipt_id,
    query_digest,
    result_digest,
    audit_json
) VALUES (
    'acceptance-append-only-audit',
    'acceptance-tenant-a',
    'acceptance-domain-a',
    'acceptance-receipt-20260820',
    repeat('1', 64),
    repeat('2', 64),
    jsonb_build_object(
        'audit_id', 'acceptance-append-only-audit',
        'query_digest', repeat('1', 64),
        'result_digest', repeat('2', 64)
    )
);

INSERT INTO memory_idempotency (
    tenant_id,
    security_domain,
    operation,
    idempotency_key,
    request_digest,
    response_json,
    receipt_id
) VALUES (
    'acceptance-tenant-a',
    'acceptance-domain-a',
    'acceptance',
    'append-only-idempotency',
    repeat('3', 64),
    '{}'::jsonb,
    'acceptance-receipt-20260820'
);

DO $$
DECLARE
    audit_update_rejected boolean := false;
    audit_delete_rejected boolean := false;
    idempotency_update_rejected boolean := false;
    idempotency_delete_rejected boolean := false;
BEGIN
    BEGIN
        UPDATE memory_query_audit
           SET result_digest = repeat('4', 64)
         WHERE audit_id = 'acceptance-append-only-audit';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            audit_update_rejected := true;
    END;
    BEGIN
        DELETE FROM memory_query_audit
         WHERE audit_id = 'acceptance-append-only-audit';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            audit_delete_rejected := true;
    END;
    BEGIN
        UPDATE memory_idempotency
           SET response_json = '{"tampered":true}'::jsonb
         WHERE tenant_id = 'acceptance-tenant-a'
           AND security_domain = 'acceptance-domain-a'
           AND operation = 'acceptance'
           AND idempotency_key = 'append-only-idempotency';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            idempotency_update_rejected := true;
    END;
    BEGIN
        DELETE FROM memory_idempotency
         WHERE tenant_id = 'acceptance-tenant-a'
           AND security_domain = 'acceptance-domain-a'
           AND operation = 'acceptance'
           AND idempotency_key = 'append-only-idempotency';
    EXCEPTION
        WHEN SQLSTATE '55000' THEN
            idempotency_delete_rejected := true;
    END;
    IF NOT audit_update_rejected
       OR NOT audit_delete_rejected
       OR NOT idempotency_update_rejected
       OR NOT idempotency_delete_rejected THEN
        RAISE EXCEPTION
          'append-only audit/idempotency mutation was not rejected with SQLSTATE 55000';
    END IF;
END;
$$;

DO $$
DECLARE
    audit_rejected boolean := false;
    idempotency_rejected boolean := false;
BEGIN
    BEGIN
        INSERT INTO memory_query_audit (
            audit_id,
            tenant_id,
            security_domain,
            receipt_id,
            query_digest,
            result_digest,
            audit_json
        ) VALUES (
            'acceptance-cross-domain-audit',
            'acceptance-tenant-a',
            'acceptance-domain-b',
            'acceptance-receipt-20260820',
            repeat('1', 64),
            repeat('2', 64),
            jsonb_build_object(
                'audit_id', 'acceptance-cross-domain-audit',
                'query_digest', repeat('1', 64),
                'result_digest', repeat('2', 64)
            )
        );
    EXCEPTION
        WHEN foreign_key_violation THEN
            audit_rejected := true;
    END;

    BEGIN
        INSERT INTO memory_idempotency (
            tenant_id,
            security_domain,
            operation,
            idempotency_key,
            request_digest,
            response_json,
            receipt_id
        ) VALUES (
            'acceptance-tenant-a',
            'acceptance-domain-b',
            'acceptance',
            'cross-domain-receipt',
            repeat('3', 64),
            '{}'::jsonb,
            'acceptance-receipt-20260820'
        );
    EXCEPTION
        WHEN foreign_key_violation THEN
            idempotency_rejected := true;
    END;

    IF NOT audit_rejected OR NOT idempotency_rejected THEN
        RAISE EXCEPTION 'cross-domain receipt relationship was not rejected';
    END IF;
END;
$$;

SET SESSION AUTHORIZATION a11oy_memory_acceptance_app;
SELECT set_config('a11oy.tenant_id', 'acceptance-tenant-a', true);
SELECT set_config('a11oy.security_domain', 'acceptance-domain-a', true);

INSERT INTO memory_outbox (
    event_id,
    tenant_id,
    security_domain,
    memory_id,
    generation_id,
    event_type,
    payload_json
) VALUES (
    'acceptance-event-20260820',
    'acceptance-tenant-a',
    'acceptance-domain-a',
    'acceptance-memory-20260820',
    'acceptance-generation',
    'INDEX_UPSERT',
    '{}'::jsonb
);

SET SESSION AUTHORIZATION postgres;
SET SESSION AUTHORIZATION a11oy_memory_acceptance_worker;

DO $$
DECLARE
    leased memory_outbox;
    invalid_limit_rejected boolean := false;
    null_limit_rejected boolean := false;
    null_duration_rejected boolean := false;
BEGIN
    SELECT * INTO leased
      FROM memory_lease_outbox('acceptance-worker', 1, 30)
     WHERE event_id = 'acceptance-event-20260820';
    IF leased.event_id IS NULL
       OR leased.status <> 'LEASED'
       OR leased.lease_owner <> 'acceptance-worker'
       OR leased.attempts <> 1
       OR leased.lease_expires_at IS NULL THEN
        RAISE EXCEPTION 'bounded worker lease failed: %', row_to_json(leased);
    END IF;

    BEGIN
        PERFORM * FROM memory_lease_outbox('acceptance-worker', 0, 30);
    EXCEPTION
        WHEN SQLSTATE '22023' THEN
            invalid_limit_rejected := true;
    END;
    IF NOT invalid_limit_rejected THEN
        RAISE EXCEPTION 'invalid worker limit was not rejected with SQLSTATE 22023';
    END IF;

    BEGIN
        PERFORM * FROM memory_lease_outbox('acceptance-worker', NULL, 30);
    EXCEPTION
        WHEN SQLSTATE '22023' THEN
            null_limit_rejected := true;
    END;
    IF NOT null_limit_rejected THEN
        RAISE EXCEPTION 'NULL worker limit was not rejected with SQLSTATE 22023';
    END IF;

    BEGIN
        PERFORM * FROM memory_lease_outbox('acceptance-worker', 1, NULL);
    EXCEPTION
        WHEN SQLSTATE '22023' THEN
            null_duration_rejected := true;
    END;
    IF NOT null_duration_rejected THEN
        RAISE EXCEPTION 'NULL lease duration was not rejected with SQLSTATE 22023';
    END IF;
END;
$$;

SET SESSION AUTHORIZATION postgres;
ROLLBACK;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM memory_records WHERE memory_id LIKE 'acceptance-%'
    ) OR EXISTS (
        SELECT 1 FROM memory_receipts WHERE receipt_id = 'acceptance-receipt-20260820'
    ) OR EXISTS (
        SELECT 1 FROM memory_outbox WHERE event_id = 'acceptance-event-20260820'
    ) OR EXISTS (
        SELECT 1 FROM memory_context_bindings
         WHERE tenant_id = 'acceptance-tenant-a'
    ) OR EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname IN (
             'a11oy_memory_acceptance_app',
             'a11oy_memory_acceptance_worker'
         )
    ) THEN
        RAISE EXCEPTION 'rollback-only acceptance left persistent state';
    END IF;
END;
$$;

SELECT jsonb_build_object(
    'status', 'PASS',
    'server_version', current_setting('server_version'),
    'table_count', (
        SELECT count(*)
          FROM pg_class AS c
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'memory_context_bindings',
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency'
           )
    ),
    'policy_count', (
        SELECT count(*)
          FROM pg_policy AS p
          JOIN pg_class AS c ON c.oid = p.polrelid
          JOIN pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname LIKE 'memory_%'
    ),
    'rollback_residue', jsonb_build_object(
        'memory_rows', (SELECT count(*) FROM memory_records WHERE memory_id LIKE 'acceptance-%'),
        'receipt_rows', (SELECT count(*) FROM memory_receipts WHERE receipt_id = 'acceptance-receipt-20260820'),
        'outbox_rows', (SELECT count(*) FROM memory_outbox WHERE event_id = 'acceptance-event-20260820'),
        'context_binding_rows', (
            SELECT count(*) FROM memory_context_bindings
             WHERE tenant_id = 'acceptance-tenant-a'
        )
    )
) AS memory_covenant_acceptance;
