from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_bin import decode_stream  # noqa: E402
from inspect_map import (  # noqa: E402
    MapFormatError,
    compare_maps,
    load_archive_map,
    normalize_map_name,
    parse_map,
)
from inspect_save import parse_save_state  # noqa: E402


class MapResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")

    def test_archive_has_complete_level_difficulty_cross_product(self):
        names = {
            entry.name
            for entry in self.archive.entries
            if entry.extension == "MAP"
        }
        self.assertEqual(names, {level + mode for mode in "END" for level in "ABCDEFG"})
        for name in names:
            world_map = load_archive_map(self.archive, name)
            self.assertEqual(len(world_map.cells), 256)
            self.assertEqual(len(world_map.to_bytes()), 768)

    def test_grid_is_row_major_with_three_byte_cells(self):
        world_map = load_archive_map(self.archive, "CE")
        self.assertEqual(
            (world_map.cell(2, 0).packed, world_map.cell(2, 0).parameter_b),
            (0x09, 0x38),
        )
        self.assertEqual(
            (
                world_map.cell(1, 1).connection_mask,
                world_map.cell(1, 1).location_kind,
                world_map.cell(1, 1).parameter_a,
            ),
            (0xA0, 0x02, 0x45),
        )

    def test_supplied_save_matches_ce_map_with_four_mutations(self):
        original = load_archive_map(self.archive, "CE")
        state = parse_save_state((ROOT / "CB" / "DDGAMES.SV3").read_bytes())
        current = parse_map(state.three_byte_table_live)
        differences = compare_maps(original, current)
        self.assertEqual(
            [
                (item.x, item.y, item.field, item.original, item.current)
                for item in differences
            ],
            [
                (2, 0, 2, 0x38, 0x00),
                (0, 1, 1, 0x37, 0x00),
                (1, 1, 0, 0xA2, 0xAB),
                (2, 1, 0, 0xE5, 0xEB),
            ],
        )

    def test_scene_programs_load_each_level_letter(self):
        loaded = set()
        for entry in self.archive.entries:
            if entry.extension != "BIN":
                continue
            data = self.archive.extract(entry)
            regions = [(0, len(data))]
            if entry.filename == "CP2.BIN":
                regions = [(0, 0x1D5A)]
            elif entry.filename == "ROOM3.BIN":
                regions = [(0, 0x0336), (0x0C96, 0x1754), (0x1768, len(data))]
            for start, limit in regions:
                loaded.update(
                    chr(command.operands[0].value)
                    for command in decode_stream(data, start, limit)
                    if command.opcode == 0x78
                )
        self.assertEqual(loaded, set("ABCDEFG"))

    def test_rejects_invalid_size_name_and_coordinate(self):
        with self.assertRaisesRegex(MapFormatError, "expected 768"):
            parse_map(bytes(767))
        with self.assertRaisesRegex(MapFormatError, "expected level"):
            normalize_map_name("ZE")
        with self.assertRaisesRegex(IndexError, "outside 16x16"):
            parse_map(bytes(768)).cell(16, 0)


if __name__ == "__main__":
    unittest.main()
