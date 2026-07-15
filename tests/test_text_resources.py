from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_text_resources import (  # noqa: E402
    TextFormatError,
    load_text_bank,
    parse_tagged_text,
    parse_verse_index,
)


class TextResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")

    def test_all_translation_banks_join_their_companion_files(self):
        counts = {}
        tagged_count = 0
        for translation in "TNRK":
            for bank_name in "ABCDEFG" + "R":
                bank = load_text_bank(
                    self.archive, ROOT / "CB", translation, bank_name
                )
                counts[bank_name] = len(bank.records)
                tagged_count += sum(len(record.tagged_text) for record in bank.records)
        self.assertEqual(
            counts,
            {
                "A": 47,
                "B": 40,
                "C": 46,
                "D": 46,
                "E": 42,
                "F": 46,
                "G": 44,
                "R": 8,
            },
        )
        self.assertEqual(tagged_count, 4 * 1057)

    def test_structural_headers_match_across_translations(self):
        for bank_name in "ABCDEFG" + "R":
            banks = [
                load_text_bank(self.archive, ROOT / "CB", translation, bank_name)
                for translation in "TNRK"
            ]
            expected = [
                (record.selector, record.data_offset, record.data_end)
                for record in banks[0].records
            ]
            for bank in banks[1:]:
                self.assertEqual(
                    [
                        (record.selector, record.data_offset, record.data_end)
                        for record in bank.records
                    ],
                    expected,
                )

    def test_duplicate_ng_members_are_identical(self):
        matches = [
            entry
            for entry in self.archive.entries
            if not entry.extension and entry.name == "NG"
        ]
        self.assertEqual([entry.index for entry in matches], [199, 206])
        self.assertEqual(self.archive.extract(matches[0]), self.archive.extract(matches[1]))

    def test_niv_bank_a_matches_qemu_export_regression(self):
        bank = load_text_bank(self.archive, ROOT / "CB", "N", "A")
        first = bank.records[0]
        self.assertEqual(first.selector, 0x31)
        self.assertEqual(first.citation, "Exodus 20:15")
        self.assertEqual(first.verse, "You shall not steal.")
        self.assertEqual(
            tuple(text.tag for text in first.tagged_text),
            ("L", "P", "W", "W", "W", "W", "C", "E"),
        )
        self.assertEqual(first.tagged_text[0].text, "If you want something, just take it.")

    def test_zero_length_companion_ranges_are_valid(self):
        bank = load_text_bank(self.archive, ROOT / "CB", "T", "F")
        self.assertEqual(bank.records[3].citation, "Psalms 119:105")
        self.assertEqual(bank.records[3].data_offset, bank.records[3].data_end)
        self.assertEqual(bank.records[3].tagged_text, ())

    def test_rejects_damaged_index_and_companion_records(self):
        entry = next(
            entry
            for entry in self.archive.entries
            if not entry.extension and entry.name == "TA"
        )
        data = self.archive.extract(entry)
        with self.assertRaisesRegex(TextFormatError, "terminal"):
            parse_verse_index(data + b"x")
        with self.assertRaisesRegex(TextFormatError, "pipe"):
            parse_verse_index(data.replace(b"|", b"/", 1))
        with self.assertRaisesRegex(TextFormatError, "unknown companion tag"):
            parse_tagged_text(b"Qbad\0", 0, 5)
        with self.assertRaisesRegex(TextFormatError, "unterminated"):
            parse_tagged_text(b"Lbad", 0, 4)


if __name__ == "__main__":
    unittest.main()
