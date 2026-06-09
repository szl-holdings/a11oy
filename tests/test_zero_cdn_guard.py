"""
test_zero_cdn_guard.py — DEV-WIRE-A (2026-06-09)

Doctrine guard: the operator console + every vendored JS asset MUST be 0 runtime CDN.
All third-party libraries are vendored in-image under static-vendor/ and referenced with
relative `<script src="/vendor/...">` tags only. This test FAILS the build if any banned
CDN host string appears in a served HTML or JS file, or if any <script>/<link> references
an absolute http(s) origin.

ADDITIVE + SAFE: this only ADDS a gate; it never weakens an existing one.
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Banned runtime-CDN host fragments (case-insensitive). A real vendored 0-CDN build
# must not contain any of these inside a served HTML/JS file.
BANNED = [
    "cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "cdn.skypack.dev",
    "esm.sh", "ajax.googleapis.com", "fonts.googleapis.com", "fonts.gstatic.com",
    "code.jquery.com", "stackpath.bootstrapcdn.com", "maxcdn.bootstrapcdn.com",
    "d3js.org/d3", "threejs.org/build", "cdn.plot.ly",
]

# Files that are SERVED to the browser and therefore must be 0-CDN.
SERVED_GLOBS = [
    "pages/console.html",
    "console/*.html",
    "static-vendor/*.js",
    "static-vendor/*.css",
]

# Absolute external ASSET loads are forbidden in served HTML: <script src="http(s)://...">
# and stylesheet <link ... href="http(s)://...">. Plain <a href> navigation links to our
# own HF Space / canonical origin are NOT asset loads and are allowed.
EXT_SCRIPT = re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']https?://', re.IGNORECASE)
EXT_STYLESHEET = re.compile(r'<link\b[^>]*\bhref\s*=\s*["\']https?://[^>]*>', re.IGNORECASE)


def _served_files():
    out = []
    for g in SERVED_GLOBS:
        out.extend(sorted(ROOT.glob(g)))
    return out


def test_no_banned_cdn_host_in_served_files():
    offenders = []
    for f in _served_files():
        try:
            txt = f.read_text(errors="ignore")
        except Exception:
            continue
        low = txt.lower()
        for host in BANNED:
            if host in low:
                offenders.append(f"{f.relative_to(ROOT)} :: {host}")
    assert not offenders, "Runtime-CDN host string(s) found in served files:\n" + "\n".join(offenders)


def test_no_absolute_external_asset_load_in_html():
    """No <script src=http(s)> or external stylesheet <link href=http(s)>. Navigation
    <a href> links to our own origin are allowed (not asset loads)."""
    offenders = []
    for f in _served_files():
        if f.suffix.lower() != ".html":
            continue
        try:
            txt = f.read_text(errors="ignore")
        except Exception:
            continue
        for rx, kind in ((EXT_SCRIPT, "script"), (EXT_STYLESHEET, "stylesheet")):
            for m in rx.finditer(txt):
                # a <link> is only an asset load if it is rel=stylesheet/preload/modulepreload
                tag = m.group(0).lower()
                if kind == "stylesheet" and not re.search(r'rel\s*=\s*["\']?(stylesheet|preload|modulepreload)', tag):
                    continue
                snippet = txt[max(0, m.start() - 10):m.start() + 70].replace("\n", " ")
                offenders.append(f"{f.relative_to(ROOT)} :: [{kind}] …{snippet}…")
    assert not offenders, "Absolute external asset load in served HTML (must be relative, 0-CDN):\n" + "\n".join(offenders)


def test_anvaka_vendor_files_present_and_real():
    """The vendored anvaka graph stack must exist in-image and be real JS (not LFS/404)."""
    required = [
        "static-vendor/ngraph.graph.min.js",
        "static-vendor/ngraph.forcelayout.min.js",
        "static-vendor/ngraph.path.min.js",
        "static-vendor/panzoom.min.js",
        "static-vendor/vivagraph.min.js",
        "static-vendor/ngraph.events.umd.js",
    ]
    for rel in required:
        f = ROOT / rel
        assert f.is_file(), f"missing vendored lib: {rel}"
        head = f.read_bytes()[:80].lstrip()
        # LFS pointer files start with 'version https://git-lfs'; real JS never does.
        assert not head.startswith(b"version https://git-lfs"), f"{rel} is an LFS pointer, not real JS"
        assert f.stat().st_size > 1500, f"{rel} suspiciously small ({f.stat().st_size} bytes)"
