"""Convert a GDW burst result into CSV, summary JSON, and offline HTML."""

import argparse
import csv
import hashlib
import html
import json
import math
from collections import Counter
from pathlib import Path


def percentile(values, quantile):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def build_summary(document):
    rows = document["rows"]
    latencies = [row["latency_ms"] for row in rows]
    accepted = [row for row in rows if row.get("decision") == "ACCEPT"]
    errors = [row for row in rows if row.get("status") != 200]
    transport_errors = [row for row in rows if row.get("status") == 0]
    malformed = [
        row
        for row in rows
        if row.get("status") not in (0, None) and not row.get("json_valid")
    ]
    missing_receipts = [row for row in accepted if not row.get("receipt_hash")]
    summary = {
        "schema": "szl.gdw.burst-summary/v1",
        "label": "MEASURED",
        "total": len(rows),
        "http_ok": len(rows) - len(errors),
        "http_errors": len(errors),
        "error_rate": len(errors) / len(rows) if rows else 0.0,
        "transport_errors": len(transport_errors),
        "malformed_json": len(malformed),
        "accepted": len(accepted),
        "accepted_missing_receipts": len(missing_receipts),
        "receipt_integrity_ok": not missing_receipts,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "decisions": dict(Counter(row.get("decision") or "UNKNOWN" for row in rows)),
        "routes": dict(
            Counter(row.get("scheduler_mode") or "UNKNOWN" for row in rows)
        ),
        "persistence_integrity": document.get("persistence_integrity", {}),
        "requests_per_second": document.get("requests_per_second"),
    }
    summary["acceptance"] = {
        "error_rate_under_1_percent": summary["error_rate"] < 0.01,
        "json_valid": summary["malformed_json"] == 0,
        "receipts_complete": summary["receipt_integrity_ok"],
        "persistence_clean": bool(
            summary["persistence_integrity"].get("ok", False)
        ),
    }
    return summary


def render_html(summary):
    decisions = json.dumps(summary["decisions"], sort_keys=True)
    routes = json.dumps(summary["routes"], sort_keys=True)
    cards = [
        ("Requests", summary["total"]),
        ("HTTP errors", summary["http_errors"]),
        ("p50 ms", f"{summary['p50_ms']:.2f}"),
        ("p95 ms", f"{summary['p95_ms']:.2f}"),
        ("p99 ms", f"{summary['p99_ms']:.2f}"),
        ("Missing receipts", summary["accepted_missing_receipts"]),
    ]
    card_html = "".join(
        f"<article><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></article>"
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>GDW measured burst evidence</title>
<style>
:root{{--ink:#13251f;--paper:#f3f0e6;--signal:#e65b35;--line:#b7c2b4}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#dce7d7,var(--paper) 55%);
color:var(--ink);font:16px/1.45 Georgia,serif}}main{{max-width:1100px;margin:auto;padding:48px 20px}}
h1{{font-size:clamp(2.4rem,7vw,5.5rem);line-height:.9;margin:.15em 0}}.eyebrow{{letter-spacing:.18em;
text-transform:uppercase}}section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
article,pre{{background:#fff9;border:1px solid var(--line);padding:18px;box-shadow:6px 6px 0 #263d3222}}
article span{{display:block;font-size:.8rem;text-transform:uppercase}}article strong{{font-size:2rem;color:var(--signal)}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}footer{{margin-top:30px;border-top:2px solid var(--ink);padding-top:12px}}
</style><main><p class="eyebrow">Measured harness output</p><h1>GDW burst evidence</h1>
<p>This page reports one captured run. It is not a universal throughput claim.</p>
<section>{card_html}</section><h2>Decision distribution</h2><pre>{html.escape(decisions)}</pre>
<h2>Route distribution</h2><pre>{html.escape(routes)}</pre>
<h2>Acceptance gates</h2><pre>{html.escape(json.dumps(summary['acceptance'], indent=2))}</pre>
<footer>Offline artifact. No CDN or live data dependency.</footer></main></html>"""


def main(args):
    source = Path(args.source)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    document = json.loads(source.read_text(encoding="utf-8"))
    rows = document["rows"]
    summary = build_summary(document)

    columns = sorted({key for row in rows for key in row})
    with (output / "gdw_burst_results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    summary_path = output / "gdw_burst_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "gdw_dashboard.html").write_text(
        render_html(summary), encoding="utf-8"
    )
    manifest = {}
    for path in sorted(output.glob("gdw_*")):
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "SHA256SUMS.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(str(summary_path.resolve()))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", default="output/bench_results/gdw_burst_results.json"
    )
    parser.add_argument("--output-dir", default="output/bench_results")
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
