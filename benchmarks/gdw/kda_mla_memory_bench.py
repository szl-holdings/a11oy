"""Measure allocated KDA recurrent state and MLA latent KV memory."""

import argparse
import gc
import json
from datetime import datetime, timezone
from pathlib import Path


def bytes_of(*tensors):
    return sum(
        tensor.numel() * tensor.element_size()
        for tensor in tensors
        if tensor is not None
    )


def resolve_device(torch, requested):
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but torch.cuda.is_available() is false")
    return requested


def measure_once(torch, batch, seq, d_model, n_heads, d_latent, device):
    dtype = torch.float16 if device == "cuda" else torch.float32
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    latent_k = torch.empty(batch, seq, d_latent, device=device, dtype=dtype)
    latent_v = torch.empty(batch, seq, d_latent, device=device, dtype=dtype)
    if device == "cuda":
        torch.cuda.synchronize()
        mla_peak = torch.cuda.max_memory_allocated()
    else:
        mla_peak = bytes_of(latent_k, latent_v)
    mla_bytes = bytes_of(latent_k, latent_v)
    del latent_k, latent_v
    gc.collect()

    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    head_dim = d_model // n_heads
    state = torch.empty(
        batch, n_heads, head_dim, head_dim, device=device, dtype=dtype
    )
    if device == "cuda":
        torch.cuda.synchronize()
        kda_peak = torch.cuda.max_memory_allocated()
    else:
        kda_peak = bytes_of(state)
    kda_bytes = bytes_of(state)
    del state
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    return {
        "batch": batch,
        "seq": seq,
        "d_model": d_model,
        "n_heads": n_heads,
        "d_latent": d_latent,
        "dtype": str(dtype),
        "device": device,
        "mla_bytes": mla_bytes,
        "kda_bytes": kda_bytes,
        "mla_peak_allocated_bytes": int(mla_peak),
        "kda_peak_allocated_bytes": int(kda_peak),
        "mla_bytes_per_token": mla_bytes / (batch * seq),
        "kda_bytes_per_session": kda_bytes / batch,
    }


def main(args):
    import torch

    device = resolve_device(torch, args.device)
    rows = []
    for batch in args.batches:
        for seq in args.sequences:
            try:
                row = measure_once(
                    torch,
                    batch,
                    seq,
                    args.d_model,
                    args.n_heads,
                    args.d_latent,
                    device,
                )
                row["status"] = "MEASURED"
            except RuntimeError as exc:
                row = {
                    "batch": batch,
                    "seq": seq,
                    "device": device,
                    "status": "OOM"
                    if "out of memory" in str(exc).lower()
                    else "ERROR",
                    "error": type(exc).__name__,
                }
                if device == "cuda":
                    torch.cuda.empty_cache()
            rows.append(row)

    metadata = {
        "schema": "szl.gdw.kda-mla-memory/v1",
        "label": "MEASURED",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "torch_version": torch.__version__,
        "device": device,
        "device_name": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(str(output.resolve()))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batches", nargs="+", type=int, default=[1, 4, 8, 16])
    parser.add_argument(
        "--sequences", nargs="+", type=int, default=[1024, 4096, 16384]
    )
    parser.add_argument("--d-model", type=int, default=1024)
    parser.add_argument("--n-heads", type=int, default=16)
    parser.add_argument("--d-latent", type=int, default=128)
    parser.add_argument(
        "--output", default="output/bench_results/gdw_kda_mla_memory.json"
    )
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
