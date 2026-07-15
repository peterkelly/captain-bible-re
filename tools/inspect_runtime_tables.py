#!/usr/bin/env python3
"""Inspect Captain Bible action, animation, and BIN-thread memory tables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys

from inspect_bin import (
    ACTION_LABELS,
    action_target_definitions,
    animation_sequence_definitions,
    decode_stream,
)


ACTION_TABLE_OFFSET = 0x480E
ACTION_COUNT_OFFSET = 0x6EA4
ACTION_RECORD_SIZE = 10
ANIMATION_TABLE_OFFSET = 0x6EBA
ANIMATION_COUNT_OFFSET = 0xB114
ANIMATION_RECORD_SIZE = 12
THREAD_CURRENT_OFFSET = 0x7DB4
THREAD_TABLE_OFFSET = 0x8D44
THREAD_RECORD_SIZE = 16
DEFAULT_THREAD_SLOTS = 10


class RuntimeTableError(ValueError):
    """Raised when a memory dump cannot contain the requested tables."""


@dataclass(frozen=True)
class ActionRecord:
    target: int
    x: int
    y: int
    selector_offset: int
    active: int
    reserved: int


@dataclass(frozen=True)
class AnimationRecord:
    first_step: int
    current_step: int
    interval: int
    link: int
    state: int
    render_slot: int
    timing: int


@dataclass(frozen=True)
class ThreadRecord:
    cursor: int
    opaque: bytes
    delay: int
    active: int
    status: int


@dataclass(frozen=True)
class RuntimeTables:
    data_segment: int
    action_records: tuple[ActionRecord, ...]
    animation_records: tuple[AnimationRecord, ...]
    current_thread: int
    thread_records: tuple[ThreadRecord, ...]


def _physical(data_segment: int, offset: int) -> int:
    return data_segment * 16 + offset


def _slice(memory: bytes, position: int, size: int, label: str) -> bytes:
    if position < 0 or position + size > len(memory):
        raise RuntimeTableError(
            f"{label} at physical {position:#x} needs {size} byte(s), "
            f"but the dump is {len(memory)} bytes"
        )
    return memory[position : position + size]


def _word(memory: bytes, data_segment: int, offset: int, label: str) -> int:
    position = _physical(data_segment, offset)
    return struct.unpack("<H", _slice(memory, position, 2, label))[0]


def parse_runtime_tables(
    memory: bytes,
    data_segment: int,
    thread_slots: int = DEFAULT_THREAD_SLOTS,
) -> RuntimeTables:
    """Decode the three runtime tables from a physical-memory dump."""

    if not 0 <= data_segment <= 0xFFFF:
        raise RuntimeTableError("data segment must fit in 16 bits")
    if thread_slots < 0:
        raise RuntimeTableError("thread slot count must not be negative")

    action_count = _word(
        memory, data_segment, ACTION_COUNT_OFFSET, "action count"
    )
    animation_count = _word(
        memory, data_segment, ANIMATION_COUNT_OFFSET, "animation count"
    )
    if action_count > 0x100:
        raise RuntimeTableError(f"implausible action count {action_count}")
    if animation_count > 0x100:
        raise RuntimeTableError(f"implausible animation count {animation_count}")

    action_data = _slice(
        memory,
        _physical(data_segment, ACTION_TABLE_OFFSET),
        action_count * ACTION_RECORD_SIZE,
        "action table",
    )
    actions = tuple(
        ActionRecord(*struct.unpack_from("<HHHHBB", action_data, index * 10))
        for index in range(action_count)
    )

    animation_data = _slice(
        memory,
        _physical(data_segment, ANIMATION_TABLE_OFFSET),
        animation_count * ANIMATION_RECORD_SIZE,
        "animation table",
    )
    animations = tuple(
        AnimationRecord(
            *struct.unpack_from("<HHHhBBH", animation_data, index * 12)
        )
        for index in range(animation_count)
    )

    thread_data = _slice(
        memory,
        _physical(data_segment, THREAD_TABLE_OFFSET),
        thread_slots * THREAD_RECORD_SIZE,
        "thread table",
    )
    threads = tuple(
        ThreadRecord(
            cursor=struct.unpack_from("<H", thread_data, index * 16)[0],
            opaque=thread_data[index * 16 + 2 : index * 16 + 12],
            delay=struct.unpack_from("<h", thread_data, index * 16 + 12)[0],
            active=thread_data[index * 16 + 14],
            status=thread_data[index * 16 + 15],
        )
        for index in range(thread_slots)
    )
    current_thread = _word(
        memory, data_segment, THREAD_CURRENT_OFFSET, "current thread index"
    )
    return RuntimeTables(
        data_segment, actions, animations, current_thread, threads
    )


def parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("memory", type=Path, help="physical-memory dump")
    parser.add_argument(
        "--data-segment",
        type=parse_int,
        required=True,
        help="runtime DS value, for example 0x14e1",
    )
    parser.add_argument(
        "--bin",
        type=Path,
        help="optional loaded BIN resource for static comparison",
    )
    parser.add_argument(
        "--thread-slots",
        type=parse_int,
        default=DEFAULT_THREAD_SLOTS,
        help=f"number of thread records to show (default {DEFAULT_THREAD_SLOTS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        memory = args.memory.read_bytes()
        tables = parse_runtime_tables(
            memory, args.data_segment, args.thread_slots
        )
        commands = decode_stream(args.bin.read_bytes()) if args.bin else None
    except (OSError, RuntimeTableError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"memory: {len(memory)} bytes; DS={tables.data_segment:04x}; "
        f"base={tables.data_segment * 16:#x}"
    )
    static_actions = action_target_definitions(commands) if commands else ()
    static_action_commands = (
        tuple(command for command in commands if command.opcode == 0x3A)
        if commands
        else ()
    )
    action_matches = 0
    print(f"actions: {len(tables.action_records)}")
    for index, record in enumerate(tables.action_records):
        fields = [
            f"action[{index:02d}]",
            f"target={record.target:#06x}",
            f"x={record.x}",
            f"y={record.y}",
            f"selector_offset={record.selector_offset:#06x}",
            f"active={record.active}",
            f"reserved={record.reserved}",
        ]
        if index < len(static_actions):
            definition = static_actions[index]
            command = static_action_commands[index]
            selector_operand = command.operands[3]
            expected_selector = (
                definition.offset + 7
                if selector_operand.kind == "string"
                else int(selector_operand.value)
            )
            matches = (
                record.target,
                record.x,
                record.y,
                record.selector_offset,
            ) == (
                definition.target,
                definition.x,
                definition.y,
                expected_selector,
            )
            if matches:
                action_matches += 1
            fields.append(f"static={'match' if matches else 'MISMATCH'}")
            fields.append(f"selector={definition.selector!r}")
            label = ACTION_LABELS.get(definition.selector)
            if label:
                fields.append(f"label={label}")
        print(" ".join(fields))

    static_animations = (
        animation_sequence_definitions(commands) if commands else ()
    )
    animation_matches = 0
    print(f"animations: {len(tables.animation_records)}")
    for index, record in enumerate(tables.animation_records):
        fields = [
            f"animation[{index:02d}]",
            f"first={record.first_step:#06x}",
            f"current={record.current_step:#06x}",
            f"interval={record.interval}",
            f"link={record.link}",
            f"state={record.state:#04x}",
            f"render={record.render_slot:#04x}",
            f"timing={record.timing:#06x}",
        ]
        if index < len(static_animations):
            definition = static_animations[index]
            matches = (
                record.first_step == definition.offset + 3
                and record.interval == definition.interval
            )
            if matches:
                animation_matches += 1
            fields.append(f"static={'match' if matches else 'MISMATCH'}")
        print(" ".join(fields))

    print(
        f"threads: current={tables.current_thread}; "
        f"shown={len(tables.thread_records)}"
    )
    for index, record in enumerate(tables.thread_records):
        print(
            f"thread[{index:02d}] cursor={record.cursor:#06x} "
            f"opaque={record.opaque.hex()} delay={record.delay} "
            f"active={record.active} status={record.status}"
        )

    if commands is not None:
        print(
            "comparison: "
            f"actions={action_matches}/{len(static_actions)}; "
            f"animations={animation_matches}/{len(static_animations)}"
        )
        if action_matches != len(static_actions) or animation_matches != len(
            static_animations
        ):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
