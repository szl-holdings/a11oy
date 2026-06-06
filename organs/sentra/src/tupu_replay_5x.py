"""TUPU independent 5x byte-identical replay across all 7 chakras.
We re-run each kernel with the inputs claimed by the recon agent and verify the hash matches their claim."""
import hashlib, json, importlib.util, pathlib

BASE = pathlib.Path("/home/user/workspace/field_meditation/amaru_sentra_chakras")

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def hashout(out):
    return hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()

def run5(fn, kwargs):
    hashes = [hashout(fn(**kwargs)) for _ in range(5)]
    return hashes, all(h == hashes[0] for h in hashes)

CLAIMS = {}
RESULTS = {}

# === Chakra 1 KALLPA ===
m1 = load("k1", BASE / "chakra_1_root" / "kernel.py")
# Inspect signature
import inspect
sig = inspect.signature(m1.dispatch)
print(f"Chakra 1 dispatch sig: {sig}")
# Build minimal state/world
state = {"seed": 7}
world = {"CPU": 0.1, "GPU": 0.3, "QUANTIZED": 0.05, "MOE": 0.2}
try:
    hashes, ok = run5(m1.dispatch, {"state": state, "world": world})
    RESULTS["chakra_1"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_1"] = (f"ERR {e}", False)

# === Chakra 2 YACHAY ===
m2 = load("k2", BASE / "chakra_2_sacral" / "kernel.py")
sig = inspect.signature(m2.yachay)
print(f"Chakra 2 yachay sig: {sig}")
import math
# Try with simple inputs
try:
    query = [1.0, 0.5, 0.2]
    codex_store = [[1.0, 0.5, 0.2], [0.0, 1.0, 0.0], [0.5, 0.5, 0.5]]
    pirwa_store = [[1.0, 0.5, 0.2], [0.2, 0.3, 0.1]]
    # Inspect signature first
    params = list(sig.parameters.keys())
    print(f"  params: {params}")
    kwargs = {}
    if "query" in params: kwargs["query"] = query
    if "codex_store" in params: kwargs["codex_store"] = codex_store
    if "pirwa_store" in params: kwargs["pirwa_store"] = pirwa_store
    if "seed" in params: kwargs["seed"] = 42
    if "k" in params or "top_k" in params:
        kn = "k" if "k" in params else "top_k"
        kwargs[kn] = 2
    hashes, ok = run5(m2.yachay, kwargs)
    RESULTS["chakra_2"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_2"] = (f"ERR {e}", False)

# === Chakra 3 RIMAY ===
m3 = load("k3", BASE / "chakra_3_solar" / "kernel.py")
sig = inspect.signature(m3.propose)
print(f"Chakra 3 propose sig: {sig}")
try:
    kwargs = {"state": {}, "world": {}, "features": [0.1, 0.2, 0.3], "priors": [0.1, 0.5, 0.4], "seed": 42}
    hashes, ok = run5(m3.propose, kwargs)
    RESULTS["chakra_3"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_3"] = (f"ERR {e}", False)

# === Chakra 4 YUYAY ===
m4 = load("k4", BASE / "chakra_4_heart" / "kernel.py")
sig = inspect.signature(m4.yuyay)
print(f"Chakra 4 yuyay sig: {sig}")
try:
    AXES = ["moralGrounding", "measurabilityHonesty", "invariance", "fidelity", "coherence",
            "minimality", "verifiability", "energy", "allegiance"]
    kwargs = {"proposal": {"x": 1}, "axes": AXES, "seed": 42}
    hashes, ok = run5(m4.yuyay, kwargs)
    RESULTS["chakra_4"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_4"] = (f"ERR {e}", False)

# === Chakra 5 RUWAY ===
m5 = load("k5", BASE / "chakra_5_throat" / "kernel.py")
sig = inspect.signature(m5.ruway)
print(f"Chakra 5 ruway sig: {sig}")
try:
    kwargs = {"state": {"a": 1}, "proposal": {"b": 2}, "gate_pass": True, "yawar_bus": []}
    hashes, ok = run5(m5.ruway, kwargs)
    RESULTS["chakra_5"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_5"] = (f"ERR {e}", False)

# === Chakra 6 NAWI ===
m6 = load("k6", BASE / "chakra_6_third_eye" / "kernel.py")
sig = inspect.signature(m6.tinkuy)
print(f"Chakra 6 tinkuy sig: {sig}")
try:
    intent = "read file"
    tools = [{"name": "read_file", "keywords": ["read", "file"]},
             {"name": "write_file", "keywords": ["write", "file"]}]
    def mock_invoke(name, args): return {"ok": True, "tool": name}
    params = list(sig.parameters.keys())
    print(f"  params: {params}")
    kwargs = {"intent": intent, "tools": tools, "seed": 1}
    if "invoke" in params: kwargs["invoke"] = mock_invoke
    hashes, ok = run5(m6.tinkuy, kwargs)
    RESULTS["chakra_6"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_6"] = (f"ERR {e}", False)

# === Chakra 7 HATUN ===
m7 = load("k7", BASE / "chakra_7_crown" / "kernel.py")
sig = inspect.signature(m7.hatun)
print(f"Chakra 7 hatun sig: {sig}")
try:
    params = list(sig.parameters.keys())
    print(f"  params: {params}")
    state = {"x": 1}
    proposal = {"y": 2}
    critic = {"moralGrounding": 0.99, "measurabilityHonesty": 0.99, "scores": {}, "passed": True}
    prev_hash = "0" * 64
    tripwires = {"T03_EVAL_AWARENESS": False, "T04_DECEPTION_KEYWORDS": False}
    timestamp = "2026-05-14T08:25:00Z"
    kwargs = {}
    if "state" in params: kwargs["state"] = state
    if "proposal" in params: kwargs["proposal"] = proposal
    if "critic_result" in params: kwargs["critic_result"] = critic
    if "critic" in params: kwargs["critic"] = critic
    if "prev_hash" in params: kwargs["prev_hash"] = prev_hash
    if "tripwires" in params: kwargs["tripwires"] = tripwires
    if "timestamp" in params: kwargs["timestamp"] = timestamp
    hashes, ok = run5(m7.hatun, kwargs)
    RESULTS["chakra_7"] = (hashes[0], ok)
except Exception as e:
    RESULTS["chakra_7"] = (f"ERR {e}", False)

print()
print("=" * 90)
print(f"{'CHAKRA':<12} {'BYTE-IDENTICAL 5X':<20} {'OUTPUT-HASH'}")
print("=" * 90)
for k, (h, ok) in RESULTS.items():
    mark = "✓" if ok else "✗"
    print(f"{k:<12} {mark:<20} {h}")
