# export_to_ollama.ps1 — Stage-B: LoRA adapter -> GGUF (q4_k_m) -> ollama create
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
#
# WHAT THIS DOES (honest, Doctrine v11):
#   Takes the REAL LoRA adapter trained by train_lora.py and:
#     1. Converts the PEFT adapter dir -> a GGUF LoRA adapter with llama.cpp's
#        convert_lora_to_gguf.py (outtype q8_0 by default; the ADAPTER is tiny,
#        so we keep it high-precision — the q4_k_m in the tag refers to the
#        BASE model quantization that llama3.1:8b already ships at in Ollama).
#     2. Copies it next to Modelfile.adapter as szl-lora-q4_k_m.gguf.
#     3. Runs `ollama create llama3-szl-finetuned-q4 -f Modelfile.adapter`,
#        which REPLACES Stage A under the SAME tag with the adapter applied.
#
#   This does NOT train anything and does NOT fabricate weights: if the adapter
#   dir or llama.cpp converter is missing, it fails LOUD (UNAVAILABLE), never
#   silently produces a model-less tag.
#
# Λ = Conjecture 1 (advisory). The exported model is a MODELED artifact.
#
# RUN (from the Tower, PowerShell, inside sovereign-weights/):
#   powershell -ExecutionPolicy Bypass -File .\export_to_ollama.ps1 `
#       -AdapterDir .\out-lora-szl `
#       -LlamaCpp   $env:USERPROFILE\llama.cpp
#
# PREREQS: ollama installed + `ollama pull llama3.1:8b` done; a llama.cpp
# checkout with convert_lora_to_gguf.py; python on PATH with gguf/torch/safetensors.

[CmdletBinding()]
param(
    # The PEFT LoRA adapter directory written by train_lora.py (--output-dir).
    [string]$AdapterDir = ".\out-lora-szl",
    # A llama.cpp checkout containing convert_lora_to_gguf.py.
    [string]$LlamaCpp = "$env:USERPROFILE\llama.cpp",
    # Ollama model tag to (re)create — SAME tag as Stage A on purpose.
    [string]$Tag = "llama3-szl-finetuned-q4",
    # Modelfile that carries FROM + ADAPTER + SYSTEM.
    [string]$Modelfile = ".\Modelfile.adapter",
    # GGUF adapter output name (must match the ADAPTER line in the Modelfile).
    [string]$OutGguf = ".\szl-lora-q4_k_m.gguf",
    # Adapter precision. q8_0 keeps the small adapter near-lossless; the base
    # stays at Ollama's shipped llama3.1:8b quant.
    [string]$OutType = "q8_0"
)

$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
    Write-Host "[UNAVAILABLE] $msg" -ForegroundColor Red
    Write-Host "  Refusing to create a model-less or fabricated tag. Fix the above and re-run." -ForegroundColor Red
    exit 2
}

Write-Host "== Stage-B export: LoRA adapter -> GGUF -> ollama create (Doctrine v11, honest) ==" -ForegroundColor Cyan

# --- Preflight (fail loud, never fabricate) ----------------------------------
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Fail "ollama is not on PATH. Install Ollama and run 'ollama pull llama3.1:8b' first."
}
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $python) { Fail "python is not on PATH (needed by llama.cpp's converter)." }

if (-not (Test-Path $AdapterDir)) {
    Fail "adapter dir '$AdapterDir' not found. Run train_lora.py first (Stage B is REAL training)."
}
$adapterWeights = Join-Path $AdapterDir "adapter_model.safetensors"
$adapterCfg = Join-Path $AdapterDir "adapter_config.json"
if (-not (Test-Path $adapterCfg)) {
    Fail "no adapter_config.json in '$AdapterDir' — that is not a PEFT LoRA adapter dir."
}
if (-not (Test-Path $adapterWeights)) {
    Write-Host "  note: adapter_model.safetensors not found; checking for adapter_model.bin ..." -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $AdapterDir "adapter_model.bin"))) {
        Fail "no adapter weights (safetensors/bin) in '$AdapterDir'. Training did not complete."
    }
}

$converter = Join-Path $LlamaCpp "convert_lora_to_gguf.py"
if (-not (Test-Path $converter)) {
    Fail "convert_lora_to_gguf.py not found under '$LlamaCpp'. Clone llama.cpp (ggml-org/llama.cpp)."
}

if (-not (Test-Path $Modelfile)) {
    Fail "Modelfile '$Modelfile' not found (expected Modelfile.adapter next to this script)."
}

# --- 1. Convert PEFT LoRA adapter -> GGUF adapter -----------------------------
Write-Host "[1/3] Converting LoRA adapter -> GGUF ($OutType) via llama.cpp ..." -ForegroundColor Cyan
# --base is required so the converter can resolve tensor shapes; point it at the
# base tag's HF id or a local base dir. We pass the HF id used at train time.
$baseModel = "meta-llama/Meta-Llama-3.1-8B-Instruct"
& $python.Source $converter $AdapterDir --base $baseModel --outtype $OutType --outfile $OutGguf
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $OutGguf)) {
    Fail "convert_lora_to_gguf.py failed (exit $LASTEXITCODE) — no GGUF adapter written."
}
$sz = "{0:N1}" -f ((Get-Item $OutGguf).Length / 1MB)
Write-Host "      wrote $OutGguf ($sz MB)" -ForegroundColor Green

# --- 2. Sanity: base tag present in Ollama ------------------------------------
Write-Host "[2/3] Verifying base tag 'llama3.1:8b' is pulled in Ollama ..." -ForegroundColor Cyan
$have = (& ollama list) 2>$null | Select-String -SimpleMatch "llama3.1:8b"
if (-not $have) {
    Fail "base 'llama3.1:8b' not found in Ollama. Run 'ollama pull llama3.1:8b' first (adapter base MUST match)."
}

# --- 3. ollama create: REPLACE Stage A under the SAME tag ---------------------
Write-Host "[3/3] ollama create $Tag -f $Modelfile  (replaces Stage A under the SAME tag) ..." -ForegroundColor Cyan
& ollama create $Tag -f $Modelfile
if ($LASTEXITCODE -ne 0) {
    Fail "ollama create failed (exit $LASTEXITCODE). Tag '$Tag' NOT updated — Stage A left intact."
}

Write-Host ""
Write-Host "== DONE: '$Tag' is now Stage B (FINE-TUNED: LoRA adapter over llama3.1:8b). ==" -ForegroundColor Green
Write-Host "  Honest label change: SYSTEM-PROMPT DERIVATIVE (Stage A) -> FINE-TUNED (Stage B)." -ForegroundColor Green
Write-Host "  Smoke test: ollama run $Tag ""State your doctrine in one line.""" -ForegroundColor Green
Write-Host "  The a11oy sovereign backend keeps routing to the SAME tag — no registry change needed." -ForegroundColor Green
