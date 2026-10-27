#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Capture supervisor startup errors without a visible console."""
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import runpy, traceback
home=Path(__file__).resolve().parent
stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
with (home/"logs"/(stamp+"-supervisor.stdout")).open("x") as out, (home/"logs"/(stamp+"-supervisor.stderr")).open("x") as err:
 with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
  try:
   runpy.run_path(str(home/"windows-supervisor.py"),run_name="__main__")
  except SystemExit:
   raise
  except Exception:
   traceback.print_exc()
   raise SystemExit(1)
