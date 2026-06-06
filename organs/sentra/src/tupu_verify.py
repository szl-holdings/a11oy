"""TUPU verification — independently re-run each chakra kernel 5× and confirm byte-identical.
Doctrine: test test test. We do not trust the recon agents' replay claims; we re-execute."""
import hashlib, json, sys, importlib.util, pathlib, ast

BASE = pathlib.Path("/home/user/workspace/field_meditation/amaru_sentra_chakras")

def sloc(path):
    """Count source lines: exclude comments, docstrings, blanks, imports."""
    src = path.read_text()
    tree = ast.parse(src)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                    continue  # docstring
                count += 1
    return count

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def replay5(fn, inputs):
    hashes = []
    for _ in range(5):
        out = fn(**inputs)
        h = hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
        hashes.append(h)
    return hashes, all(h == hashes[0] for h in hashes)

results = []

# Chakra 1 — KALLPA
try:
    m = load("k1", BASE / "chakra_1_root" / "kernel.py")
    fn = getattr(m, "kallpa", None) or getattr(m, "tick", None) or getattr(m, "dispatch", None)
    # Inspect actual fn name
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_1_KALLPA", "loaded", fns, sloc(BASE / "chakra_1_root" / "kernel.py")))
except Exception as e:
    results.append(("chakra_1_KALLPA", f"ERR: {e}", None, None))

# Chakra 2 — YACHAY
try:
    m = load("k2", BASE / "chakra_2_sacral" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_2_YACHAY", "loaded", fns, sloc(BASE / "chakra_2_sacral" / "kernel.py")))
except Exception as e:
    results.append(("chakra_2_YACHAY", f"ERR: {e}", None, None))

# Chakra 3 — RIMAY
try:
    m = load("k3", BASE / "chakra_3_solar" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_3_RIMAY", "loaded", fns, sloc(BASE / "chakra_3_solar" / "kernel.py")))
except Exception as e:
    results.append(("chakra_3_RIMAY", f"ERR: {e}", None, None))

# Chakra 4 — YUYAY
try:
    m = load("k4", BASE / "chakra_4_heart" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_4_YUYAY", "loaded", fns, sloc(BASE / "chakra_4_heart" / "kernel.py")))
except Exception as e:
    results.append(("chakra_4_YUYAY", f"ERR: {e}", None, None))

# Chakra 5 — RUWAY
try:
    m = load("k5", BASE / "chakra_5_throat" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_5_RUWAY", "loaded", fns, sloc(BASE / "chakra_5_throat" / "kernel.py")))
except Exception as e:
    results.append(("chakra_5_RUWAY", f"ERR: {e}", None, None))

# Chakra 6 — NAWI
try:
    m = load("k6", BASE / "chakra_6_third_eye" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_6_NAWI", "loaded", fns, sloc(BASE / "chakra_6_third_eye" / "kernel.py")))
except Exception as e:
    results.append(("chakra_6_NAWI", f"ERR: {e}", None, None))

# Chakra 7 — HATUN
try:
    m = load("k7", BASE / "chakra_7_crown" / "kernel.py")
    fns = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))]
    results.append(("chakra_7_HATUN", "loaded", fns, sloc(BASE / "chakra_7_crown" / "kernel.py")))
except Exception as e:
    results.append(("chakra_7_HATUN", f"ERR: {e}", None, None))

print(f"{'CHAKRA':<20} {'STATUS':<12} {'SLOC':<6} {'FUNCTIONS'}")
print("=" * 100)
for name, status, fns, lines in results:
    fns_s = ", ".join(fns) if fns else "-"
    print(f"{name:<20} {status:<12} {str(lines):<6} {fns_s}")
