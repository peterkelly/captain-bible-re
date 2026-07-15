from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_bin import (  # noqa: E402
    BinFormatError,
    OPCODE_NAMES,
    OPCODE_SCHEMAS,
    SCRIPT_VARIABLE_OPERANDS,
    decode_command,
    decode_stream,
    dialogue_choice_definitions,
    display_record_definitions,
)


class BinBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")
        cls.bin_members = {
            entry.filename: cls.archive.extract(entry)
            for entry in cls.archive.entries
            if entry.extension == "BIN"
        }

    @classmethod
    def member(cls, filename):
        entry = cls.archive.matching(filename)[0]
        return cls.archive.extract(entry)

    def test_has_layout_for_every_dispatched_opcode(self):
        self.assertEqual(set(OPCODE_SCHEMAS), set(range(1, 0x92)))

    def test_recovered_state_opcode_names(self):
        self.assertEqual(OPCODE_NAMES[0x1E], "copy_variable")
        self.assertEqual(OPCODE_NAMES[0x20], "jump_if_zero")
        self.assertEqual(OPCODE_NAMES[0x21], "jump_if_nonzero")
        self.assertEqual(OPCODE_NAMES[0x36], "set_text_record_state")
        self.assertEqual(OPCODE_NAMES[0x73], "jump_if_state_flag_clear")
        self.assertEqual(OPCODE_NAMES[0x81], "reduce_faith")

    def test_recovered_display_object_opcode_names(self):
        self.assertEqual(OPCODE_NAMES[0x02], "create_scene_thread")
        self.assertEqual(OPCODE_NAMES[0x03], "add_native_scale_display_object")
        self.assertEqual(OPCODE_NAMES[0x43], "add_scaled_display_object")
        self.assertEqual(OPCODE_NAMES[0x65], "clear_display_object_frames")
        self.assertEqual(OPCODE_NAMES[0x66], "advance_display_object_frames")
        self.assertEqual(OPCODE_NAMES[0x85], "hide_display_object")
        self.assertEqual(OPCODE_NAMES[0x86], "show_display_object")

    def test_recovered_conversation_opcode_names(self):
        self.assertEqual(OPCODE_NAMES[0x14], "show_adversary_dialogue")
        self.assertEqual(OPCODE_NAMES[0x44], "add_dialogue_choice")
        self.assertEqual(OPCODE_NAMES[0x45], "clear_dialogue_choices")
        self.assertEqual(OPCODE_NAMES[0x46], "present_dialogue_choices")
        self.assertEqual(OPCODE_NAMES[0x48], "show_character_dialogue")
        self.assertEqual(OPCODE_NAMES[0x49], "request_study_bible")
        self.assertEqual(OPCODE_NAMES[0x4E], "show_captain_bible_dialogue")
        self.assertEqual(OPCODE_NAMES[0x7D], "configure_study_prompt")

    def test_boss_dialogue_choices_match_qemu_live_table(self):
        commands = decode_stream(self.member("BOSS.BIN"))
        definitions = dialogue_choice_definitions(commands)
        self.assertEqual(
            [(definition.target, definition.text) for definition in definitions],
            [
                (0x0644, "So what do I do when I get inside?"),
                (0x07E8, "Can I expect any resistance?"),
                (0x0751, "What about the people inside?"),
                (
                    0x0519,
                    "Should I expect any problems with my computer bible?",
                ),
                (0x095C, "OK!  I'd better go do it!"),
            ],
        )

    def test_dialogue_choice_corpus_count(self):
        count = 0
        for filename, data in self.bin_members.items():
            regions = ((0, len(data)),)
            if filename == "CP2.BIN":
                regions = ((0, 0x1D5A),)
            elif filename == "ROOM3.BIN":
                regions = ((0, 0x0336), (0x0C96, 0x1754), (0x1768, len(data)))
            for start, limit in regions:
                commands = decode_stream(data, start, limit)
                count += len(dialogue_choice_definitions(commands))
        self.assertEqual(count, 40)

    def test_logo_display_definitions_match_qemu_live_table(self):
        commands = decode_stream(self.member("LOGO.BIN"))
        definitions = display_record_definitions(commands)
        self.assertEqual(
            [definition.kind for definition in definitions],
            [0x06] * 4 + [0x02] * 3 + [0x43] * 3 + [0x06] + [0x02] * 2,
        )
        self.assertEqual(len(definitions), 13)
        self.assertEqual(
            (
                definitions[7].x,
                definitions[7].y,
                definitions[7].scale,
                definitions[7].flags,
                definitions[7].frame,
                definitions[7].art_slot,
            ),
            (303, 0, 0x0100, 1, 4, 1),
        )
        self.assertEqual(
            (
                definitions[8].art_slot,
                definitions[8].frame,
                definitions[8].flags,
            ),
            (1, 4, 0),
        )

    def test_script_variable_operands_are_even_offsets_in_primary_state(self):
        for filename, data in self.bin_members.items():
            regions = ((0, len(data)),)
            if filename == "CP2.BIN":
                regions = ((0, 0x1D5A),)
            elif filename == "ROOM3.BIN":
                regions = ((0, 0x0336), (0x0C96, 0x1754), (0x1768, len(data)))
            for start, limit in regions:
                for command in decode_stream(data, start, limit):
                    positions = SCRIPT_VARIABLE_OPERANDS.get(command.opcode, ())
                    for position in positions:
                        value = command.operands[position].value
                        self.assertIsInstance(value, int)
                        self.assertEqual(value % 2, 0)
                        self.assertLess(value, 200)

    def test_decodes_complete_startup_scripts(self):
        expected = {
            "LOGO.BIN": 114,
            "TITLE.BIN": 80,
            "INTRO.BIN": 39,
            "MENU.BIN": 99,
        }
        for filename, count in expected.items():
            with self.subTest(filename=filename):
                data = self.member(filename)
                commands = decode_stream(data)
                self.assertEqual(len(commands), count)
                self.assertEqual(commands[-1].end, len(data))

    def test_intro_resource_and_scene_change_commands(self):
        commands = decode_stream(self.member("INTRO.BIN"))
        self.assertEqual(
            (commands[2].opcode, commands[2].operands[0].value),
            (0x4D, "TITLE"),
        )
        self.assertEqual(
            (commands[3].opcode, commands[3].operands[0].value),
            (0x01, "INTRO"),
        )
        scene_change = next(command for command in commands if command.opcode == 0x0D)
        self.assertEqual(
            tuple(operand.value for operand in scene_change.operands),
            ("dome", "seg"),
        )

    def test_victim_scenes_set_their_distinct_rescue_flags(self):
        expected = {
            "JELO.BIN": 0x3A,
            "FEAR.BIN": 0x3B,
            "CULT.BIN": 0x3C,
            "LAW.BIN": 0x3D,
            "RICH.BIN": 0x3E,
            "DENY.BIN": 0x3F,
            "NAGE.BIN": 0x40,
        }
        for filename, identifier in expected.items():
            commands = decode_stream(self.bin_members[filename])
            set_flags = {
                command.operands[0].value
                for command in commands
                if command.opcode == 0x76
            }
            self.assertIn(identifier, set_flags, filename)

    def test_all_bin_command_regions_follow_recovered_layouts(self):
        self.assertEqual(len(self.bin_members), 62)
        mixed_resources = {"CP2.BIN", "ROOM3.BIN"}
        for filename, data in self.bin_members.items():
            if filename in mixed_resources:
                continue
            with self.subTest(filename=filename):
                commands = decode_stream(data)
                self.assertEqual(commands[-1].end, len(data))

        cp2 = self.bin_members["CP2.BIN"]
        commands = decode_stream(cp2, 0, 0x1D5A)
        self.assertEqual(commands[-1].end, 0x1D5A)

    def test_conditional_extra_word_after_negative_operand(self):
        command = decode_command(bytes.fromhex("11 01 f8 ff e6 01"), 0)
        self.assertEqual(command.end, 6)
        self.assertEqual(
            tuple(operand.value for operand in command.operands),
            (1, 0xFFF8, 0x01E6),
        )

    def test_room3_command_regions_surround_reserved_zero_blocks(self):
        data = self.member("ROOM3.BIN")
        regions = ((0, 0x0336), (0x0C96, 0x1754), (0x1768, len(data)))
        for start, limit in regions:
            with self.subTest(start=start, limit=limit):
                commands = decode_stream(data, start, limit)
                self.assertEqual(commands[-1].end, limit)
        self.assertEqual(data[0x0336:0x0C96], bytes(0x0960))
        self.assertEqual(data[0x1754:0x1768], bytes(0x14))

    def test_rejects_zero_padding_as_an_opcode(self):
        with self.assertRaisesRegex(BinFormatError, "invalid BIN opcode"):
            decode_command(bytes(1), 0)

    def test_rejects_unterminated_string(self):
        with self.assertRaisesRegex(BinFormatError, "unterminated string"):
            decode_command(b"\x01INTRO", 0)

    def test_decodes_explicit_string_offset_escape(self):
        command = decode_command(bytes.fromhex("01 ff 34 12"), 0)
        self.assertEqual(command.end, 4)
        self.assertEqual(command.operands[0].kind, "string_offset")
        self.assertEqual(command.operands[0].value, 0x1234)


if __name__ == "__main__":
    unittest.main()
