import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "checker", ROOT / "scripts/check_a11oy_frontdoor_truth.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOOD = '''<!doctype html><style>
.mono{overflow-wrap:anywhere}.btn{min-height:44px}
.hero{position:relative;min-height:92vh}
.hero .wrap{position:relative;z-index:2;padding-top:54px}
.cta-row{display:flex;gap:12px}
section.band{padding:88px 0;position:relative}
/* Mobile overrides intentionally follow all equal-specificity base rules. */
@media(max-width:560px){.hero{min-height:auto}.cta-row{display:grid}}
</style>
<section class="band" id="ecosystem"><a class="estate-cell"><b>OPEN</b><span>Models</span></a></section>
<script>function lamChip(elId, v){ const relation="advisory"; return grayChip(relation + " · CONJECTURE"); }</script>
<div class="cl">Receipt records · signer state separate</div>
<div>Signer state is disclosed separately only where an actual signer-status read is present.</div>
'''


class ContractTests(unittest.TestCase):
    def write(self, text: str):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "a11oy_landing.html"
        path.write_text(text, encoding="utf-8")
        return td, path

    def test_good(self):
        td, path = self.write(GOOD)
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "PASS")

    def test_rejects_unconditional_signing(self):
        td, path = self.write(GOOD + "Every answer arrives with a signed receipt")
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_numeric_estate(self):
        bad = GOOD.replace(
            '<a class="estate-cell"><b>OPEN</b><span>Models</span></a>',
            '<div class="estate-cell"><b>15</b><span>Models</span></div>',
        )
        td, path = self.write(bad)
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_green_lambda(self):
        bad = GOOD.replace(
            'const relation="advisory"; return grayChip(relation + " · CONJECTURE");',
            'const pass = v >= 0.90; return liveChip(pass);',
        )
        td, path = self.write(bad)
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_mobile_override_before_base_rules(self):
        marker = "/* Mobile overrides intentionally follow all equal-specificity base rules. */\n@media(max-width:560px){.hero{min-height:auto}.cta-row{display:grid}}\n"
        bad = GOOD.replace(marker, "").replace(
            ".hero{position:relative;min-height:92vh}\n",
            marker + ".hero{position:relative;min-height:92vh}\n",
        )
        td, path = self.write(bad)
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_unmeasured_signer_in_measured_legend(self):
        bad = GOOD + "receipt count, separately reported signer state, advisory Λ posture"
        td, path = self.write(bad)
        self.addCleanup(td.cleanup)
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def write_owned(self, html: str | None = None, css: str | None = None):
        td, path = self.write(html if html is not None else (ROOT / "a11oy_landing.html").read_text(encoding="utf-8"))
        self.addCleanup(td.cleanup)
        sheet = path.parent / "console/assets/a11oy-homepage.css"
        sheet.parent.mkdir(parents=True)
        sheet.write_text(css if css is not None else (ROOT / "console/assets/a11oy-homepage.css").read_text(encoding="utf-8"), encoding="utf-8")
        return path, sheet

    def test_accepts_exact_local_canonical_owner(self):
        path, _ = self.write_owned()
        self.assertEqual(mod.check(path)["status"], "PASS")

    def test_rejects_missing_remote_or_ambiguous_visual_owner(self):
        html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        owner = '<link rel="stylesheet" href="/assets/a11oy-homepage.css?v=61c132098e06" id="szl-homepage-shell" />'
        for replacement in ("", owner + owner, owner.replace("/assets/a11oy-homepage.css", "https://example.invalid/page.css"), owner.replace("/assets/a11oy-homepage.css", "../../outside.css")):
            with self.subTest(replacement=replacement):
                path, _ = self.write_owned(html.replace(owner, replacement))
                self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_unavailable_or_symlinked_owned_sheet(self):
        path, sheet = self.write_owned()
        sheet.unlink()
        self.assertEqual(mod.check(path)["status"], "FAIL")
        sheet.symlink_to(ROOT / "console/assets/a11oy-homepage.css")
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_canonical_sheet_after_page_owner(self):
        html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        canonical = '<link rel="stylesheet" href="/assets/szl/szl-design-system.css" data-szl-design="kanchay" />'
        path, _ = self.write_owned(html.replace(canonical, "").replace("</head>", canonical + "</head>"))
        self.assertEqual(mod.check(path)["status"], "FAIL")

    def test_rejects_shrunken_targets_clipping_palette_forks_and_lost_fallbacks(self):
        css = (ROOT / "console/assets/a11oy-homepage.css").read_text(encoding="utf-8")
        mutations = (
            css.replace("min-height:52px", "min-height:20px"),
            css.replace("overflow:visible !important", "overflow:hidden !important"),
            css.replace("@media(prefers-reduced-motion:reduce)", "@media print"),
            css.replace("@media(forced-colors:active)", "@media print"),
            css.replace("var(--action-press-bg)", "var(--accent)"),
            css + "\nbody{color:#ffff00}",
        )
        for changed in mutations:
            with self.subTest(change=mutations.index(changed)):
                path, _ = self.write_owned(css=changed)
                self.assertEqual(mod.check(path)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
