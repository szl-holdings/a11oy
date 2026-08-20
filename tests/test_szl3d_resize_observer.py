"""Static lifecycle guards for the shared SZL3D renderer resize path."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "static" / "3d" / "szl3d" / "szl3d_boot.js"


def _boot() -> str:
    return BOOT.read_text(encoding="utf-8")


def test_renderer_observes_the_canvas_host_and_coalesces_layout_resizes():
    src = _boot()
    assert "new ResizeObserver(_queueObservedSize)" in src
    assert "_resizeObserver.observe(host)" in src
    assert "if (_disposed || _observerRaf) return" in src
    assert '_observerRaf = requestAnimationFrame(() =>' in src
    assert "w === _lastWidth && h === _lastHeight" in src
    assert "renderer.setSize(w, h, false)" in src
    assert "camera.aspect = w / h" in src
    assert "camera.updateProjectionMatrix()" in src


def test_renderer_resize_observer_is_optional_and_disposed_cleanly():
    src = _boot()
    assert 'window.addEventListener("resize", _size)' in src
    assert 'window.removeEventListener("resize", _size)' in src
    assert 'typeof ResizeObserver !== "undefined"' in src
    assert "_resizeObserver.disconnect()" in src
    assert "cancelAnimationFrame(_observerRaf)" in src
    assert "_disposed = true" in src
