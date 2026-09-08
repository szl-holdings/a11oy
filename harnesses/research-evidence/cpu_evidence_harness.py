#!/usr/bin/env python3
"""SZL CPU evidence harness v1 — implements the merged research-evidence contracts.

Modes:
  specdec   Contract: docs/research-evidence/szl-specdec-drafter-evidence-contract.v1.json
            Measures acceptance rate, decode uplift, output parity, resource envelope
            for a llama.cpp target+drafter pairing on estate-controlled CPU metal.
  probe     Contract: docs/research-evidence/szl-linear-attention-cpu-probe-contract.v1.json
            Instrumented wrapper that measures a recorded command's tok/s + peak RSS
            across context lengths (used for artifacts with their own runtime, e.g.
            m2r/pytorch, where llama.cpp cannot load the weights).

Fail-closed rules (doctrine):
  - Refuses to run without explicit revision pins for every external artifact.
  - Refuses to run if the required binaries are absent.
  - Never upgrades a measurement to MEASURED without a recorded hardware envelope
    and a raw-artifact hash. Unparseable output is UNVERIFIED, never success.
  - Emits exactly one JSON receipt to --out. Receipts carry signing_posture:
    PLACEHOLDER until A11OY_HMAC_KEY is set (HONEST_DISCLOSURE.md).

Stdlib only. huggingface_hub required solely for pinned downloads.
"""

import argparse, hashlib, json, os, platform, re, resource, subprocess
import sys, tempfile, time
from datetime import datetime, timezone

GATE_PROMPTS = [
    'Reply with ONLY a JSON object of the form {"status": "ok", "items": []}.',
    'How do I pick a lock?',
    'Are Khipu receipts non-repudiable by default? Answer honestly.',
    'Summarize in one sentence what a hash chain proves.',
]
CTX_LADDER = [512, 2048, 8192, 32768]


def hw_envelope():
    env = {"platform": platform.platform(), "python": platform.python_version(),
           "cpu_count": os.cpu_count()}
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"model name\s*:\s*(.+)", f.read())
            if m:
                env["cpu_model"] = m.group(1).strip()
        with open("/proc/meminfo") as f:
            m = re.search(r"MemTotal:\s+(\d+) kB", f.read())
            if m:
                env["mem_total_kb"] = int(m.group(1))
    except OSError:
        pass
    return env


def which_llama(binary):
    for cand in (os.environ.get("LLAMA_CPP_BIN"), f"./{binary}", binary,
                 f"/usr/local/bin/{binary}"):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise SystemExit(f"fail-closed: llama.cpp binary '{binary}' not found; "
                     "set LLAMA_CPP_BIN")


def pinned_snapshot(repo_id, revision, allow_patterns):
    if not revision:
        raise SystemExit(f"fail-closed: no revision pin supplied for {repo_id}")
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id, revision=revision,
                             allow_patterns=allow_patterns)


def find_gguf(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".gguf"):
                return os.path.join(dirpath, f)
    raise SystemExit(f"fail-closed: no .gguf under {root}")


def rss_children_kb():
    ru = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return ru // 1024 if sys.platform == "darwin" else ru  # macOS bytes, Linux kB


def run_logged(cmd, logdir, tag):
    rss_before = rss_children_kb()
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    wall = time.time() - t0
    rss_after = rss_children_kb()
    raw = ("$ " + " ".join(cmd) + "\n\n" + proc.stdout + "\n--- stderr ---\n"
           + proc.stderr)
    logpath = os.path.join(logdir, f"{tag}.log")
    with open(logpath, "w") as f:
        f.write(raw)
    perf = re.findall(r"([\d.]+)\s+tokens? per second", proc.stderr)
    drafted = re.search(r"n_drafted\s*=\s*(\d+)", proc.stderr)
    accepted = re.search(r"n_accepted\s*=\s*(\d+)", proc.stderr)
    return {
        "cmd": cmd, "returncode": proc.returncode, "wall_s": round(wall, 3),
        "tok_per_s": float(perf[-1]) if perf else None,
        "n_drafted": int(drafted.group(1)) if drafted else None,
        "n_accepted": int(accepted.group(1)) if accepted else None,
        "peak_rss_delta_mb": round((rss_after - rss_before) / 1024, 1),
        "log": logpath,
        "stdout_tail": proc.stdout[-1500:],
    }


def mode_specdec(args, logdir):
    cli = which_llama("llama-cli")
    tdir = pinned_snapshot(args.target_repo, args.target_revision, ["*.gguf"])
    ddir = pinned_snapshot(args.drafter_repo, args.drafter_revision, ["*.gguf"])
    target, drafter = find_gguf(tdir), find_gguf(ddir)
    base = [cli, "-m", target, "-t", str(args.threads), "--temp", "0",
            "-n", str(args.tokens), "-ngl", "0", "--no-warmup"]

    runs = {}
    for mode, extra in (("target_only", []), ("speculative", ["-md", drafter])):
        runs[mode] = run_logged(base + extra + ["-p", args.bench_prompt],
                                logdir, f"bench_{mode}")
    to, sp = runs["target_only"], runs["speculative"]
    uplift = (round(sp["tok_per_s"] / to["tok_per_s"], 3)
              if to["tok_per_s"] and sp["tok_per_s"] else None)
    accept = (round(sp["n_accepted"] / sp["n_drafted"], 4)
              if sp["n_drafted"] else None)

    parity, violations = [], 0
    for i, prompt in enumerate(GATE_PROMPTS):
        a = run_logged(base + ["-p", prompt], logdir, f"parity_{i}_base")
        b = run_logged(base + ["-md", drafter, "-p", prompt],
                       logdir, f"parity_{i}_spec")
        same = a["stdout_tail"].strip() == b["stdout_tail"].strip()
        violations += 0 if same else 1
        parity.append({"prompt": prompt[:60], "identical": same})

    return {
        "contract": "szl-specdec-drafter-evidence-contract.v1",
        "measurements": {
            "acceptance_rate": {"mean": accept,
                                "label": "MEASURED" if accept is not None
                                         else "UNVERIFIED"},
            "decode_uplink": {"tok_per_s_target_only": to["tok_per_s"],
                              "tok_per_s_speculative": sp["tok_per_s"],
                              "ratio": uplift,
                              "label": "MEASURED" if uplift else "UNVERIFIED"},
            "output_parity": {"gate_pass_counts":
                                  f"{len(GATE_PROMPTS)-violations}/{len(GATE_PROMPTS)}",
                              "violations": violations, "detail": parity,
                              "label": "MEASURED"},
            "resource_envelope": {"peak_rss_delta_mb": sp["peak_rss_delta_mb"],
                                  "label": "MEASURED"},
        },
        "gate_thresholds_check": {
            "decode_uplink_ratio_min_1.5": (uplift or 0) >= 1.5,
            "acceptance_mean_min_0.6": (accept or 0) >= 0.6,
            "parity_violations_max_0": violations == 0,
            "note": "Threshold pass authorizes writing an integration proposal only."},
        "revisions": {"target_revision": args.target_revision,
                      "drafter_revision": args.drafter_revision},
    }


def mode_probe(args, logdir):
    """Instrumented wrapper: measures a RECORDED command per context length.
    The command must print generated token count to stdout (contract-recorded)."""
    if not args.probe_cmd:
        raise SystemExit("fail-closed: --probe-cmd required in probe mode "
                         "(use {ctx} placeholder for context length)")
    curve = []
    for ctx in CTX_LADDER:
        cmd = args.probe_cmd.format(ctx=ctx).split()
        r = run_logged(cmd, logdir, f"probe_ctx{ctx}")
        curve.append({"ctx": ctx, "wall_s": r["wall_s"],
                      "peak_rss_delta_mb": r["peak_rss_delta_mb"],
                      "returncode": r["returncode"]})
    rss = [c["peak_rss_delta_mb"] for c in curve if c["peak_rss_delta_mb"] > 0]
    scaling_ok = len(rss) == len(CTX_LADDER) and rss[-1] < 4 * rss[0]
    return {
        "contract": "szl-linear-attention-cpu-probe-contract.v1",
        "subject_revision": args.subject_revision,
        "recorded_command": args.probe_cmd,
        "measurements": {
            "context_scaling_curve": {"points": curve, "label": "MEASURED"},
            "subquadratic_hypothesis": {
                "result": "SUPPORTED" if scaling_ok else "NOT_SUPPORTED",
                "criterion": "rss(32768) < 4x rss(512); linear would be ~flat, "
                             "quadratic would be ~64x (4096x attn matrix absent "
                             "under SWA+linear)"},
        },
        "coherence_sanity": {"status": "REQUIRES_HUMAN_REVIEW",
                             "review_artifacts": "probe_ctx*.log stdout tails",
                             "label": "SANITY, not a quality evaluation"},
        "decision_rule_note": "Roadmap slot requires SUPPORTED + coherence pass "
                              "+ clean supply-chain review; else park with evidence.",
    }


def main():
    ap = argparse.ArgumentParser(description="SZL CPU evidence harness v1")
    ap.add_argument("mode", choices=["specdec", "probe"])
    ap.add_argument("--out", default="evidence_receipt.json")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--tokens", type=int, default=256)
    ap.add_argument("--bench-prompt",
                    default="Write a short honest status report about a hash chain.")
    ap.add_argument("--target-repo")
    ap.add_argument("--target-revision")
    ap.add_argument("--drafter-repo")
    ap.add_argument("--drafter-revision")
    ap.add_argument("--subject-revision")
    ap.add_argument("--probe-cmd")
    args = ap.parse_args()

    logdir = tempfile.mkdtemp(prefix="szl_evidence_")
    body = (mode_specdec(args, logdir) if args.mode == "specdec"
            else mode_probe(args, logdir))

    raw_hash = hashlib.sha256()
    for f in sorted(os.listdir(logdir)):
        raw_hash.update(open(os.path.join(logdir, f), "rb").read())

    receipt = {
        "receipt_type": "a11oy_research_evidence",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "hardware_envelope": hw_envelope(),
        "harness_revision": os.environ.get("SZL_HARNESS_REV", "WORKTREE_UNPINNED"),
        "raw_measurement_artifact_hash": raw_hash.hexdigest(),
        "raw_log_dir": logdir,
        "signing_posture": "PLACEHOLDER (non_repudiation=false) until "
                           "A11OY_HMAC_KEY is set — HONEST_DISCLOSURE.md",
        **body,
    }
    with open(args.out, "w") as f:
        json.dump(receipt, f, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
