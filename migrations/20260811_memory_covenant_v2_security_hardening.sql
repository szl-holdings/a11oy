-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant v0.1 — role/RLS and worker hardening.
-- Apply after 20260811_memory_covenant_v2.sql.
-- PostgreSQL remains authoritative; derived indexes remain rebuildable.

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

-- The runtime login is expected to inherit this capability role. Existing
-- roles are normalized, not trusted. Any missing authority aborts the entire
-- transaction; a partially hardened role must never be treated as enabled.
DO $$
DECLARE
    observed record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_app') THEN
        CREATE ROLE a11oy_memory_app
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        -- A provider-managed owner is not expected to be a superuser (for
        -- Neon this is MODELED, not read back from the provider), and
        -- PostgreSQL refuses any ALTER ROLE that names the superuser attribute
        -- or targets a superuser role unless the caller is one. Refuse that
        -- case by name before touching the role.
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
        -- instead of landing between this read and COMMIT. A principal that
        -- is not a superuser needs CREATEROLE and ADMIN on the role for this
        -- statement; clearing CREATEDB or REPLICATION below also needs the
        -- principal to hold that attribute itself.
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
END;
$$;

-- The outbox worker receives no table-wide bypass. Cross-tenant leasing is
-- exposed only through the bounded SECURITY DEFINER function below.
DO $$
DECLARE
    observed record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'a11oy_memory_worker') THEN
        CREATE ROLE a11oy_memory_worker
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        -- A provider-managed owner is not expected to be a superuser (for
        -- Neon this is MODELED, not read back from the provider), and
        -- PostgreSQL refuses any ALTER ROLE that names the superuser attribute
        -- or targets a superuser role unless the caller is one. Refuse that
        -- case by name before touching the role.
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
        -- instead of landing between this read and COMMIT. A principal that
        -- is not a superuser needs CREATEROLE and ADMIN on the role for this
        -- statement; clearing CREATEDB or REPLICATION below also needs the
        -- principal to hold that attribute itself.
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
-- can still carry SET or INHERIT.
-- Runtime logins must INHERIT their capability role. A row with SET but
-- neither INHERIT nor ADMIN is the signature older sweeps left behind, and it
-- lets SET ROLE reach the capability without the inherited privileges the
-- lease guard checks.
-- PostgreSQL authorizes GRANT <role> against committed state before it takes
-- the role's lock, so an ADMIN holder connected while this runs can still add
-- a row after COMMIT whose grantor no longer holds ADMIN. Every row must name
-- a superuser or a current ADMIN holder as its grantor. This detects such a row
-- on the next run and in the acceptance; it cannot prevent it, so no ADMIN
-- holder may be connected while the migrations run.
-- A capability role must not own the database or any schema: ownership is a
-- privilege path that pg_auth_members does not show. The attributes are
-- re-read last, while this transaction still holds both role rows.
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
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS holder ON holder.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.set_option
           AND NOT edge.inherit_option
           AND NOT edge.admin_option
           AND holder.rolname <> CURRENT_USER
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability-role membership grants SET without INHERIT; runtime logins must inherit';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_roles AS grantor
                WHERE grantor.oid = edge.grantor
                  AND grantor.rolsuper
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_auth_members AS authority
                WHERE authority.roleid = edge.roleid
                  AND authority.member = edge.grantor
                  AND authority.admin_option
           )
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability-role membership was granted by a role that no longer holds ADMIN on it';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS capability
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (EXISTS (
                    SELECT 1
                      FROM pg_catalog.pg_database AS owned_database
                     WHERE owned_database.datname = pg_catalog.current_database()
                       AND owned_database.datdba = capability.oid
                )
                OR EXISTS (
                    SELECT 1
                      FROM pg_catalog.pg_namespace AS owned_schema
                     WHERE owned_schema.nspowner = capability.oid
                ))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role owns the database or a schema';
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

-- Reapplication is subtractive before it is additive. Remove schema CREATE
-- from every non-owner grantee; USAGE for unrelated public-schema consumers is
-- left intact. Then remove every non-owner table and column ACL on covenant
-- relations before restoring the exact application contract.
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
    -- USAGE, not MEMBER: in PostgreSQL 16 and later MEMBER is true for any
    -- membership row, including a swept delegate's and a SET-only one. Only a
    -- session user that inherits the worker role may lease.
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='a11oy_memory_worker'
    ) OR NOT pg_catalog.pg_has_role(
        session_user,
        'a11oy_memory_worker',
        'USAGE'
    ) THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='session user does not inherit a11oy_memory_worker';
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

-- CREATE OR REPLACE preserves existing ACLs. Converge every covenant helper
-- from arbitrary and PUBLIC grants, then restore only the two callable
-- capabilities required by the RLS and worker contracts.
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
    'Bounded cross-tenant lease for logins that inherit the dedicated worker role only.';

COMMIT;
