#!/usr/bin/env python3
"""Decode Captain Bible BIN scene bytecode into a linear command listing."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


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


# Operand layout recovered from execute_bin_commands at load-module offset
# 0x451b. B is an unsigned byte, H is a little-endian 16-bit word, z is a
# NUL-terminated CP437 string, 9 is a nine-byte opaque animation record, and
# s adds another word when the immediately preceding H is negative.
OPCODE_SCHEMAS = {
    0x01: "z", 0x02: "BHHH", 0x03: "BBHHB", 0x04: "BBHHHB",
    0x05: "", 0x06: "H", 0x07: "9", 0x08: "BB", 0x09: "B",
    0x0A: "", 0x0B: "BB", 0x0C: "BBz", 0x0D: "zz", 0x0E: "",
    0x0F: "H", 0x10: "BHHz", 0x11: "BHs", 0x12: "BHs",
    0x13: "H", 0x14: "z", 0x15: "B", 0x16: "HHH", 0x17: "BHs",
    0x18: "BHs", 0x19: "BHs", 0x1A: "BHs", 0x1B: "H",
    0x1C: "B", 0x1D: "B", 0x1E: "HH", 0x1F: "HH",
    0x20: "HH", 0x21: "HH", 0x22: "HHH", 0x23: "HHH",
    0x24: "HHH", 0x25: "HHH", 0x26: "HHH", 0x27: "HHH",
    0x28: "HHH", 0x29: "HHH", 0x2A: "HH", 0x2B: "HH",
    0x2C: "HH", 0x2D: "HH", 0x2E: "HH", 0x2F: "HH",
    0x30: "HH", 0x31: "HH", 0x32: "H", 0x33: "H",
    0x34: "H", 0x35: "", 0x36: "B", 0x37: "B", 0x38: "BH",
    0x39: "BH", 0x3A: "HHHz", 0x3B: "B", 0x3C: "B",
    0x3D: "H", 0x3E: "BH", 0x3F: "B", 0x40: "B", 0x41: "",
    0x42: "", 0x43: "BBHHHB", 0x44: "Hz", 0x45: "",
    0x46: "", 0x47: "B", 0x48: "z", 0x49: "", 0x4A: "",
    0x4B: "", 0x4C: "B", 0x4D: "z", 0x4E: "z", 0x4F: "BB",
    0x50: "", 0x51: "BHB", 0x52: "B", 0x53: "B", 0x54: "B",
    0x55: "", 0x56: "", 0x57: "BH", 0x58: "", 0x59: "",
    0x5A: "H", 0x5B: "B", 0x5C: "BBB", 0x5D: "BBB",
    0x5E: "H", 0x5F: "BBB", 0x60: "", 0x61: "B", 0x62: "H",
    0x63: "H", 0x64: "H", 0x65: "BB", 0x66: "BBBB",
    0x67: "", 0x68: "H", 0x69: "H", 0x6A: "HH", 0x6B: "B",
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
    0x05: "return_minus_one",
    0x06: "set_animation_delay",
    0x07: "skip_animation_record",
    0x0D: "change_scene",
    0x0F: "adjust_thread_delay",
    0x1F: "set_variable",
    0x21: "jump_if_zero",
    0x32: "increment_variable",
    0x33: "decrement_variable",
    0x34: "call",
    0x35: "return",
    0x3D: "jump",
    0x4D: "load_palette",
    0x52: "play_music",
    0x55: "snapshot_state",
    0x57: "play_sound_effect",
    0x58: "stop_sound_effect",
    0x6D: "load_palette",
    0x70: "unload_last_art",
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


def _format_operand(operand: Operand) -> str:
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
        operands = ", ".join(_format_operand(value) for value in command.operands)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
