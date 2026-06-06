import numpy as np  # line 1


def yachay(query, codex_store, pirwa_store, k=3, seed=42):  # line 2
    rng = np.random.default_rng(seed)  # line 3
    q = rng.standard_normal(len(next(iter(pirwa_store.values()))))  # line 4
    scores_p = {f: float(np.dot(q, v) / (np.linalg.norm(q)*np.linalg.norm(v)+1e-9)) for f,v in pirwa_store.items()}  # line 5
    top_k_features = sorted(scores_p, key=scores_p.get, reverse=True)[:k]  # line 6
    scores_c = {p: float(np.dot(q, v) / (np.linalg.norm(q)*np.linalg.norm(v)+1e-9)) for p,v in codex_store.items()}  # line 7
    codex_priors = sorted(scores_c, key=scores_c.get, reverse=True)[:8]  # line 8
    return top_k_features, codex_priors  # line 9
