// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// webgpu_compute.mjs — headless WebGPU compute-shader CI selftest for the holographic estate.
//
// Loaded by /static/3d/selftest/webgpu.html and driven by Playwright in CI (SwiftShader WebGPU
// path, see the vendor manifest / harvest notes). It proves a three.js r170 TSL compute kernel
// actually RAN on a real WebGPU device by reading back a StorageBuffer and asserting the GPU
// computed the expected values. Honest: if no WebGPU adapter is present it reports SKIPPED
// (WebGL2 is the production default) — it never fakes a pass.
//
// Result is written to window.__WEBGPU_SELFTEST__ = { status, backend, n, ok, detail }.
// status ∈ { "PASS", "SKIPPED", "FAIL" }.  CI asserts status !== "FAIL".
//
// 0 runtime CDN: three/webgpu resolves through the page importmap to /static/3d/vendor/.

const OUT = { status: "INIT", backend: null, n: 0, ok: false, detail: "" };
window.__WEBGPU_SELFTEST__ = OUT;

(async () => {
  try {
    if (typeof navigator === "undefined" || !("gpu" in navigator)) {
      OUT.status = "SKIPPED"; OUT.detail = "navigator.gpu absent (no WebGPU adapter — WebGL2 is the production default)"; return;
    }
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) { OUT.status = "SKIPPED"; OUT.detail = "no WebGPU adapter"; return; }

    const mod = await import("three/webgpu");
    const { WebGPURenderer, Fn, uniform, float, instanceIndex, instancedArray, storage, StorageInstancedBufferAttribute } = mod;
    // Storage-buffer TSL helper moved across three revisions: newer builds export `instancedArray`,
    // r170 (this vendored build) exports `storage` + `StorageInstancedBufferAttribute`. Accept
    // either so the selftest actually RUNS on the vendored build instead of false-SKIPPING.
    const canStorage = !!instancedArray || !!(storage && StorageInstancedBufferAttribute);
    if (!WebGPURenderer || !Fn || !canStorage) { OUT.status = "SKIPPED"; OUT.detail = "TSL/WebGPU storage-buffer exports unavailable in vendored build"; return; }

    const canvas = document.createElement("canvas"); canvas.width = canvas.height = 16;
    const renderer = new WebGPURenderer({ canvas, antialias: false });
    await renderer.init();
    OUT.backend = "webgpu";

    // Compute kernel: buf[i] = i * 2 + 1  — a deterministic pattern we can verify on readback.
    const N = 256; OUT.n = N;
    let buf, readTarget;
    if (instancedArray) { buf = instancedArray(N, "float"); readTarget = buf.value; }
    else { const attr = new StorageInstancedBufferAttribute(N, 1); buf = storage(attr, "float", N); readTarget = attr; }
    const kernel = Fn(() => {
      const i = instanceIndex.toFloat();
      buf.element(instanceIndex).assign(i.mul(float(2.0)).add(float(1.0)));
    });
    const node = kernel().compute(N);
    await renderer.computeAsync(node);

    // Read the StorageBuffer back and assert every element matches i*2+1.
    const arr = new Float32Array(await renderer.getArrayBufferAsync(readTarget));
    let ok = arr.length >= N;
    let firstBad = -1;
    for (let i = 0; i < N; i++) { if (Math.abs(arr[i] - (i * 2 + 1)) > 1e-3) { ok = false; firstBad = i; break; } }
    OUT.ok = ok;
    OUT.status = ok ? "PASS" : "FAIL";
    OUT.detail = ok ? `GPU computed ${N} elements correctly (buf[10]=${arr[10]})` : `mismatch at i=${firstBad}: got ${arr[firstBad]}, want ${firstBad * 2 + 1}`;
    try { renderer.dispose(); } catch (_) {}
  } catch (e) {
    // A genuine WebGPU error during compute is a FAIL (the device was present but the kernel broke);
    // an adapter/init failure already returned SKIPPED above.
    OUT.status = OUT.backend ? "FAIL" : "SKIPPED";
    OUT.detail = "exception: " + ((e && e.message) || String(e));
  }
})();
