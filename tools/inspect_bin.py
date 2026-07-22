#!/usr/bin/env python3
"""Decode Captain Bible BIN scene bytecode into a linear command listing."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from inspect_save import SCRIPT_VARIABLE_NAMES


class BinFormatError(ValueError):
    """Raised when a BIN command or operand extends outside the input."""


@dataclass(frozen=True)
class Operand:
    kind: str
    value: int | str | bytes


@dataclass(frozen=True)
class BinCommand:
    offset: int
    end: int
    opcode: int
    name: str
    operands: tuple[Operand, ...]


@dataclass(frozen=True)
class DisplayRecordDefinition:
    """One command which appends a record to the scene display list."""

    offset: int
    kind: int
    delay: int | None = None
    thread_slot: int | None = None
    x: int | None = None
    y: int | None = None
    scale: int | None = None
    flags: int | None = None
    frame: int | None = None
    art_slot: int | None = None


@dataclass(frozen=True)
class DialogueChoiceDefinition:
    """One command which adds an option to the current dialogue menu."""

    offset: int
    target: int
    text: str | int


@dataclass(frozen=True)
class AnimationSequenceDefinition:
    """One animation header and its contiguous nine-byte steps."""

    offset: int
    interval: int
    steps: tuple[bytes, ...]


@dataclass(frozen=True)
class ActionTargetDefinition:
    """One selectable screen action defined by a BIN command."""

    offset: int
    target: int
    x: int
    y: int
    selector: str | int


COMBAT_ACTION_LABELS = {
    ".11": "ATTACK",
    ".12": "DEFEND",
    ".13": "RETREAT",
    ".14": "COMBAT",
}
HALL_ACTION_LABELS = {
    ".d": "MOVE DOWN",
    ".u": "MOVE UP",
    ".r": "MOVE RIGHT",
    ".l": "MOVE LEFT",
    ".c": "CONFRONT CYBER",
    ".x": "UNLOCK",
    ".v": "GET VERSE",
}
ACTION_LABELS = COMBAT_ACTION_LABELS | HALL_ACTION_LABELS


# Operand layout recovered from execute_bin_commands at load-module offset
# 0x451b. B is an unsigned byte, H is a little-endian 16-bit word, z is an
# inline NUL-terminated CP437 string, p is a string pointer encoded as either
# an inline NUL-terminated string or 0xFF plus an explicit 16-bit offset, 9 is
# a nine-byte opaque animation record, and s adds another word when the
# immediately preceding H is negative.
OPCODE_SCHEMAS = {
    0x01: "z", 0x02: "BHHH", 0x03: "BBHHB", 0x04: "BBHHHB",
    0x05: "", 0x06: "H", 0x07: "9", 0x08: "BB", 0x09: "B",
    0x0A: "", 0x0B: "BB", 0x0C: "BBp", 0x0D: "zz", 0x0E: "",
    0x0F: "H", 0x10: "BHHp", 0x11: "BHs", 0x12: "BHs",
    0x13: "H", 0x14: "p", 0x15: "B", 0x16: "HHH", 0x17: "BHs",
    0x18: "BHs", 0x19: "BHs", 0x1A: "BHs", 0x1B: "H",
    0x1C: "B", 0x1D: "B", 0x1E: "HH", 0x1F: "HH",
    0x20: "HH", 0x21: "HH", 0x22: "HHH", 0x23: "HHH",
    0x24: "HHH", 0x25: "HHH", 0x26: "HHH", 0x27: "HHH",
    0x28: "HHH", 0x29: "HHH", 0x2A: "HH", 0x2B: "HH",
    0x2C: "HH", 0x2D: "HH", 0x2E: "HH", 0x2F: "HH",
    0x30: "HH", 0x31: "HH", 0x32: "H", 0x33: "H",
    0x34: "H", 0x35: "", 0x36: "B", 0x37: "B", 0x38: "BH",
    0x39: "BH", 0x3A: "HHHp", 0x3B: "B", 0x3C: "B",
    0x3D: "H", 0x3E: "BH", 0x3F: "B", 0x40: "B", 0x41: "",
    0x42: "", 0x43: "BBHHHB", 0x44: "Hp", 0x45: "",
    0x46: "", 0x47: "B", 0x48: "p", 0x49: "", 0x4A: "",
    0x4B: "", 0x4C: "B", 0x4D: "z", 0x4E: "p", 0x4F: "BB",
    0x50: "", 0x51: "BHB", 0x52: "B", 0x53: "B", 0x54: "B",
    0x55: "", 0x56: "", 0x57: "BH", 0x58: "", 0x59: "",
    0x5A: "H", 0x5B: "B", 0x5C: "BBB", 0x5D: "BBB",
    0x5E: "H", 0x5F: "BBB", 0x60: "", 0x61: "B", 0x62: "H",
    0x63: "H", 0x64: "H", 0x65: "BB", 0x66: "BBBB",
    0x67: "", 0x68: "H", 0x69: "HH", 0x6A: "HH", 0x6B: "B",
    0x6C: "HHHH", 0x6D: "z", 0x6E: "B", 0x6F: "",
    0x70: "", 0x71: "HH", 0x72: "", 0x73: "BH", 0x74: "BH",
    0x75: "B", 0x76: "B", 0x77: "", 0x78: "B", 0x79: "",
    0x7A: "HH", 0x7B: "H", 0x7C: "H", 0x7D: "BH",
    0x7E: "", 0x7F: "H", 0x80: "BH", 0x81: "H", 0x82: "HH",
    0x83: "HBH", 0x84: "HH", 0x85: "B", 0x86: "B",
    0x87: "", 0x88: "", 0x89: "", 0x8A: "BH", 0x8B: "",
    0x8C: "H", 0x8D: "H", 0x8E: "", 0x8F: "HH",
    0x90: "HH", 0x91: "HH",
}


OPCODE_NAMES = {
    0x01: "load_art",
    0x02: "create_scene_thread",
    0x03: "add_native_scale_display_object",
    0x04: "add_scaled_display_object",
    0x05: "return_minus_one",
    0x06: "begin_animation_sequence",
    0x07: "animation_step",
    0x08: "start_animation",
    0x09: "stop_animation",
    0x0A: "wait_for_scene_thread_movement",
    0x0B: "add_navigation_edge",
    0x0C: "add_scene_entry",
    0x0D: "change_scene",
    0x0E: "nop",
    0x0F: "adjust_thread_delay",
    0x10: "configure_scene_thread_action",
    0x11: "add_navigation_arrival_handler",
    0x12: "add_navigation_departure_handler",
    0x13: "remove_dialogue_choice",
    0x14: "show_adversary_dialogue",
    0x15: "select_study_record",
    0x16: "set_palette_adjustment_range_from_variable",
    0x17: "add_reverse_edge_departure_handler",
    0x18: "add_forward_edge_departure_handler",
    0x19: "add_forward_edge_arrival_handler",
    0x1A: "add_reverse_edge_arrival_handler",
    0x1B: "prime_primary_scene_thread_timer",
    0x1C: "enable_scene_thread_action",
    0x1D: "disable_scene_thread_action",
    0x1E: "copy_variable",
    0x1F: "set_variable",
    0x20: "jump_if_zero",
    0x21: "jump_if_nonzero",
    0x22: "jump_if_variables_equal",
    0x23: "jump_if_variable_equals",
    0x24: "jump_if_variables_not_equal",
    0x25: "jump_if_variable_not_equal",
    0x26: "jump_if_variable_greater_than_variable",
    0x27: "jump_if_variable_greater_than",
    0x28: "jump_if_variable_less_than_variable",
    0x29: "jump_if_variable_less_than",
    0x2A: "add_variable",
    0x2B: "add_to_variable",
    0x2C: "subtract_variable",
    0x2D: "subtract_from_variable",
    0x2E: "multiply_variables",
    0x2F: "multiply_variable",
    0x30: "divide_variables",
    0x31: "divide_variable",
    0x32: "increment_variable",
    0x33: "decrement_variable",
    0x34: "call",
    0x35: "return",
    0x36: "set_text_record_state",
    0x37: "clear_text_record_state",
    0x38: "jump_if_text_record_set",
    0x39: "jump_if_text_record_clear",
    0x3A: "add_action_target",
    0x3B: "enable_action_target",
    0x3C: "disable_action_target",
    0x3D: "jump",
    0x3E: "start_scene_thread_at",
    0x3F: "wait_for_animation",
    0x40: "set_scene_thread_motion_state",
    0x41: "enable_action_selection",
    0x42: "disable_action_selection",
    0x43: "add_scaled_display_object",
    0x44: "add_dialogue_choice",
    0x45: "clear_dialogue_choices",
    0x46: "present_dialogue_choices",
    0x47: "set_modal_menu_selection",
    0x48: "show_character_dialogue",
    0x49: "request_study_bible",
    0x4A: "nop",
    0x4B: "nop",
    0x4C: "fill_screen",
    0x4D: "load_palette",
    0x4E: "show_captain_bible_dialogue",
    0x4F: "configure_study_navigation_success",
    0x50: "clear_study_record_selection",
    0x51: "configure_study_thread_success",
    0x52: "play_music",
    0x53: "set_scene_thread_origin",
    0x54: "move_scene_thread_to",
    0x55: "snapshot_state",
    0x56: "nop",
    0x57: "play_sound_effect",
    0x58: "stop_sound_effect",
    0x59: "wait_for_sound_effect",
    0x5A: "jump_if_digital_audio_fallback",
    0x5B: "set_scene_thread_direction",
    0x5C: "configure_captain_bible_dialogue",
    0x5D: "configure_character_dialogue",
    0x5E: "set_deferred_scene_thread_target",
    0x5F: "start_linked_animation",
    0x60: "nop",
    0x61: "stop_scene_thread",
    0x62: "store_mouse_x",
    0x63: "store_mouse_y",
    0x64: "jump_if_confirm_pressed",
    0x65: "clear_display_object_frames",
    0x66: "advance_display_object_frames",
    0x67: "request_restore_saved_game",
    0x68: "adjust_variable_1280_once",
    0x69: "load_bin_word",
    0x6A: "patch_bin_word_from_variable",
    0x6B: "load_text_bank",
    0x6C: "rotate_palette_range",
    0x6D: "load_palette",
    0x6E: "start_primary_scene_thread_overlay",
    0x6F: "wait_for_primary_scene_thread_overlay",
    0x70: "unload_last_art",
    0x71: "load_bin_word_indirect",
    0x72: "suspend_scene_thread",
    0x73: "jump_if_state_flag_clear",
    0x74: "jump_if_state_flag_set",
    0x75: "clear_state_flag",
    0x76: "set_state_flag",
    0x77: "process_current_map_cell",
    0x78: "load_map",
    0x79: "clear_navigation_handlers",
    0x7A: "patch_bin_byte_from_variable",
    0x7B: "set_current_map_cell_kind",
    0x7C: "set_current_map_cell_parameter_a",
    0x7D: "configure_study_prompt",
    0x7E: "blackout_palette",
    0x7F: "set_current_map_cell_parameter_b",
    0x80: "jump_if_animation_active",
    0x81: "reduce_faith",
    0x82: "set_variable_random_modulo",
    0x83: "copy_text_record_component_to_bin",
    0x84: "load_bin_byte",
    0x85: "hide_display_object",
    0x86: "show_display_object",
    0x87: "normalize_map_cells",
    0x88: "clear_text_record_states",
    0x89: "mark_current_map_cell_explored",
    0x8A: "jump_if_animation_finished",
    0x8B: "consume_random_text_record",
    0x8C: "jump_if_no_combat",
    0x8D: "jump_if_file_missing",
    0x8E: "sync_current_cell_flags_23_to_27",
    0x8F: "and_variables",
    0x90: "and_variable",
    0x91: "set_variable_current_cell_byte_modulo",
}


def code_regions(filename: str, size: int) -> tuple[tuple[int, int], ...]:
    """Return the independently recovered executable regions of a BIN member."""

    if filename.upper() == "CP2.BIN":
        return ((0, 0x1D55),)
    if filename.upper() == "ROOM3.BIN":
        return ((0, 0x0336), (0x0C96, 0x1754), (0x1768, size))
    return ((0, size),)


# These operands are even byte offsets into the 200-byte primary-state block.
# The interpreter divides them by two before indexing its 100 signed words.
SCRIPT_VARIABLE_OPERANDS = {
    0x16: (2,),
    0x1E: (0, 1),
    0x1F: (1,),
    0x20: (0,),
    0x21: (0,),
    0x22: (0, 1),
    0x23: (0,),
    0x24: (0, 1),
    0x25: (0,),
    0x26: (0, 1),
    0x27: (0,),
    0x28: (0, 1),
    0x29: (0,),
    0x2A: (0, 1),
    0x2B: (1,),
    0x2C: (0, 1),
    0x2D: (1,),
    0x2E: (0, 1),
    0x2F: (1,),
    0x30: (0, 1),
    0x31: (1,),
    0x32: (0,),
    0x33: (0,),
    0x62: (0,),
    0x63: (0,),
    0x68: (0,),
    0x69: (1,),
    0x6A: (1,),
    0x6C: (3,),
    0x71: (0, 1),
    0x7A: (1,),
    0x7B: (0,),
    0x7C: (0,),
    0x7D: (1,),
    0x7F: (0,),
    0x82: (1,),
    0x83: (0,),
    0x84: (1,),
    0x8F: (0, 1),
    0x90: (1,),
    0x91: (1,),
}


def _require(data: bytes, position: int, size: int, limit: int) -> None:
    if position + size > limit:
        raise BinFormatError(
            f"operand at {position:#x} needs {size} byte(s), "
            f"but the decoding limit is {limit:#x}"
        )


def decode_command(data: bytes, offset: int, limit: int | None = None) -> BinCommand:
    """Decode the command beginning at *offset*."""

    if limit is None:
        limit = len(data)
    if offset < 0 or limit < offset or limit > len(data):
        raise BinFormatError("invalid BIN decoding bounds")
    _require(data, offset, 1, limit)

    opcode = data[offset]
    if opcode not in OPCODE_SCHEMAS:
        raise BinFormatError(f"invalid BIN opcode {opcode:#04x} at {offset:#x}")

    position = offset + 1
    operands: list[Operand] = []
    last_signed_word = 0
    for field in OPCODE_SCHEMAS[opcode]:
        if field == "B":
            _require(data, position, 1, limit)
            operands.append(Operand("u8", data[position]))
            position += 1
        elif field == "H":
            _require(data, position, 2, limit)
            raw = int.from_bytes(data[position : position + 2], "little")
            last_signed_word = raw if raw < 0x8000 else raw - 0x10000
            operands.append(Operand("u16", raw))
            position += 2
        elif field == "z":
            _require(data, position, 1, limit)
            end = data.find(b"\0", position, limit)
            if end < 0:
                raise BinFormatError(
                    f"unterminated string operand at {position:#x}"
                )
            value = data[position:end].decode("cp437")
            operands.append(Operand("string", value))
            position = end + 1
        elif field == "p":
            _require(data, position, 1, limit)
            if data[position] == 0xFF:
                _require(data, position, 3, limit)
                value = int.from_bytes(data[position + 1 : position + 3], "little")
                operands.append(Operand("string_offset", value))
                position += 3
            else:
                end = data.find(b"\0", position, limit)
                if end < 0:
                    raise BinFormatError(
                        f"unterminated string operand at {position:#x}"
                    )
                value = data[position:end].decode("cp437")
                operands.append(Operand("string", value))
                position = end + 1
        elif field == "9":
            _require(data, position, 9, limit)
            operands.append(Operand("record9", data[position : position + 9]))
            position += 9
        elif field == "s":
            if last_signed_word < 0:
                _require(data, position, 2, limit)
                raw = int.from_bytes(data[position : position + 2], "little")
                operands.append(Operand("u16", raw))
                position += 2
        else:
            raise AssertionError(f"unknown internal operand field {field!r}")

    return BinCommand(
        offset=offset,
        end=position,
        opcode=opcode,
        name=OPCODE_NAMES.get(opcode, f"opcode_{opcode:02x}"),
        operands=tuple(operands),
    )


def decode_stream(
    data: bytes, start: int = 0, limit: int | None = None
) -> tuple[BinCommand, ...]:
    """Linearly decode commands between *start* and *limit*."""

    if limit is None:
        limit = len(data)
    commands: list[BinCommand] = []
    position = start
    while position < limit:
        command = decode_command(data, position, limit)
        commands.append(command)
        position = command.end
    return tuple(commands)


def display_record_definitions(
    commands: tuple[BinCommand, ...],
) -> tuple[DisplayRecordDefinition, ...]:
    """Return display records appended by a linear command sequence.

    Branches can skip definitions at runtime. The returned order is therefore
    a static linear view, not a control-flow simulation.
    """

    definitions: list[DisplayRecordDefinition] = []
    for command in commands:
        if command.opcode == 0x06:
            values = [int(operand.value) for operand in command.operands]
            definitions.append(
                DisplayRecordDefinition(
                    command.offset, kind=0x06, delay=values[0]
                )
            )
        elif command.opcode == 0x02:
            values = [int(operand.value) for operand in command.operands]
            definitions.append(
                DisplayRecordDefinition(
                    command.offset,
                    kind=0x02,
                    thread_slot=values[0],
                    x=values[1],
                    y=values[2],
                    scale=values[3],
                )
            )
        elif command.opcode == 0x03:
            values = [int(operand.value) for operand in command.operands]
            definitions.append(
                DisplayRecordDefinition(
                    command.offset,
                    kind=0x03,
                    frame=values[0],
                    art_slot=values[1],
                    x=values[2],
                    y=values[3],
                    scale=0x0100,
                    flags=values[4],
                )
            )
        elif command.opcode in (0x04, 0x43):
            values = [int(operand.value) for operand in command.operands]
            definitions.append(
                DisplayRecordDefinition(
                    command.offset,
                    kind=0x43,
                    frame=values[0],
                    art_slot=values[1],
                    x=values[2],
                    y=values[3],
                    scale=values[4],
                    flags=values[5],
                )
            )
    return tuple(definitions)


def dialogue_choice_definitions(
    commands: tuple[BinCommand, ...],
) -> tuple[DialogueChoiceDefinition, ...]:
    """Return choices added by a linear command sequence.

    Branches can change which clear, add, and present commands execute. The
    returned order is therefore a static inventory, not a reconstructed menu
    for every possible runtime path.
    """

    definitions: list[DialogueChoiceDefinition] = []
    for command in commands:
        if command.opcode != 0x44:
            continue
        target = int(command.operands[0].value)
        text = command.operands[1].value
        if not isinstance(text, (str, int)):
            raise AssertionError("dialogue choice has an invalid text operand")
        definitions.append(DialogueChoiceDefinition(command.offset, target, text))
    return tuple(definitions)


def animation_sequence_definitions(
    commands: tuple[BinCommand, ...],
) -> tuple[AnimationSequenceDefinition, ...]:
    """Return animation headers with immediately following step records."""

    definitions: list[AnimationSequenceDefinition] = []
    for index, command in enumerate(commands):
        if command.opcode != 0x06:
            continue
        steps: list[bytes] = []
        position = index + 1
        while position < len(commands) and commands[position].opcode == 0x07:
            steps.append(bytes(commands[position].operands[0].value))
            position += 1
        definitions.append(
            AnimationSequenceDefinition(
                command.offset,
                int(command.operands[0].value),
                tuple(steps),
            )
        )
    return tuple(definitions)


def action_target_definitions(
    commands: tuple[BinCommand, ...],
) -> tuple[ActionTargetDefinition, ...]:
    """Return selectable action records from a linear command sequence."""

    definitions: list[ActionTargetDefinition] = []
    for command in commands:
        if command.opcode != 0x3A:
            continue
        selector = command.operands[3].value
        if not isinstance(selector, (str, int)):
            raise AssertionError("action target has an invalid selector operand")
        definitions.append(
            ActionTargetDefinition(
                command.offset,
                int(command.operands[0].value),
                int(command.operands[1].value),
                int(command.operands[2].value),
                selector,
            )
        )
    return tuple(definitions)


def _format_operand(operand: Operand, is_script_variable: bool = False) -> str:
    if is_script_variable:
        value = int(operand.value)
        if value % 2 == 0 and 0 <= value < 200:
            index = value // 2
            name = SCRIPT_VARIABLE_NAMES.get(index)
            suffix = f":{name}" if name else ""
            return f"var[{index:02d}{suffix}]@{value:#06x}"
    if operand.kind == "u8":
        return f"{operand.value:#04x}"
    if operand.kind == "u16":
        value = int(operand.value)
        if value >= 0x8000:
            return f"{value:#06x} ({value - 0x10000})"
        return f"{value:#06x}"
    if operand.kind == "record9":
        return bytes(operand.value).hex(" ")
    if operand.kind == "string_offset":
        return f"@{int(operand.value):#06x}"
    return repr(operand.value)


def parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decode a Captain Bible BIN scene command stream."
    )
    parser.add_argument("input", type=Path, help="expanded BIN resource")
    parser.add_argument(
        "--start", type=parse_int, default=0, help="starting offset (default: 0)"
    )
    parser.add_argument(
        "--limit", type=parse_int, help="exclusive ending offset (default: EOF)"
    )
    parser.add_argument(
        "--objects",
        action="store_true",
        help="summarize display-record definitions after the command listing",
    )
    parser.add_argument(
        "--choices",
        action="store_true",
        help="summarize dialogue-choice definitions after the command listing",
    )
    parser.add_argument(
        "--animations",
        action="store_true",
        help="summarize animation sequences after the command listing",
    )
    parser.add_argument(
        "--actions",
        action="store_true",
        help="summarize selectable action targets after the command listing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = args.input.read_bytes()
    try:
        commands = decode_stream(data, args.start, args.limit)
    except BinFormatError as error:
        print(f"{args.input}: {error}", file=sys.stderr)
        return 1

    for command in commands:
        variable_positions = SCRIPT_VARIABLE_OPERANDS.get(command.opcode, ())
        operands = ", ".join(
            _format_operand(value, index in variable_positions)
            for index, value in enumerate(command.operands)
        )
        suffix = f" {operands}" if operands else ""
        print(
            f"{command.offset:04x}-{command.end:04x} "
            f"{command.opcode:02x} {command.name}{suffix}"
        )
    end = commands[-1].end if commands else args.start
    print(
        f"# {len(commands)} commands, {end - args.start} bytes "
        f"({args.start:#x}-{end:#x})"
    )
    if args.objects:
        definitions = display_record_definitions(commands)
        print(
            "# display records in linear definition order; "
            "branches may skip them"
        )
        for index, definition in enumerate(definitions):
            fields = [
                f"display[{index:02d}]",
                f"source={definition.offset:#06x}",
                f"type={definition.kind:#04x}",
            ]
            for name in (
                "delay",
                "thread_slot",
                "x",
                "y",
                "scale",
                "flags",
                "frame",
                "art_slot",
            ):
                value = getattr(definition, name)
                if value is not None:
                    fields.append(f"{name}={value:#06x}")
            print(" ".join(fields))
    if args.choices:
        definitions = dialogue_choice_definitions(commands)
        print(
            "# dialogue choices in linear definition order; "
            "branches may change each menu"
        )
        for index, definition in enumerate(definitions):
            text = (
                repr(definition.text)
                if isinstance(definition.text, str)
                else f"@{definition.text:#06x}"
            )
            print(
                f"choice[{index:02d}] source={definition.offset:#06x} "
                f"target={definition.target:#06x} text={text}"
            )
    if args.animations:
        definitions = animation_sequence_definitions(commands)
        print(
            "# animation sequences in linear definition order; "
            "branches may skip them"
        )
        for index, definition in enumerate(definitions):
            fields = [
                f"animation[{index:02d}]",
                f"source={definition.offset:#06x}",
                f"interval={definition.interval}",
                f"steps={len(definition.steps)}",
            ]
            if definition.steps:
                fields.append(f"first={definition.steps[0].hex()}")
            print(" ".join(fields))
    if args.actions:
        definitions = action_target_definitions(commands)
        print(
            "# selectable actions in linear definition order; "
            "branches may change active targets"
        )
        for index, definition in enumerate(definitions):
            selector = (
                repr(definition.selector)
                if isinstance(definition.selector, str)
                else f"@{definition.selector:#06x}"
            )
            fields = [
                f"action[{index:02d}]",
                f"source={definition.offset:#06x}",
                f"target={definition.target:#06x}",
                f"x={definition.x}",
                f"y={definition.y}",
                f"selector={selector}",
            ]
            label = ACTION_LABELS.get(definition.selector)
            if label is not None:
                fields.append(f"label={label}")
            print(" ".join(fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
