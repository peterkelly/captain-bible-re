from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_bin import code_regions, decode_stream  # noqa: E402
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
        self.assertEqual(
            world_map.cell(1, 1).connection_directions,
            ("down", "right"),
        )

    def test_zero_connection_kinds_decode_as_five_room_classes(self):
        expected_classes = (
            "victim",
            "trap",
            "prayer",
            "communications",
            "jump-tunnel",
        )
        expected_sides = ("west", "east", "south")
        for kind in range(1, 16):
            cell = parse_map(bytes((kind, 0x12, 0x34)) + bytes(765)).cell(0, 0)
            self.assertEqual(
                cell.room_class,
                expected_classes[(kind - 1) // 3],
            )
            self.assertEqual(
                cell.room_entrance_side,
                expected_sides[(kind - 1) % 3],
            )

        hall = parse_map(bytes((0x11, 0, 0)) + bytes(765)).cell(0, 0)
        empty = parse_map(bytes(768)).cell(0, 0)
        self.assertIsNone(hall.room_class)
        self.assertIsNone(hall.room_entrance_side)
        self.assertIsNone(empty.room_class)

    def test_connected_kinds_decode_only_proven_hall_features(self):
        expected = {
            0x1: "macho-cyber",
            0x2: "armored-cyber",
            0x3: "mantis-cyber",
            0x4: "snake-cyber",
            0x5: "spider-cyber",
            0x6: "leech-covered-station",
            0x7: "zapper-cyber",
            0x9: "hidden-spider-trigger",
            0xA: "scripture-station",
            0xB: "cleared-encounter",
            0xE: "level-exit",
        }
        for kind, feature in expected.items():
            cell = parse_map(bytes((0x10 | kind, 0, 0)) + bytes(765)).cell(0, 0)
            self.assertEqual(cell.hall_feature, feature)

        for kind in (0x0, 0x8, 0xC, 0xD, 0xF):
            cell = parse_map(bytes((0x10 | kind, 0, 0)) + bytes(765)).cell(0, 0)
            self.assertIsNone(cell.hall_feature)
        room = parse_map(bytes((0x04, 0, 0)) + bytes(765)).cell(0, 0)
        self.assertIsNone(room.hall_feature)

    def test_hall_programs_encode_spider_trigger_and_feature_resources(self):
        members = {
            entry.filename: self.archive.extract(entry)
            for entry in self.archive.entries
        }
        combat_resources = {
            "COMBAT1.BIN": b"BIG\0",
            "COMBAT2.BIN": b"HELMET\0",
            "COMBAT3.BIN": b"MANTIS\0",
            "COMBAT4.BIN": b"SNAKE\0",
            "COMBAT5.BIN": b"CRAB\0",
            "COMBAT6.BIN": b"GUARD\0",
            "COMBAT7.BIN": b"ZAP\0",
        }
        for filename, resource_name in combat_resources.items():
            self.assertIn(resource_name, members[filename])

        for level in "ABCDEFG":
            commands = decode_stream(members[level + "HAL.BIN"])
            has_hidden_spider_transition = any(
                command.opcode == 0x1F
                and tuple(operand.value for operand in command.operands)
                == (0x0005, 0x003A)
                and commands[index + 1].opcode == 0x7B
                and commands[index + 1].operands[0].value == 0x003A
                for index, command in enumerate(commands[:-1])
            )
            self.assertTrue(has_hidden_spider_transition, level)
            self.assertIn(b"POWER\0", members[level + "HAL.BIN"])
            self.assertIn(b"Verse loaded: &\0", members[level + "HAL.BIN"])

    def test_archive_room_cells_use_fourteen_class_orientation_pairs(self):
        observed = set()
        for level in "ABCDEFG":
            for difficulty in "END":
                world_map = load_archive_map(self.archive, level + difficulty)
                for cell in world_map.cells:
                    if cell.room_class is not None:
                        observed.add((cell.room_class, cell.room_entrance_side))
        self.assertEqual(
            observed,
            {
                (room_class, entrance)
                for room_class in (
                    "victim",
                    "trap",
                    "prayer",
                    "communications",
                    "jump-tunnel",
                )
                for entrance in ("west", "east", "south")
            }
            - {("jump-tunnel", "south")},
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
            for start, limit in code_regions(entry.filename, len(data)):
                loaded.update(
                    chr(command.operands[0].value)
                    for command in decode_stream(data, start, limit)
                    if command.opcode == 0x78
                )
        self.assertEqual(loaded, set("ABCDEFG"))

    def test_every_map_kind_write_uses_a_low_nibble_immediate(self):
        observed = []
        for entry in self.archive.entries:
            if entry.extension != "BIN":
                continue
            data = self.archive.extract(entry)
            for start, limit in code_regions(entry.filename, len(data)):
                commands = decode_stream(data, start, limit)
                for index, command in enumerate(commands):
                    if command.opcode != 0x7B:
                        continue
                    previous = commands[index - 1]
                    self.assertEqual(previous.opcode, 0x1F)
                    self.assertEqual(
                        previous.operands[1].value, command.operands[0].value
                    )
                    value = previous.operands[0].value
                    self.assertLessEqual(value, 0x0F)
                    observed.append(value)
        self.assertEqual(len(observed), 30)
        self.assertEqual(set(observed), {0x00, 0x05, 0x0A, 0x0B, 0x0C})

    def test_room_and_victim_scene_dispatch_matches_decoded_classes(self):
        members = {
            entry.filename: self.archive.extract(entry)
            for entry in self.archive.entries
        }
        room_resources = {
            "ROOM1.BIN": (b"TRAP\0", b"TRAP2\0", b"TRAP3\0"),
            "ROOM2.BIN": (b"PRAY\0",),
            "ROOM3.BIN": (b"COMM\0", b"COMM2\0", b"FACE1\0"),
            "ROOM4.BIN": (b"TUNNEL\0", b"TUNNEL2\0", b"MONST1\0"),
        }
        for filename, resource_names in room_resources.items():
            for resource_name in resource_names:
                self.assertIn(resource_name, members[filename])

        for hall, victim in zip(
            ("AHAL", "BHAL", "CHAL", "DHAL", "EHAL", "FHAL", "GHAL"),
            (
                b"JELO\0",
                b"FEAR\0",
                b"CULT\0",
                b"LAW\0",
                b"RICH\0",
                b"DENY\0",
                b"NAGE\0",
            ),
        ):
            self.assertIn(victim, members[hall + ".BIN"])

    def test_rejects_invalid_size_name_and_coordinate(self):
        with self.assertRaisesRegex(MapFormatError, "expected 768"):
            parse_map(bytes(767))
        with self.assertRaisesRegex(MapFormatError, "expected level"):
            normalize_map_name("ZE")
        with self.assertRaisesRegex(IndexError, "outside 16x16"):
            parse_map(bytes(768)).cell(16, 0)


if __name__ == "__main__":
    unittest.main()
