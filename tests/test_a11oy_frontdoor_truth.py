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


if __name__ == "__main__":
    unittest.main()
