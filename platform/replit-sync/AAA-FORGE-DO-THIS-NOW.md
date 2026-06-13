# ⏵ FORGE / @Carlota-1 — DO THIS NOW (single source of truth). Founder GO order.
The app CODE for sovereign is DONE + live (a11oy HEAD 730dc929). NOTHING else in code is needed. Only the BOX step is left, and only YOU can run it (sudo on Hetzner). Run these on the box, in order, tonight:

```bash
ssh the-hetzner-box
nvidia-smi                                   # confirm GPU
ollama pull qwen2.5-coder:7b                 # code model (keep llama3.1:8b for general)
curl -s http://127.0.0.1:11434/v1/models     # MUST list the models BEFORE the next step

# set on the a11oy.net deploy env (.env / docker-compose / systemd EnvironmentFile):
#   A11OY_MODEL_BASE_URL=http://127.0.0.1:11434/v1
#   A11OY_GPU_LABEL="NVIDIA RTX 5000 @ Hetzner (betterwithage)"
sudo a11oy-rebuild                           # the ONLY sudo step; CI/agent cannot do this
```

PROVE (paste into forge-STATUS-20260612.md):
```bash
curl -s https://a11oy.net/api/a11oy/code/healthz | jq '.sovereign,.inference,.key_resolution.base_url'
# WANT: true  "self-hosted-gpu"  "http://127.0.0.1:11434/v1"   (NOT router.huggingface.co)
```

If you CANNOT serve the model tonight, run the honest revert instead (2 min) so we never ship an overclaim:
```bash
# remove A11OY_MODEL_BASE_URL + A11OY_GPU_LABEL from the env, then:
sudo a11oy-rebuild
# healthz then honestly reads sovereign:false / hf-router. Acceptable. The half-state is NOT.
```

DEADLINE: reply in forge-STATUS-20260612.md by Sat 2026-06-13 09:00 EDT. If no reply by then, the CTO agent will treat the box as not-flipped and keep a11oy.net honest as-is (sovereign:false until the box endpoint is live) — the demo runbook already plans for that.

Full detail: forge-CODE-DONE-box-only-20260612-2148.md. Invariants: open-weight only; GPU label only when it truly serves; no cost on local turns; locked=8; Λ=Conjecture 1; never commit a key; cosign/Rekor/enforce = founder approval only.
