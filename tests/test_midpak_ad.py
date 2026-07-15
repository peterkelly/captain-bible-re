from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from inspect_midpak_ad import MidpakAdFormatError, parse_midpak_ad  # noqa: E402


class MidpakAdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (ROOT / "CB" / "SOUND.4").read_bytes()

    def test_sound_4_directory_and_timbre_population(self):
        library = parse_midpak_ad(self.data)
        self.assertEqual(library.directory_end, 0x440)
        self.assertEqual(len(library.timbres), 181)
        self.assertEqual(len(library.melodic), 128)
        self.assertEqual(len(library.percussion), 53)
        self.assertEqual(
            [(item.patch, item.bank) for item in library.melodic],
            [(patch, 0) for patch in range(128)],
        )
        self.assertEqual(
            [(item.patch, item.bank) for item in library.percussion],
            [(patch, 0x7F) for patch in range(35, 88)],
        )

    def test_sound_4_records_are_contiguous_two_operator_timbres(self):
        library = parse_midpak_ad(self.data)
        self.assertTrue(all(item.length == 14 for item in library.timbres))
        self.assertEqual(library.timbres[0].offset, 0x440)
        self.assertEqual(library.timbres[-1].offset + 14, len(self.data))
        self.assertEqual(library.timbres[0].transpose, 0)
        self.assertEqual(library.timbres[0].modulator, bytes.fromhex("218ff24500"))
        self.assertEqual(library.timbres[0].feedback_connection, 8)
        self.assertEqual(library.timbres[0].carrier, bytes.fromhex("2106f27600"))

    def test_parser_rejects_missing_terminator_and_bad_length(self):
        with self.assertRaisesRegex(MidpakAdFormatError, "terminator"):
            parse_midpak_ad(self.data[:0x43E])
        damaged = bytearray(self.data)
        damaged[0x440:0x442] = (13).to_bytes(2, "little")
        with self.assertRaisesRegex(MidpakAdFormatError, "length"):
            parse_midpak_ad(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
