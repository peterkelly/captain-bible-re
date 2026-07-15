from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from inspect_save import (  # noqa: E402
    SaveFormatError,
    SaveIndex,
    SaveState,
    parse_save,
    parse_save_index,
    parse_save_state,
)
from inspect_text_resources import load_text_bank  # noqa: E402


class SaveInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game_directory = ROOT / "CB"
        cls.states = tuple(
            parse_save_state(
                (cls.game_directory / f"DDGAMES.SV{number}").read_bytes()
            )
            for number in range(1, 10)
        )

    def test_supplied_index_has_nine_fixed_c_string_buffers(self):
        index = parse_save_index(
            (self.game_directory / "DDGAMES.SV0").read_bytes()
        )
        self.assertEqual(len(index.slots), 9)
        self.assertEqual([slot.text for slot in index.slots], ["EMPTY"] * 9)
        self.assertTrue(any(any(slot.stale_tail) for slot in index.slots))

    def test_parser_selects_index_or_state_by_exact_size(self):
        self.assertIsInstance(parse_save(bytes(243)), SaveIndex)
        self.assertIsInstance(parse_save(bytes(2752)), SaveState)
        with self.assertRaisesRegex(SaveFormatError, "unrecognized save size"):
            parse_save(bytes(244))

    def test_all_supplied_states_have_recovered_settings_and_snapshots(self):
        for state in self.states:
            self.assertEqual(state.translation, 1)
            self.assertEqual(state.music_enabled, 1)
            self.assertEqual(state.effects_enabled, 1)
            self.assertEqual(state.text_bank_snapshot, ord("C"))
            self.assertEqual(state.text_bank_live, ord("C"))
            self.assertEqual(
                (state.resource_name_snapshot, state.resource_name_live),
                ("LOGO", "LOGO"),
            )
            self.assertEqual(
                (state.resource_extension_snapshot, state.resource_extension_live),
                ("seg", "seg"),
            )
            self.assertEqual(
                state.three_byte_table_snapshot, state.three_byte_table_live
            )

    def test_compact_flags_match_saved_descriptor_state_bytes(self):
        for state in self.states:
            self.assertEqual(
                state.record_flags,
                tuple(descriptor.state for descriptor in state.text_descriptors),
            )

    def test_descriptors_match_niv_bank_c_structure(self):
        archive = DD1Archive.from_path(self.game_directory / "DD1.DAT")
        bank = load_text_bank(archive, self.game_directory, "N", "C")
        state = self.states[0]
        expected = tuple(
            (record.selector, record.data_offset, record.data_end - record.data_offset)
            for record in bank.records
        )
        actual = tuple(
            (descriptor.selector, descriptor.data_offset, descriptor.data_span)
            for descriptor in state.text_descriptors[: len(expected)]
        )
        self.assertEqual(actual, expected)
        self.assertTrue(
            all(
                descriptor.selector == descriptor.data_offset == descriptor.data_span == 0
                for descriptor in state.text_descriptors[len(expected) :]
            )
        )

    def test_known_duplicate_supplied_states_are_identical(self):
        self.assertEqual(
            (self.game_directory / "DDGAMES.SV6").read_bytes(),
            (self.game_directory / "DDGAMES.SV8").read_bytes(),
        )

    def test_rejects_truncated_or_extended_files(self):
        with self.assertRaisesRegex(SaveFormatError, "expected 243"):
            parse_save_index(bytes(242))
        with self.assertRaisesRegex(SaveFormatError, "expected 2752"):
            parse_save_state(bytes(2753))


if __name__ == "__main__":
    unittest.main()
