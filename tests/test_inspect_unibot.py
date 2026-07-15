from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_bin import decode_stream  # noqa: E402
from inspect_unibot import (  # noqa: E402
    PYLON_NUMBERS,
    UnibotMapError,
    parse_unibot_map,
)


class UnibotProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")
        cls.members = {
            entry.filename: archive.extract(entry)
            for entry in archive.entries
        }

    def test_cp2_embeds_reciprocal_sixteen_node_graph(self):
        world = parse_unibot_map(self.members["CP2.BIN"])
        self.assertEqual(len(world.nodes), 16)
        self.assertEqual(world.node(0).exits, (1, None, None, None))
        self.assertEqual(world.node(1).exits, (14, 4, 0, 2))
        self.assertEqual(world.node(14).exits, (None, None, 1, None))
        self.assertEqual(
            [(node.map_x, node.map_y) for node in world.nodes[:4]],
            [(270, 170), (270, 165), (265, 165), (265, 170)],
        )

    def test_seven_pylons_and_tower_have_exact_nodes(self):
        world = parse_unibot_map(self.members["CP2.BIN"])
        self.assertEqual(
            {
                node.index: node.pylon_number
                for node in world.nodes
                if node.cell_type == "pylon"
            },
            PYLON_NUMBERS,
        )
        self.assertEqual(world.node(14).cell_type, "tower")

    def test_gantry_mirrors_rescue_flags_into_crew_flags(self):
        commands = decode_stream(self.members["GANTRY.BIN"])
        pairs = []
        for index, command in enumerate(commands[:-1]):
            following = commands[index + 1]
            if command.opcode == 0x73 and following.opcode == 0x76:
                pairs.append(
                    (command.operands[0].value, following.operands[0].value)
                )
        self.assertEqual(
            pairs,
            list(zip(range(0x3A, 0x41), range(0x42, 0x49))),
        )

    def test_cp2_pylon_variables_and_final_scene_chain(self):
        commands = decode_stream(self.members["CP2.BIN"], limit=0x1D55)
        assignments = {
            tuple(operand.value for operand in command.operands)
            for command in commands
            if command.opcode == 0x1F
        }
        self.assertTrue(
            {(1, offset) for offset in range(0x70, 0x7E, 2)} <= assignments
        )
        self.assertEqual(
            [
                command.operands[0].value
                for command in commands
                if command.opcode == 0x0D
            ],
            ["FACE", "OVER"],
        )

        self.assertIn(b"KABLAM\0", self.members["CP3.BIN"])
        self.assertIn(b"OVER\0", self.members["CP3.BIN"])
        self.assertIn(b"WIN\0", self.members["KABLAM.BIN"])

    def test_crew_gate_and_unibot_initialization(self):
        cp1 = decode_stream(self.members["CP1.BIN"])
        tested_flags = {
            command.operands[0].value
            for command in cp1
            if command.opcode == 0x73
            and 0x42 <= command.operands[0].value <= 0x48
        }
        self.assertEqual(tested_flags, set(range(0x42, 0x49)))
        self.assertIn(b"ROBOT\0", self.members["CP1.BIN"])

        robot = decode_stream(self.members["ROBOT.BIN"])
        assignments = {
            tuple(operand.value for operand in command.operands)
            for command in robot
            if command.opcode == 0x1F
        }
        self.assertTrue({(0, 0x6A), (0, 0x6C), (0, 0x6E)} <= assignments)
        self.assertIn(b"CP2\0", self.members["ROBOT.BIN"])

    def test_tower_confrontation_has_success_and_failure_states(self):
        cp3 = decode_stream(self.members["CP3.BIN"])
        assignments = {
            tuple(operand.value for operand in command.operands)
            for command in cp3
            if command.opcode == 0x1F
        }
        self.assertTrue({(1, 0x82), (2, 0x82), (9, 0x82)} <= assignments)
        cp3_scenes = [
            command.operands[0].value
            for command in cp3
            if command.opcode == 0x0D
        ]
        self.assertEqual(
            cp3_scenes,
            ["KABLAM", "FACE", "FACE", "FACE", "OVER"],
        )

        face = decode_stream(self.members["FACE.BIN"])
        tested_states = {
            command.operands[1].value
            for command in face
            if command.opcode == 0x23
            and command.operands[0].value == 0x82
        }
        self.assertEqual(tested_states, {1, 2, 9})

    def test_rejects_wrong_size_and_nonreciprocal_edge(self):
        data = self.members["CP2.BIN"]
        with self.assertRaisesRegex(UnibotMapError, "expected 7765"):
            parse_unibot_map(data[:-1])
        damaged = bytearray(data)
        damaged[0x1D55:0x1D57] = (2).to_bytes(2, "little")
        with self.assertRaisesRegex(UnibotMapError, "not reciprocal"):
            parse_unibot_map(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
