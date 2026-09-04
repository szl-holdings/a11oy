from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
SERVE = ROOT / "serve.py"

MODEL_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
MODEL_FILE = "SZL-Khipu-1.5B-Q4_K_M.gguf"
MODEL_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
MODEL_SIZE = "986047904"
NEMO_REVISION = "810231a531188bb569e3faa17396386eb0a5e260"
WHEEL = "llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
WHEEL_SHA256 = "d172f3d3c8cdd194c3c47c71cb077ed6e61354a2d0f939ceeac0c8fd29999596"


def test_dockerfile_uses_pinned_prebuilt_cpu_wheel_not_source_compile() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG A11OY_REQUIRE_LOCAL_LLM=1" in text
    assert WHEEL in text
    assert WHEEL_SHA256 in text
    assert "pip wheel --no-cache-dir --no-binary llama-cpp-python" not in text
    builder = text.split("FROM llama-build-${A11OY_REQUIRE_LOCAL_LLM} AS llama-build", 1)[0]
    for forbidden in ("build-essential", "cmake", "ninja-build"):
        assert forbidden not in builder


def test_dockerfile_fetches_only_exact_owned_khipu_q4_artifact() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    for expected in (
        f"ARG A11OY_ALLOY_GGUF_REPO={MODEL_REPO}",
        f"ARG A11OY_ALLOY_GGUF_FILE={MODEL_FILE}",
        f"ARG A11OY_ALLOY_GGUF_REV={MODEL_REVISION}",
        f"ARG A11OY_ALLOY_GGUF_SHA256={MODEL_SHA256}",
        f"ARG A11OY_ALLOY_GGUF_SIZE={MODEL_SIZE}",
        f"A11OY_ALLOY_GGUF=/app/models/{MODEL_FILE}",
        f"A11OY_KHIPU_GGUF=/app/models/{MODEL_FILE}",
    ):
        assert expected in text
    assert "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF" not in text


def test_image_installs_exact_nemo_and_copies_cortex() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert f"szl-nemo/archive/{NEMO_REVISION}.tar.gz" in text
    assert "a11oy_governed_cortex.py" in text
    assert re.search(
        r"COPY .*a11oy_governed_cortex\.py.*\./",
        text,
    )


def test_cortex_registers_after_brain_and_before_spa_catchall() -> None:
    text = SERVE.read_text(encoding="utf-8")
    brain = text.index("import szl_brain_api as _szl_brain_api")
    cortex = text.index("import a11oy_governed_cortex as _a11oy_governed_cortex")
    catchall = text.index('@app.get("/{full_path:path}")')
    assert brain < cortex < catchall
    assert "_a11oy_governed_cortex.register(app, ns=\"a11oy\")" in text
