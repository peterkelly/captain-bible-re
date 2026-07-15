import hashlib
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive, DD1FormatError  # noqa: E402


class DD1ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")

    def test_directory_regression(self):
        self.assertEqual(len(self.archive.entries), 369)
        self.assertEqual(self.archive.entries[0].offset, 0x229A)
        run = self.archive.matching("run.art")
        self.assertEqual(len(run), 1)
        self.assertEqual(run[0].offset, 0x6F69C)
        self.assertEqual(run[0].expanded_size, 53213)
        self.assertEqual(run[0].stored_size, 16138)

    def test_every_member_extracts_to_declared_size(self):
        for entry in self.archive.entries:
            with self.subTest(index=entry.index, filename=entry.filename):
                self.assertEqual(
                    len(self.archive.extract(entry)), entry.expanded_size
                )

    def test_run_art_regression(self):
        entry = self.archive.matching("RUN.ART")[0]
        extracted = self.archive.extract(entry)
        self.assertEqual(
            hashlib.sha256(extracted).hexdigest(),
            "c4b00d2e31e9dec81cc419dc577086b143a546a4a0b618dbe5600df4e5fd4ac0",
        )

    def test_logo_bin_regression(self):
        entry = self.archive.matching("LOGO.BIN")[0]
        extracted = self.archive.extract(entry)
        self.assertEqual(
            hashlib.sha256(extracted).hexdigest(),
            "8580d3ff93c6e775aa71334c50762ffde2b1f42a320ee362f5608bd8cbc51424",
        )

    def test_rejects_noncontiguous_member(self):
        data = bytearray()
        data += struct.pack("<H", 1)
        data += struct.pack("<8s4sIII", b"TEST", b"\0BIN", 27, 1, 3)
        data += b"GCx"
        with self.assertRaisesRegex(DD1FormatError, "starts at"):
            DD1Archive.from_bytes(bytes(data))


if __name__ == "__main__":
    unittest.main()
