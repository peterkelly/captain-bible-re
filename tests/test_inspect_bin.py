from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_bin import (  # noqa: E402
    BinFormatError,
    COMBAT_ACTION_LABELS,
    HALL_ACTION_LABELS,
    OPCODE_NAMES,
    OPCODE_SCHEMAS,
    SCRIPT_VARIABLE_OPERANDS,
    action_target_definitions,
    animation_sequence_definitions,
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

    def test_has_name_for_every_dispatched_opcode(self):
        self.assertEqual(set(OPCODE_NAMES), set(OPCODE_SCHEMAS))

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

    def test_recovered_combat_runtime_opcode_names(self):
        expected = {
            0x08: "start_animation",
            0x09: "stop_animation",
            0x3A: "add_action_target",
            0x3B: "enable_action_target",
            0x3C: "disable_action_target",
            0x3E: "start_scene_thread_at",
            0x3F: "wait_for_animation",
            0x41: "enable_action_selection",
            0x42: "disable_action_selection",
            0x59: "wait_for_sound_effect",
            0x5F: "start_linked_animation",
            0x60: "nop",
            0x61: "stop_scene_thread",
            0x6C: "rotate_palette_range",
            0x7A: "patch_bin_byte_from_variable",
            0x7E: "blackout_palette",
            0x80: "jump_if_animation_active",
            0x82: "set_variable_random_modulo",
            0x8E: "sync_current_cell_flags_23_to_27",
        }
        for opcode, name in expected.items():
            self.assertEqual(OPCODE_NAMES[opcode], name)

    def test_combat7_action_targets_match_art_labels(self):
        commands = decode_stream(self.member("COMBAT7.BIN"))
        definitions = action_target_definitions(commands)
        self.assertEqual(
            [
                (
                    definition.offset,
                    definition.target,
                    definition.x,
                    definition.y,
                    definition.selector,
                    COMBAT_ACTION_LABELS[definition.selector],
                )
                for definition in definitions
            ],
            [
                (0x0C06, 0x0EC8, 151, 61, ".11", "ATTACK"),
                (0x0C11, 0x0EAB, 136, 153, ".12", "DEFEND"),
                (0x0C1C, 0x1053, 15, 167, ".13", "RETREAT"),
                (0x0C27, 0x0FA7, 157, 62, ".14", "COMBAT"),
            ],
        )

    def test_hall_action_selectors_match_manual_actions(self):
        definitions = action_target_definitions(decode_stream(self.member("AHAL.BIN")))
        self.assertEqual(
            [
                (definition.selector, HALL_ACTION_LABELS[definition.selector])
                for definition in definitions
            ],
            [
                (".d", "MOVE DOWN"),
                (".u", "MOVE UP"),
                (".c", "CONFRONT CYBER"),
                (".c", "CONFRONT CYBER"),
                (".c", "CONFRONT CYBER"),
                (".c", "CONFRONT CYBER"),
                (".x", "UNLOCK"),
                (".x", "UNLOCK"),
                (".x", "UNLOCK"),
                (".r", "MOVE RIGHT"),
                (".l", "MOVE LEFT"),
                (".v", "GET VERSE"),
            ],
        )

    def test_combat_animation_and_action_corpus_counts(self):
        sequence_count = 0
        step_count = 0
        action_count = 0
        selectors = []
        for number in range(1, 8):
            commands = decode_stream(self.member(f"COMBAT{number}.BIN"))
            sequences = animation_sequence_definitions(commands)
            actions = action_target_definitions(commands)
            sequence_count += len(sequences)
            step_count += sum(len(sequence.steps) for sequence in sequences)
            action_count += len(actions)
            selectors.extend(action.selector for action in actions)
        self.assertEqual(
            (sequence_count, step_count, action_count), (214, 2596, 27)
        )
        self.assertEqual(selectors.count(".11"), 7)
        self.assertEqual(selectors.count(".12"), 6)
        self.assertEqual(selectors.count(".13"), 7)
        self.assertEqual(selectors.count(".14"), 7)

    def test_combat_outcome_epilogues_and_faith_effects(self):
        expected_losses = {
            1: [0x0215, 0x07DB],
            2: [0x006B, 0x0066, 0x01F6],
            3: [0x040D, 0x0213, 0x07DB, 0x06A7],
            4: [0x0254, 0x03ED],
            5: [0x00D5, 0x07D9],
            6: [],
            7: [0x00E9, 0x00CF],
        }
        expected_kinds = {
            1: {0x0B},
            2: {0x0B},
            3: {0x0B},
            4: {0x0B},
            5: {0x0B},
            6: {0x0A},
            7: {0x0B},
        }

        for number in range(1, 8):
            commands = decode_stream(self.member(f"COMBAT{number}.BIN"))
            by_offset = {command.offset: command for command in commands}
            actions = action_target_definitions(commands)
            retreat = next(action for action in actions if action.selector == ".13")
            self.assertEqual(by_offset[retreat.target].opcode, 0x3D)

            losses = [
                int(command.operands[0].value)
                for command in commands
                if command.opcode == 0x81
            ]
            self.assertEqual(losses, expected_losses[number])

            assigned = {}
            map_kinds = set()
            for command in commands:
                if command.opcode == 0x1F:
                    value = int(command.operands[0].value)
                    variable = int(command.operands[1].value)
                    assigned[variable] = value
                elif command.opcode == 0x7B:
                    variable = int(command.operands[0].value)
                    map_kinds.add(assigned[variable])
            self.assertEqual(map_kinds, expected_kinds[number])

            set_flags = [
                command.operands[0].value
                for command in commands
                if command.opcode == 0x76
            ]
            clear_flags = [
                command.operands[0].value
                for command in commands
                if command.opcode == 0x75
            ]
            self.assertEqual(0x38 in set_flags, number != 6)
            self.assertEqual(0x38 in clear_flags, number != 6)

            hall_patches = [
                command
                for command in commands
                if command.opcode == 0x7A
                and command.operands[1].value == 0x20
            ]
            self.assertEqual(len(hall_patches), 1)
            return_scenes = {
                command.operands[0].value
                for command in commands
                if command.opcode == 0x0D
            }
            self.assertTrue({"CHAL", "GHALB", "GHALS"} <= return_scenes)

    def test_zapper_victory_restores_full_faith(self):
        commands = decode_stream(self.member("COMBAT7.BIN"))
        assignments = [
            command.operands[0].value
            for command in commands
            if command.opcode == 0x1F
            and command.operands[1].value == 0x002A
        ]
        self.assertEqual(assignments, [1, 10000] * 5)

    def test_power_scene_returns_to_selected_combat(self):
        commands = decode_stream(self.member("POWER.BIN"))
        patch = next(
            command
            for command in commands
            if command.opcode == 0x7A
            and command.operands[1].value == 0x003A
        )
        self.assertEqual(patch.operands[0].value, 0x01F3)
        scene = next(command for command in commands if command.offset == patch.end)
        self.assertEqual(scene.opcode, 0x0D)
        self.assertEqual(scene.operands[0].value, "combat1")

    def test_combat7_first_animation_sequence(self):
        commands = decode_stream(self.member("COMBAT7.BIN"))
        sequences = animation_sequence_definitions(commands)
        self.assertEqual(
            (len(sequences), sum(len(x.steps) for x in sequences)), (35, 293)
        )
        self.assertEqual(
            (sequences[0].offset, sequences[0].interval, sequences[0].steps),
            (0x002B, 50, (bytes.fromhex("01 04 92 00 35 00 00 01 02"),)),
        )

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
                regions = ((0, 0x1D55),)
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
                regions = ((0, 0x1D55),)
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
        commands = decode_stream(cp2, 0, 0x1D55)
        self.assertEqual(commands[-1].end, 0x1D55)

    def test_complete_command_corpus_count(self):
        commands = []
        region_count = 0
        for filename, data in self.bin_members.items():
            regions = ((0, len(data)),)
            if filename == "CP2.BIN":
                regions = ((0, 0x1D55),)
            elif filename == "ROOM3.BIN":
                regions = (
                    (0, 0x0336),
                    (0x0C96, 0x1754),
                    (0x1768, len(data)),
                )
            for start, limit in regions:
                commands.extend(decode_stream(data, start, limit))
                region_count += 1
        self.assertEqual(region_count, 64)
        self.assertEqual(len(commands), 25_829)
        self.assertEqual(len({command.opcode for command in commands}), 122)

    def test_load_bin_word_consumes_offset_and_destination(self):
        commands = decode_stream(self.member("CP2.BIN"), 0, 0x1D55)
        command = next(
            command for command in commands if command.offset == 0x15D4
        )
        self.assertEqual(command.opcode, 0x69)
        self.assertEqual(command.name, "load_bin_word")
        self.assertEqual(
            tuple(operand.value for operand in command.operands),
            (0x0DEB, 0x0040),
        )
        self.assertEqual(command.end, 0x15D9)

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
