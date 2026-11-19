-- SPDX-License-Identifier: Apache-2.0
-- Forward-only corrective migration for Memory Covenant v2 installations.
-- Apply after both 20260811 migrations. This source migration does not claim
-- that any production database has been altered.

BEGIN;

SET LOCAL search_path = pg_catalog, pg_temp;

-- The migration principal must see every existing row and own schema public.
-- Without the first, the preflights and foreign-key validation in this chain
-- run under FORCE RLS with every policy stripped, see no rows and pass. Without
-- the second, PostgreSQL reduces the schema privilege sweep to warnings. A
-- provider-managed owner needs row-security bypass and database ownership.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS principal
         WHERE principal.rolname = CURRENT_USER
           AND (principal.rolsuper OR principal.rolbypassrls)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'the migration principal must bypass row security to check existing rows';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS principal
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.nspname = 'public'
         WHERE principal.rolname = CURRENT_USER
           AND (principal.rolsuper
                OR pg_catalog.pg_has_role(CURRENT_USER, namespace.nspowner, 'USAGE'))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'the migration principal must own schema public';
    END IF;
END;
$$;

-- Existing installations need an owner-only source of truth tying the real
-- session principal to the tenant/domain values presented through custom GUCs.
-- Without this binding, any application-role member can select another tenant
-- merely by changing those user-settable values.
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

-- No historical release stored durable row-level write provenance for this
-- authorization table. Current owners, ACLs, and helper source cannot prove
-- that a binding predates a revoked temporary INSERT grant. Refuse every
-- nonempty reapplication until an operator reconciles and reprovisions the
-- bindings through a future provenance-bearing path.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN
        RAISE EXCEPTION USING
          ERRCODE = '23514',
          MESSAGE = 'pre-existing memory_context_bindings rows lack durable write provenance';
    END IF;
END;
$$;

ALTER TABLE public.memory_records OWNER TO CURRENT_USER;
ALTER TABLE public.memory_evidence_refs OWNER TO CURRENT_USER;
ALTER TABLE public.memory_outbox OWNER TO CURRENT_USER;
ALTER TABLE public.memory_receipts OWNER TO CURRENT_USER;
ALTER TABLE public.memory_query_audit OWNER TO CURRENT_USER;
ALTER TABLE public.memory_index_generations OWNER TO CURRENT_USER;
ALTER TABLE public.memory_idempotency OWNER TO CURRENT_USER;

-- A stale RLS policy is executable SQL. Strip every policy immediately after
-- ownership convergence and before any application-table query or FORCE-RLS
-- transition. This prevents an attacker-controlled SECURITY INVOKER policy
-- expression from running with the trusted migration principal's privileges.
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT relation.relname AS table_name, policy.polname AS policy_name
          FROM pg_catalog.pg_policy AS policy
          JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
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
    LOOP
        EXECUTE pg_catalog.format(
            'DROP POLICY %I ON public.%I',
            policy_row.policy_name,
            policy_row.table_name
        );
    END LOOP;
END;
$$;

-- Rewrite rules can discard or redirect writes before trigger enforcement.
-- Covenant relations are tables, so they have no required _RETURN rule; keep
-- that catalog-reserved identity fail-closed while removing every user rule.
DO $$
DECLARE
    rewrite_row record;
BEGIN
    FOR rewrite_row IN
        SELECT relation.relname AS table_name, rewrite.rulename AS rule_name
          FROM pg_catalog.pg_rewrite AS rewrite
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = rewrite.ev_class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
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
    LOOP
        EXECUTE pg_catalog.format(
            'DROP RULE %I ON public.%I',
            rewrite_row.rule_name,
            rewrite_row.table_name
        );
    END LOOP;
END;
$$;

-- A stale function owner can replace either trigger helper while retaining the
-- same function identity. Restore both bodies before transferring ownership,
-- then rebuild every non-internal covenant trigger from a known-empty set.
CREATE OR REPLACE FUNCTION public.memory_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.memory_reject_mutation()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='55000', MESSAGE=format('%I is append-only', TG_TABLE_NAME);
END;
$$;

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
ALTER FUNCTION public.memory_touch_updated_at() OWNER TO CURRENT_USER;
ALTER FUNCTION public.memory_reject_mutation() OWNER TO CURRENT_USER;
ALTER FUNCTION public.a11oy_memory_context_matches(text, text)
  OWNER TO CURRENT_USER;

DO $$
DECLARE
    trigger_row record;
BEGIN
    FOR trigger_row IN
        SELECT relation.relname AS table_name, trigger.tgname AS trigger_name
          FROM pg_catalog.pg_trigger AS trigger
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = trigger.tgrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
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
           AND NOT trigger.tgisinternal
    LOOP
        EXECUTE pg_catalog.format(
            'DROP TRIGGER %I ON public.%I',
            trigger_row.trigger_name,
            trigger_row.table_name
        );
    END LOOP;
END;
$$;

CREATE TRIGGER memory_records_touch_updated_at
BEFORE UPDATE ON public.memory_records
FOR EACH ROW EXECUTE FUNCTION public.memory_touch_updated_at();
CREATE TRIGGER memory_outbox_touch_updated_at
BEFORE UPDATE ON public.memory_outbox
FOR EACH ROW EXECUTE FUNCTION public.memory_touch_updated_at();
CREATE TRIGGER memory_receipts_append_only BEFORE UPDATE OR DELETE ON public.memory_receipts
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();
CREATE TRIGGER memory_query_audit_append_only BEFORE UPDATE OR DELETE ON public.memory_query_audit
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();
CREATE TRIGGER memory_idempotency_append_only BEFORE UPDATE OR DELETE ON public.memory_idempotency
FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();

-- Policy recreation is ineffective if a stale owner disabled RLS. Restore the
-- exact enforcement state in this forward migration, without relying on the
-- historical migrations to run again afterward. Policies are already absent,
-- so FORCE RLS cannot execute attacker-controlled policy expressions below.
ALTER TABLE public.memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence_refs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_outbox NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_receipts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_query_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_query_audit FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_index_generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_index_generations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_idempotency FORCE ROW LEVEL SECURITY;

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

-- Reinstall exactly one tenant/domain policy per application table. The early
-- sweep above is the security boundary; this second sweep is idempotent defense
-- in depth in case a future edit inserts a policy before this section.
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
DECLARE
    observed record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_app') THEN
        CREATE ROLE a11oy_memory_app
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        -- A provider-managed owner (Neon, for example) is never a superuser,
        -- and PostgreSQL refuses any ALTER ROLE that names the superuser
        -- attribute or targets a superuser role unless the caller is one.
        -- Refuse that case by name before touching the role.
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS role
             WHERE role.rolname = 'a11oy_memory_app'
               AND role.rolsuper
        ) AND NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS principal
             WHERE principal.rolname = CURRENT_USER
               AND principal.rolsuper
        ) THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
              MESSAGE = 'a11oy_memory_app holds an attribute this migration principal cannot clear';
        END IF;
        -- Rewrite the role's catalog row before reading it. The row stays
        -- locked until COMMIT, so a concurrent ALTER ROLE waits and then fails
        -- instead of landing between this read and COMMIT.
        ALTER ROLE a11oy_memory_app NOCREATEROLE;
        SELECT role.rolsuper, role.rolcreatedb, role.rolcanlogin,
               role.rolreplication, role.rolinherit, role.rolbypassrls
          INTO observed
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname = 'a11oy_memory_app';
        -- Name only the attributes that deviate.
        IF observed.rolsuper THEN ALTER ROLE a11oy_memory_app NOSUPERUSER; END IF;
        IF observed.rolcreatedb THEN ALTER ROLE a11oy_memory_app NOCREATEDB; END IF;
        IF observed.rolcanlogin THEN ALTER ROLE a11oy_memory_app NOLOGIN; END IF;
        IF observed.rolreplication THEN ALTER ROLE a11oy_memory_app NOREPLICATION; END IF;
        IF NOT observed.rolinherit THEN ALTER ROLE a11oy_memory_app INHERIT; END IF;
        IF observed.rolbypassrls THEN ALTER ROLE a11oy_memory_app NOBYPASSRLS; END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_worker') THEN
        CREATE ROLE a11oy_memory_worker
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        -- A provider-managed owner (Neon, for example) is never a superuser,
        -- and PostgreSQL refuses any ALTER ROLE that names the superuser
        -- attribute or targets a superuser role unless the caller is one.
        -- Refuse that case by name before touching the role.
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS role
             WHERE role.rolname = 'a11oy_memory_worker'
               AND role.rolsuper
        ) AND NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS principal
             WHERE principal.rolname = CURRENT_USER
               AND principal.rolsuper
        ) THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
              MESSAGE = 'a11oy_memory_worker holds an attribute this migration principal cannot clear';
        END IF;
        -- Rewrite the role's catalog row before reading it. The row stays
        -- locked until COMMIT, so a concurrent ALTER ROLE waits and then fails
        -- instead of landing between this read and COMMIT.
        ALTER ROLE a11oy_memory_worker NOCREATEROLE;
        SELECT role.rolsuper, role.rolcreatedb, role.rolcanlogin,
               role.rolreplication, role.rolinherit, role.rolbypassrls
          INTO observed
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname = 'a11oy_memory_worker';
        -- Name only the attributes that deviate.
        IF observed.rolsuper THEN ALTER ROLE a11oy_memory_worker NOSUPERUSER; END IF;
        IF observed.rolcreatedb THEN ALTER ROLE a11oy_memory_worker NOCREATEDB; END IF;
        IF observed.rolcanlogin THEN ALTER ROLE a11oy_memory_worker NOLOGIN; END IF;
        IF observed.rolreplication THEN ALTER ROLE a11oy_memory_worker NOREPLICATION; END IF;
        IF NOT observed.rolinherit THEN ALTER ROLE a11oy_memory_worker INHERIT; END IF;
        IF observed.rolbypassrls THEN ALTER ROLE a11oy_memory_worker NOBYPASSRLS; END IF;
    END IF;
END;
$$;

-- Capability roles must not inherit or SET ROLE into any historical parent.
-- Inbound application/worker login memberships are intentionally preserved.
DO $$
DECLARE
    membership record;
BEGIN
    FOR membership IN
        SELECT DISTINCT parent.rolname AS parent_role,
                        child.rolname AS capability_role
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS parent ON parent.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS child ON child.oid = edge.member
         WHERE child.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE %I FROM %I CASCADE',
            membership.parent_role,
            membership.capability_role
        );
    END LOOP;
END;
$$;

-- Preserve inbound memberships. ADMIN OPTION holders keep the membership row
-- but lose INHERIT and SET, so they can neither use worker EXECUTE nor SET ROLE
-- into it. PostgreSQL 16 and later leave SET true unless it is named.
DO $$
DECLARE
    membership record;
BEGIN
    FOR membership IN
        SELECT DISTINCT parent.rolname AS capability_role,
                        member.rolname AS member_role
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS parent ON parent.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS member ON member.oid = edge.member
         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.admin_option
           AND member.rolname <> CURRENT_USER
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ADMIN OPTION FOR %I FROM %I CASCADE',
            membership.capability_role,
            membership.member_role
        );
        EXECUTE pg_catalog.format(
            'GRANT %I TO %I WITH INHERIT FALSE, SET FALSE, ADMIN FALSE',
            membership.capability_role,
            membership.member_role
        );
    END LOOP;
END;
$$;

-- A principal that is not a superuser can revoke only membership grants it
-- made itself; PostgreSQL reports another grantor's grant as a WARNING and
-- keeps it. Prove both sweeps converged instead of trusting them. The
-- migration principal, which owns every covenant relation, keeps ADMIN so it
-- can still grant these capability roles to runtime logins where no superuser
-- exists. A swept delegate's grant from another grantor is a separate row that
-- can still carry SET or INHERIT. The attributes are re-read last, while this
-- transaction still holds both role rows.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role still belongs to a parent role this principal could not revoke';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS holder ON holder.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.admin_option
           AND holder.rolname <> CURRENT_USER
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'capability-role delegation survived the sweep; another grantor holds it';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS swept
          JOIN pg_catalog.pg_auth_members AS other
            ON other.roleid = swept.roleid
           AND other.member = swept.member
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = swept.roleid
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND NOT swept.admin_option
           AND NOT swept.inherit_option
           AND NOT swept.set_option
           AND (other.inherit_option OR other.set_option)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a swept capability-role delegate keeps SET or INHERIT through another grant';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS capability
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (capability.rolsuper OR capability.rolcreatedb
                OR capability.rolcreaterole OR capability.rolcanlogin
                OR capability.rolreplication OR NOT capability.rolinherit
                OR capability.rolbypassrls)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role attribute did not converge';
    END IF;
END;
$$;

-- Revoke first so reapplication converges from stale additive ACLs. Remove
-- CREATE from every non-owner public-schema grantee, and remove table-level
-- and column-level privileges from every non-owner covenant-table grantee.
REVOKE ALL PRIVILEGES ON SCHEMA public
  FROM a11oy_memory_app, a11oy_memory_worker;
DO $$
DECLARE
    grantee_oid oid;
BEGIN
    FOR grantee_oid IN
        SELECT DISTINCT acl.grantee
          FROM pg_catalog.pg_namespace AS namespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  namespace.nspacl,
                  pg_catalog.acldefault('n', namespace.nspowner)
              )
          ) AS acl
         WHERE namespace.nspname = 'public'
           AND acl.privilege_type = 'CREATE'
           AND acl.grantee <> namespace.nspowner
    LOOP
        IF grantee_oid = 0 THEN
            REVOKE CREATE ON SCHEMA public FROM PUBLIC CASCADE;
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE CREATE ON SCHEMA public FROM %I CASCADE',
                pg_catalog.pg_get_userbyid(grantee_oid)
            );
        END IF;
    END LOOP;
END;
$$;

DO $$
DECLARE
    privilege_row record;
BEGIN
    FOR privilege_row IN
        SELECT DISTINCT relation.relname AS table_name, acl.grantee
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  relation.relacl,
                  pg_catalog.acldefault('r', relation.relowner)
              )
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
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM PUBLIC CASCADE',
                privilege_row.table_name
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I CASCADE',
                privilege_row.table_name,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;

    FOR privilege_row IN
        SELECT DISTINCT relation.relname AS table_name,
                        attribute.attname AS column_name,
                        acl.grantee
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
          JOIN pg_catalog.pg_attribute AS attribute
            ON attribute.attrelid = relation.oid
          CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl
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
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM PUBLIC CASCADE',
                privilege_row.column_name,
                privilege_row.table_name
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM %I CASCADE',
                privilege_row.column_name,
                privilege_row.table_name,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public TO a11oy_memory_app, a11oy_memory_worker;
GRANT SELECT, INSERT, UPDATE ON TABLE public.memory_records TO a11oy_memory_app;
GRANT SELECT, INSERT, DELETE ON TABLE public.memory_evidence_refs TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_receipts TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_query_audit TO a11oy_memory_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.memory_index_generations TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_idempotency TO a11oy_memory_app;
GRANT SELECT, INSERT ON TABLE public.memory_outbox TO a11oy_memory_app;

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
ALTER FUNCTION public.memory_lease_outbox(text, integer, integer)
  OWNER TO CURRENT_USER;

DO $$
DECLARE
    privilege_row record;
BEGIN
    FOR privilege_row IN
        SELECT DISTINCT procedure.oid::pg_catalog.regprocedure::text AS identity,
                        acl.grantee
          FROM pg_catalog.pg_proc AS procedure
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  procedure.proacl,
                  pg_catalog.acldefault('f', procedure.proowner)
              )
          ) AS acl
         WHERE procedure.oid = ANY(ARRAY[
                   'public.memory_touch_updated_at()'::pg_catalog.regprocedure,
                   'public.memory_reject_mutation()'::pg_catalog.regprocedure,
                   'public.a11oy_memory_context_matches(text,text)'::pg_catalog.regprocedure,
                   'public.memory_lease_outbox(text,integer,integer)'::pg_catalog.regprocedure
               ])
           AND acl.grantee <> procedure.proowner
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC CASCADE',
                privilege_row.identity
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM %I CASCADE',
                privilege_row.identity,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;
END;
$$;

GRANT EXECUTE ON FUNCTION public.a11oy_memory_context_matches(text, text)
  TO a11oy_memory_app;
GRANT EXECUTE ON FUNCTION public.memory_lease_outbox(text, integer, integer)
  TO a11oy_memory_worker;

COMMENT ON FUNCTION public.memory_lease_outbox(text, integer, integer) IS
    'Bounded cross-tenant lease for dedicated worker role members only.';

COMMIT;
