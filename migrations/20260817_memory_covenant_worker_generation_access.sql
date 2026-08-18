-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant — RLS-bound generation identity read for the worker.
-- Apply after 20260811_memory_covenant_v2_security_hardening.sql.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='a11oy_memory_worker') THEN
        RAISE EXCEPTION USING ERRCODE='42704', MESSAGE='a11oy_memory_worker role is required';
    END IF;

    GRANT SELECT ON memory_index_generations TO a11oy_memory_worker;
END;
$$;

COMMENT ON TABLE memory_index_generations IS
    'Authoritative immutable generation identity; worker SELECT remains tenant/security-domain RLS-bound.';

COMMIT;
