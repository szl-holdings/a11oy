#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Capture classified supervisor startup failures without a visible console."""

import contextlib
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy


PREFLIGHT_FAILURES = {
    "Pinned source mismatch": "SOURCE_PIN_MISMATCH",
    "Pinned SSH configuration mismatch": "SSH_CONFIG_PIN_MISMATCH",
    "Existing listener preserved; startup refused": "EXISTING_LISTENER_PRESERVED",
    "Invalid private gateway credential": "INVALID_GATEWAY_CREDENTIAL",
}


def record_failure(stream, code):
    """Write only a fixed diagnostic code; this is not a signed receipt."""
    print(json.dumps({
        "schema": "szl.vm-model-bootstrap-failure/v1",
        "failure_code": code,
        "signed": False,
    }, sort_keys=True), file=stream, flush=True)


def main():
    home = Path(__file__).resolve().parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with (home / "logs" / (stamp + "-supervisor.stdout")).open("x") as out, \
            (home / "logs" / (stamp + "-supervisor.stderr")).open("x") as err:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                runpy.run_path(str(home / "windows-supervisor.py"), run_name="__main__")
            except SystemExit as exc:
                status = exc.code
                if status is None or (isinstance(status, int) and status == 0):
                    raise
                if type(status) is str:
                    code = PREFLIGHT_FAILURES.get(status, "UNCLASSIFIED_SYSTEM_EXIT")
                elif isinstance(status, int):
                    code = "NONZERO_SYSTEM_EXIT"
                else:
                    code = "UNCLASSIFIED_SYSTEM_EXIT"
                record_failure(err, code)
                # Re-raising a string SystemExit prints it after redirection has
                # closed. Preserve failure without leaking that message to pythonw.
                raise SystemExit(status if isinstance(status, int) else 1) from None
            except Exception:
                record_failure(err, "SUPERVISOR_EXCEPTION")
                raise SystemExit(1) from None


if __name__ == "__main__":
    main()
