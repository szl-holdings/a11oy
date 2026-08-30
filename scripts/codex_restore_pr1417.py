#!/usr/bin/env python3
"""Three-way inverse merge for the stale-source overwrite in merged PR #1417.

Base is the bad #1417 result, ours is current protected-main-derived source, and
other is #1417's parent. This reapplies only the parent->bad inverse while
preserving later edits in conflict regions. It never pushes or mutates remotes.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

BAD = "37753ef139e79f595b54e4420796e24297501d6b"
GOOD = "f58d6cd2648ab2a7590674dc4678f85af95f4dc9"
FILES = (
    "a11oy_landing.html",
    "pages/console.html",
    "pages/landing.html",
    "serve.py",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def show(revision: str, path: str) -> bytes:
    return run("git", "show", f"{revision}:{path}").stdout


def merge_path(path: str) -> None:
    target = Path(path)
    current = target.read_bytes()
    base = show(BAD, path)
    other = show(GOOD, path)
    with tempfile.TemporaryDirectory(prefix="estate-v10-") as td:
        root = Path(td)
        ours_path = root / "current"
        base_path = root / "base"
        other_path = root / "other"
        ours_path.write_bytes(current)
        base_path.write_bytes(base)
        other_path.write_bytes(other)
        merged = run(
            "git",
            "merge-file",
            "--ours",
            "-p",
            str(ours_path),
            str(base_path),
            str(other_path),
            check=False,
        )
        if merged.returncode not in (0, 1):
            raise RuntimeError(
                f"merge-file failed for {path}: {merged.stderr.decode('utf-8', 'replace')}"
            )
        content = merged.stdout
        if b"<<<<<<<" in content or b">>>>>>>" in content or b"|||||||" in content:
            raise RuntimeError(f"unresolved conflict marker in {path}")
        target.write_bytes(content)


def repair_current_landing(path: Path) -> None:
    """Add the shared Command/Proof header and fail-closed Lean-8 loader.

    PR #1462 intentionally collapsed the product door to three flagships. Keep
    that information architecture and add only the command-bar contract lost by
    the stale #1417 overwrite.
    """
    text = path.read_text(encoding="utf-8")
    nav_open = '<nav class="nav-links" id="site-nav">'
    if nav_open not in text:
        raise RuntimeError("current flagship navigation anchor is missing")

    if '<a href="/console">Command</a>' not in text:
        shared_links = (
            '\n      <a href="/console">Command</a>'
            '\n      <a href="https://a11oy.net">Proof registry ↗</a>'
        )
        text = text.replace(nav_open, nav_open + shared_links, 1)

    if 'aria-label="Open the command center"' not in text:
        command_cta = (
            '\n      <a href="/console" class="btn nav-command-cta" '
            'aria-label="Open the command center">'
            '<span class="nav-cta-full">Open <span>Command center</span> →</span>'
            '<span class="nav-cta-short">Command</span></a>'
        )
        text = text.replace("</nav>", command_cta + "\n    </nav>", 1)

    if 'id="estate-v10-command-header-style"' not in text:
        style = (
            '\n<style id="estate-v10-command-header-style">'
            '.nav-command-cta{min-width:44px;min-height:44px}'
            '.nav-cta-short{display:none}'
            '@media(max-width:680px){.nav-cta-full{display:none}.nav-cta-short{display:inline}}'
            '</style>\n'
        )
        text = text.replace("</head>", style + "</head>", 1)

    if "function loadLockedKernel" not in text:
        loader = r'''
<script id="estate-v10-locked-kernel-loader">
function setCatalogNote(note){
  const el=document.getElementById('catalog-note')||document.querySelector('[data-catalog-note]');
  if(el) el.textContent=String(note);
}
async function loadLockedKernel(){
  try{
    const response=await fetch('/api/a11oy/v1/honest',{headers:{Accept:'application/json'}});
    if(!response.ok) throw new Error('honest endpoint '+response.status);
    const h=await response.json();
    const locked=(h&&h.locked_formula_count===8)?h.locked_formula_count:null;
    document.querySelectorAll('[data-locked-formula-count]').forEach(function(el){
      el.textContent=locked==null?'UNAVAILABLE':String(locked);
      el.dataset.state=locked==null?'unavailable':'reported';
    });
    setCatalogNote(locked==null
      ? 'UNAVAILABLE — /honest locked_formula_count did not verify exact Lean-8'
      : 'Lean kernel: '+locked+' locked formulas from /honest locked_formula_count; genome tiers remain catalog labels');
    return locked;
  }catch(error){
    setCatalogNote('UNAVAILABLE — exact Lean-8 evidence could not be read');
    return null;
  }
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',loadLockedKernel,{once:true});
}else{
  loadLockedKernel();
}
</script>
'''
        text = text.replace("</body>", loader + "\n</body>", 1)

    path.write_text(text, encoding="utf-8")


def repair_current_console(path: Path) -> None:
    """Restore the no-argument estate API while retaining force-refresh callers.

    The protected contract deliberately exposes `fetchHFEstate()` with no
    required parameters. Later source added an options parameter. Read that
    optional object through `arguments[0]` instead, preserving `{force:true}`
    calls without changing the public signature.
    """
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"async\s+function\s+fetchHFEstate\s*\([^)]*\)\s*\{",
        flags=re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one estate fetch declaration, found {len(matches)}"
        )
    replacement = (
        "async function fetchHFEstate() {\n"
        "  const { force = false } = "
        "(arguments[0] && typeof arguments[0] === 'object') ? arguments[0] : {};"
    )
    text = pattern.sub(replacement, text, count=1)
    path.write_text(text, encoding="utf-8")


def require(text: str, needle: str, path: str) -> None:
    if needle not in text:
        raise RuntimeError(f"restoration contract missing in {path}: {needle}")


def main() -> int:
    for path in FILES:
        merge_path(path)
    repair_current_landing(Path("a11oy_landing.html"))
    repair_current_console(Path("pages/console.html"))

    console = Path("pages/console.html").read_text(encoding="utf-8")
    landing = Path("a11oy_landing.html").read_text(encoding="utf-8")
    serve = Path("serve.py").read_text(encoding="utf-8")

    for needle in (
        '--teal:#3af4c8',
        'id="szl-series-a-cards"',
        'V.estate=',
        "go('investor')",
        "u.searchParams.set('view', view)",
        'Verify on a11oy.net',
        'function emptyUnknown(kind, detail)',
        'async function fetchHFEstate()',
        "typeof arguments[0] === 'object'",
        'locked_formula_count===8',
        'LOCKED-PROVEN (catalog)',
        '["Home"', '["Operate"', '["Build"', '["Observe"',
        '["Govern"', '["Research"', '["More"',
    ):
        require(console, needle, "pages/console.html")
    if "tier_counts['LOCKED-PROVEN']" in console:
        raise RuntimeError("console still binds kernel count to genome catalog")

    for needle in (
        '<a href="/console">Command</a>',
        'Proof registry ↗',
        'loadLockedKernel',
        'h.locked_formula_count',
        'setCatalogNote',
        'aria-expanded',
        'aria-label="Open the command center"',
        'class="nav-cta-short"',
        '>Command center</span> →',
    ):
        require(landing, needle, "a11oy_landing.html")

    for needle in (
        '"szl_command_bar.js": _VENDOR_JS_CT',
        '"szl_command_bar.css": _VENDOR_CSS_CT',
        'url="/console?view=investor"',
        'app.add_api_route("/investor"',
        'pages/estate.html',
        '"/estate"',
        'import a11oy_khipu_chat',
        '_resolve_llm_registry_module',
        'allow_methods=["GET", "HEAD", "POST", "OPTIONS"]',
        'if p == "/" or p == "/landing":',
        '_is_public_front',
    ):
        require(serve, needle, "serve.py")

    print("PR #1417 inverse three-way restoration contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
