#!/usr/bin/env python3
"""run_all_json.py — thin JSON wrapper around OUROBOROS_RUN_ALL.py.

Imports the embedded-module runner, executes the 32 module self-tests in a temp
dir (exactly as the canonical _run_all does), and emits a single JSON object to
stdout: {verdict, total, green, red, duration_s, exit_code, results:[{name,status,duration_s}]}.

Stdlib-only. Invoked by the a11oy serve.py /api/a11oy/internal/run-all endpoint.
The real runner lives at /app/OUROBOROS_RUN_ALL.py on the Space."""
from __future__ import annotations
import importlib.util, json, sys, time, tempfile, pathlib, io, contextlib

RUNNER = pathlib.Path(__file__).with_name("OUROBOROS_RUN_ALL.py")

def load_runner():
    spec = importlib.util.spec_from_file_location("ouro_run_all", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ouro_run_all"] = mod
    spec.loader.exec_module(mod)
    return mod

def main(list_only: bool = False) -> int:
    R = load_runner()
    if list_only:
        print(json.dumps({"modules": list(R._MODULE_FILES), "count": len(R._MODULE_FILES)}))
        return 0
    results = []
    total_fail = 0
    t_all = time.time()
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = pathlib.Path(tmp_str)
        R._write_modules(tmp)
        for name in R._MODULE_FILES:
            path = tmp / name
            t0 = time.time()
            # silence each module's chatty stdout; we only want pass/fail
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    _, fails = R._run_module(name, path)
                dt = time.time() - t0
                if fails == 0:
                    status = "GREEN"
                else:
                    status = f"RED ({fails} fail)"
                    total_fail += fails
                results.append({"name": name, "status": status, "duration_s": round(dt, 3)})
            except Exception as exc:  # noqa
                total_fail += 1
                results.append({"name": name, "status": f"ERROR: {exc}", "duration_s": round(time.time() - t0, 3)})
    green = len([r for r in results if "GREEN" in r["status"]])
    red = len([r for r in results if "GREEN" not in r["status"]])
    out = {
        "runner": "OUROBOROS_RUN_ALL.py",
        "verdict": "GREEN" if total_fail == 0 else "RED",
        "total": len(results),
        "green": green,
        "red": red,
        "total_failures": total_fail,
        "exit_code": 0 if total_fail == 0 else 1,
        "duration_s": round(time.time() - t_all, 3),
        "header_advertised_modules": 25,
        "actual_embedded_modules": len(R._MODULE_FILES),
        "results": results,
        "doctrine": "v10",
    }
    print(json.dumps(out))
    return out["exit_code"]

if __name__ == "__main__":
    list_only = "--list" in sys.argv
    sys.exit(main(list_only=list_only))
