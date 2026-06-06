import hashlib  # line 1
import json


# CH'ULLA-HATUN L7 crown kernel — ours; no upstream absorption.  # line 2
# Continuum hash: sha256 chain over (prev_hash, state, proposal, critic, timestamp).  # line 3
# HUKLLA 10 tripwires: T01-T10 from D45. Any trip → allegiance_pass=False, state frozen.  # line 4
# timestamp is caller-supplied (ISO string) for byte-identical 5× replay.  # line 5
def hatun(state, proposal, critic_result, prev_hash, tripwires, timestamp):  # line 6
    tripped = [t for t in tripwires if t["fired"]]  # line 7
    blob = json.dumps([prev_hash, state, proposal, critic_result, timestamp], sort_keys=True, default=str).encode()  # line 8
    continuum_hash = hashlib.sha256(blob).hexdigest()  # line 9
    return continuum_hash, len(tripped) == 0  # line 10
