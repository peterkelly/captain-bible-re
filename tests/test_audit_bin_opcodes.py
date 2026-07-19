from pathlib import Path
from collections import defaultdict
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_bin_opcodes import (  # noqa: E402
    audit,
    cyclic_u8_reader_sites,
    format_report,
    load_static_analysis,
)
from inspect_bin import OPCODE_SCHEMAS  # noqa: E402


class BinOpcodeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable = ROOT / "build/analysis/CB_UNPACKED.EXE"
        if not cls.executable.exists():
            raise unittest.SkipTest("unpacked executable is not available")
        cls.rows = audit(
            cls.executable,
            ROOT / "CB/DD1.DAT",
            ROOT / "analysis/cb.rz",
            ROOT / "analysis/symbol-map.tsv",
        )

    def test_all_dispatch_entries_and_distinct_handlers_are_audited(self):
        self.assertEqual(len(self.rows), 145)
        self.assertEqual(len({row.handler for row in self.rows}), 134)
        self.assertEqual({row.opcode for row in self.rows}, set(range(1, 0x92)))

    def test_only_known_opcode_groups_share_implementations(self):
        by_handler = defaultdict(set)
        for row in self.rows:
            by_handler[row.handler].add(row.opcode)
        shared = {
            frozenset(opcodes)
            for opcodes in by_handler.values()
            if len(opcodes) > 1
        }
        self.assertEqual(
            shared,
            {
                frozenset({0x04, 0x43}),
                frozenset({0x0E, 0x4A, 0x4B, 0x56, 0x60}),
                frozenset({0x14, 0x48, 0x4E}),
                frozenset({0x17, 0x18, 0x19, 0x1A}),
                frozenset({0x4D, 0x6D}),
            },
        )

    def test_checked_report_matches_fresh_executable_and_corpus_audit(self):
        self.assertEqual(
            (ROOT / "analysis/opcode-audit.tsv").read_text(),
            format_report(self.rows),
        )

    def test_pointer_capable_and_inline_string_schemas_are_distinct(self):
        pointer_opcodes = {
            row.opcode for row in self.rows if "p" in OPCODE_SCHEMAS[row.opcode]
        }
        inline_opcodes = {
            row.opcode for row in self.rows if "z" in OPCODE_SCHEMAS[row.opcode]
        }
        self.assertEqual(
            pointer_opcodes, {0x0C, 0x10, 0x14, 0x3A, 0x44, 0x48, 0x4E}
        )
        self.assertEqual(inline_opcodes, {0x01, 0x0D, 0x4D, 0x6D})

    def test_inline_string_loops_are_found_independently_in_cfg(self):
        _, operations = load_static_analysis(
            self.executable, ROOT / "analysis/cb.rz"
        )
        self.assertEqual(
            cyclic_u8_reader_sites(operations),
            frozenset({0x4D8C, 0x4DA4, 0x4DE9, 0x540F}),
        )

    def test_only_dialogue_has_an_operand_free_retry_path(self):
        retrying = {
            row.opcode
            for row in self.rows
            if "" in row.static_paths and row.schema != "-"
        }
        self.assertEqual(retrying, {0x14, 0x48, 0x4E})

    def test_complete_corpus_counts_are_attached_to_audit(self):
        self.assertEqual(sum(row.uses for row in self.rows), 25_829)
        self.assertEqual(sum(row.uses > 0 for row in self.rows), 122)
        unused = {row.opcode for row in self.rows if row.uses == 0}
        self.assertEqual(
            unused,
            {
                0x03,
                0x0E,
                0x13,
                0x18,
                0x1B,
                0x2E,
                0x30,
                0x37,
                0x39,
                0x47,
                0x4A,
                0x4B,
                0x4F,
                0x50,
                0x56,
                0x5E,
                0x65,
                0x66,
                0x6E,
                0x6F,
                0x8B,
                0x8F,
                0x90,
            },
        )


if __name__ == "__main__":
    unittest.main()
