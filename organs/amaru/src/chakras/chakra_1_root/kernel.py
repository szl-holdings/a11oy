import math
import random

# KALLPA L1 dispatch — distilled from tinygrad/device.py lines 39-54 (MIT, tinygrad/tinygrad)
# NINA Butler-Volmer: i = i0*(exp(α·F·η/RT) - exp(-(1-α)·F·η/RT)); min-energy path wins
PATHS = ["CPU", "GPU", "QUANTIZED", "MOE"]
nina = lambda η,α=0.5,F=96485,RT=2478.96,i0=1e-6: abs(i0*(math.exp(α*F*η/RT)-math.exp(-(1-α)*F*η/RT)))
def dispatch(state, world, seed=0):
    rng = random.Random(seed)
    costs = {p: nina(rng.gauss(world.get(p, 0.0), 0.01)) for p in PATHS}
    chosen = min(costs, key=costs.__getitem__)
    return chosen, costs[chosen]
