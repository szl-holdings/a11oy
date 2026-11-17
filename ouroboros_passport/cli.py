import argparse, hashlib, json, sys
from .passport import build_from_training_report
from .promotion import evaluate
from .verifier import verify

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ouroboros_passport")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("report"); b.add_argument("dataset"); b.add_argument("--tenant", default="szl-estate")
    v = sub.add_parser("verify"); v.add_argument("passport")
    p = sub.add_parser("promote"); p.add_argument("passport")
    s = sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        report = json.load(open(args.report, encoding="utf-8"))
        dsd = hashlib.sha256(open(args.dataset, "rb").read()).hexdigest()
        print(json.dumps(build_from_training_report(report, dsd, tenant=args.tenant), indent=2))
    elif args.cmd == "verify":
        result = verify(json.load(open(args.passport, encoding="utf-8")))
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1
    elif args.cmd == "promote":
        result = evaluate(json.load(open(args.passport, encoding="utf-8")))
        print(json.dumps(result, indent=2))
        return 0 if result["eligible"] else 1
    elif args.cmd == "selftest":
        report = {"run": "selftest-r1", "base": "Qwen/Qwen3-1.7B", "corpus_examples": 188,
                  "dataset": "SZLHOLDINGS/clinical-abstention-sft-api-v2", "wall_hours": 0.7,
                  "method": "LoRA r32 a64 bf16", "candidate": "SZLHOLDINGS/salad-clinical-abstention-r1",
                  "curriculum": "synthetic, generated via Anthropic Messages API (claude-haiku-5-5) 2026-11-15"}
        passport = build_from_training_report(report, "0" * 64)
        ver = verify(passport)
        dec = evaluate(passport)
        ok = ver["valid"] and ver["digest_ok"] and dec["decision"] == "CANDIDATE" and len(dec["blocking"]) == 9
        print(json.dumps({"selftest": "PASS" if ok else "FAIL", "verify": ver, "promotion": {"decision": dec["decision"], "n_blocking": len(dec["blocking"]), "n_passed": len(dec["passed"])}}))
        return 0 if ok else 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
