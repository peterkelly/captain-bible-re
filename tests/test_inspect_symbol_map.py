from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from inspect_symbol_map import (  # noqa: E402
    SymbolMapError,
    load_catalog,
    parse_rizin_flags,
    parse_rizin_script,
    validate_catalog,
)


class SymbolMapTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(ROOT / "analysis" / "symbol-map.tsv")
        self.declarations = parse_rizin_script(ROOT / "analysis" / "cb.rz")

    def test_catalog_exactly_matches_rizin_names(self):
        validate_catalog(self.catalog, self.declarations)
        counts = {
            kind: sum(symbol.kind == kind for symbol in self.catalog)
            for kind in ("function", "handler", "data")
        }
        self.assertEqual(counts, {"function": 140, "handler": 134, "data": 9})

    def test_every_symbol_has_evidence_and_controlled_confidence(self):
        self.assertTrue(all(symbol.evidence for symbol in self.catalog))
        self.assertEqual(
            {symbol.confidence for symbol in self.catalog},
            {"verified", "high", "medium"},
        )

    def test_saved_rizin_flags_can_verify_handler_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flags.txt"
            path.write_text(
                "0x00004672 1 bin_handler_configure_study_prompt\n"
                "0x00000010 4 unrelated_flag\n",
                encoding="utf-8",
            )
            self.assertEqual(
                parse_rizin_flags(path),
                {(0x4672, "bin_handler_configure_study_prompt")},
            )

    def test_rejects_bad_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.tsv"
            path.write_text("name\toffset\nfoo\t0x10\n", encoding="utf-8")
            with self.assertRaisesRegex(SymbolMapError, "unexpected header"):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
