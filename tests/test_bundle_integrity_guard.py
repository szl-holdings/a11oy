import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "check_bundle_integrity.py"
SPEC = importlib.util.spec_from_file_location("check_bundle_integrity", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bundle_integrity = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bundle_integrity
SPEC.loader.exec_module(bundle_integrity)


class BundleIntegrityGuardTests(unittest.TestCase):
    def test_candidate_static_template_literal_lazy_chunk_must_be_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            entry_name = "index-Cuo27aFU.js"
            lazy_name = "GovernedSecurityAgents-DoK12lCX.js"
            entry = assets / entry_name
            lazy = assets / lazy_name

            entry.write_text(
                "var route=()=>import(`./GovernedSecurityAgents-DoK12lCX.js`)"
                ".then(module=>({default:module.GovernedSecurityAgents}));",
                encoding="utf-8",
            )
            lazy.write_text(
                'import{r as runtime}from"./index-Cuo27aFU.js";'
                "export{runtime as GovernedSecurityAgents};",
                encoding="utf-8",
            )

            self.assertEqual((True, 2, {}), bundle_integrity.scan_dir(assets))

            lazy.unlink()
            self.assertEqual(
                (False, 1, {lazy_name: [entry_name]}),
                bundle_integrity.scan_dir(assets),
            )


if __name__ == "__main__":
    unittest.main()
