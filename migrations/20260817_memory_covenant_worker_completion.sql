-- SPDX-License-Identifier: Apache-2.0
-- A11oy Memory Covenant — bounded worker completion authority.
-- Apply after 20260811_memory_covenant_v2_security_hardening.sql.

BEGIN;

CREATE OR REPLACE FUNCTION memory_complete_outbox(
    p_worker_id text,
    p_event_id text,
    p_success boolean,
    p_retryable boolean DEFAULT true,
    p_result_json jsonb DEFAULT '{}'::jsonb,
    p_error_class text DEFAULT NULL,
    p_retry_seconds integer DEFAULT 30
)
RETURNS memory_outbox
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    completed memory_outbox;
BEGIN
    IF p_worker_id IS NULL OR p_worker_id = '' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker id is required';
    END IF;
    IF p_event_id IS NULL OR p_event_id = '' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='event id is required';
    END IF;
    IF p_retry_seconds < 1 OR p_retry_seconds > 3600 THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='retry delay is outside the bounded contract';
    END IF;
    IF p_result_json IS NULL OR jsonb_typeof(p_result_json) <> 'object' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='result_json must be one object';
    END IF;
    IF p_success AND p_error_class IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='successful completion cannot include an error class';
    END IF;
    IF NOT p_success AND (p_error_class IS NULL OR p_error_class = '') THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='failed completion requires an error class';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='a11oy_memory_worker')
       OR NOT pg_has_role(session_user, 'a11oy_memory_worker', 'member') THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='session user is not an a11oy_memory_worker member';
    END IF;

    UPDATE memory_outbox
       SET status = CASE
                        WHEN p_success THEN 'DONE'
                        WHEN p_retryable THEN 'RETRY'
                        ELSE 'FAILED'
                    END,
           available_at = CASE
                              WHEN NOT p_success AND p_retryable
                                  THEN now() + make_interval(secs => p_retry_seconds)
                              ELSE available_at
                          END,
           lease_owner = NULL,
           lease_expires_at = NULL,
           last_error = CASE
                            WHEN p_success THEN NULL
                            ELSE left(p_error_class, 255)
                        END,
           result_json = p_result_json,
           updated_at = now()
     WHERE event_id = p_event_id
       AND status = 'LEASED'
       AND lease_owner = p_worker_id
       AND lease_expires_at IS NOT NULL
    RETURNING * INTO completed;

    IF completed.event_id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='leased event is unavailable for this worker';
    END IF;

    RETURN completed;
END;
$$;

REVOKE ALL ON FUNCTION memory_complete_outbox(
    text, text, boolean, boolean, jsonb, text, integer
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='a11oy_memory_worker') THEN
        GRANT EXECUTE ON FUNCTION memory_complete_outbox(
            text, text, boolean, boolean, jsonb, text, integer
        ) TO a11oy_memory_worker;
    END IF;
END;
$$;

COMMENT ON FUNCTION memory_complete_outbox(
    text, text, boolean, boolean, jsonb, text, integer
) IS 'Completes only the caller worker lease; bounds retry delay and stores sanitized result metadata.';

COMMIT;
