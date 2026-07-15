from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools" / "setup_freedos_image.py"
SPEC = importlib.util.spec_from_file_location("setup_freedos_image", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def source_mbr() -> bytes:
    mbr = bytearray((index % 251 for index in range(setup.SECTOR_SIZE)))
    mbr[510:512] = setup.MBR_SIGNATURE
    return bytes(mbr)


class MbrValidationTests(unittest.TestCase):
    def test_accepts_valid_mbr_signature(self) -> None:
        setup.validate_mbr(source_mbr())

    def test_rejects_invalid_source_mbr(self) -> None:
        with self.assertRaises(setup.ImageBuildError):
            setup.validate_mbr(b"\x00" * setup.SECTOR_SIZE)


class PartitionedMbrTests(unittest.TestCase):
    IMAGE_SIZE = 1024 * 1024 * 1024

    def setUp(self) -> None:
        self.source = source_mbr()
        self.result = setup.partitioned_mbr(self.source, self.IMAGE_SIZE)
        self.entry = self.result[446:462]

    def test_preserves_source_boot_code(self) -> None:
        self.assertEqual(self.result[:446], self.source[:446])

    def test_marks_partition_active(self) -> None:
        self.assertEqual(self.entry[0], 0x80)

    def test_uses_fat16_lba_partition_type(self) -> None:
        self.assertEqual(self.entry[4], 0x0E)

    def test_starts_partition_at_lba_2048(self) -> None:
        self.assertEqual(struct.unpack_from("<I", self.entry, 8)[0], 2048)

    def test_partition_occupies_remaining_sectors(self) -> None:
        expected = self.IMAGE_SIZE // setup.SECTOR_SIZE - 2048
        self.assertEqual(struct.unpack_from("<I", self.entry, 12)[0], expected)


class ChsTests(unittest.TestCase):
    def test_encodes_chs_for_declared_geometry(self) -> None:
        self.assertEqual(setup.chs_address(2048), b"\x00\x21\x01")

    def test_saturates_out_of_range_chs(self) -> None:
        first_invalid_lba = (
            1024 * setup.DISK_HEADS * setup.DISK_SECTORS_PER_TRACK
        )
        self.assertEqual(setup.chs_address(first_invalid_lba), b"\xfe\xff\xff")


if __name__ == "__main__":
    unittest.main()
