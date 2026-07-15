#!/usr/bin/env python3
"""Inspect Captain Bible SV0 save indexes and SV1-SV9/SVQ states."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


INDEX_RECORD_SIZE = 27
INDEX_SLOT_COUNT = 9
INDEX_SIZE = INDEX_RECORD_SIZE * INDEX_SLOT_COUNT
STATE_SIZE = 2752
DESCRIPTOR_COUNT = 66
DESCRIPTOR_SIZE = 10


class SaveFormatError(ValueError):
    """Raised when a save index or state has an invalid structure."""


@dataclass(frozen=True)
class SlotLabel:
    text: str
    raw: bytes
    stale_tail: bytes


@dataclass(frozen=True)
class SaveIndex:
    slots: tuple[SlotLabel, ...]


@dataclass(frozen=True)
class TextDescriptor:
    far_offset: int
    far_segment: int
    state: int
    selector: int
    data_offset: int
    data_span: int


@dataclass(frozen=True)
class SaveState:
    primary_snapshot: bytes
    primary_live: bytes
    record_flags: tuple[int, ...]
    text_descriptors: tuple[TextDescriptor, ...]
    resource_name_snapshot: str
    resource_name_live: str
    resource_extension_snapshot: str
    resource_extension_live: str
    translation: int
    music_enabled: int
    effects_enabled: int
    text_bank_snapshot: int
    text_bank_live: int
    three_byte_table_live: bytes
    three_byte_table_snapshot: bytes


def _decode_c_buffer(raw: bytes, context: str) -> tuple[str, bytes]:
    nul = raw.find(b"\0")
    if nul < 0:
        visible = raw
        tail = b""
    else:
        visible = raw[:nul]
        tail = raw[nul + 1 :]
    try:
        return visible.decode("cp437"), tail
    except UnicodeDecodeError as error:
        raise SaveFormatError(f"invalid CP437 in {context}") from error


def parse_save_index(data: bytes) -> SaveIndex:
    """Parse the nine fixed-size label buffers in an SV0 file."""

    if len(data) != INDEX_SIZE:
        raise SaveFormatError(
            f"save index is {len(data)} bytes; expected {INDEX_SIZE}"
        )
    slots = []
    for slot in range(INDEX_SLOT_COUNT):
        start = slot * INDEX_RECORD_SIZE
        raw = data[start : start + INDEX_RECORD_SIZE]
        text, stale_tail = _decode_c_buffer(raw, f"slot {slot + 1} label")
        slots.append(SlotLabel(text, raw, stale_tail))
    return SaveIndex(tuple(slots))


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _state_c_string(data: bytes, offset: int, label: str) -> str:
    text, _tail = _decode_c_buffer(data[offset : offset + 20], label)
    return text


def parse_save_state(data: bytes) -> SaveState:
    """Parse the fixed 2,752-byte game-state layout."""

    if len(data) != STATE_SIZE:
        raise SaveFormatError(
            f"save state is {len(data)} bytes; expected {STATE_SIZE}"
        )

    descriptor_data = data[0x1D2:0x466]
    descriptors = []
    for offset in range(0, len(descriptor_data), DESCRIPTOR_SIZE):
        record = descriptor_data[offset : offset + DESCRIPTOR_SIZE]
        descriptors.append(
            TextDescriptor(
                far_offset=_u16(record, 0),
                far_segment=_u16(record, 2),
                state=record[4],
                selector=record[5],
                data_offset=_u16(record, 6),
                data_span=_u16(record, 8),
            )
        )
    if len(descriptors) != DESCRIPTOR_COUNT:
        raise SaveFormatError("internal descriptor-block size mismatch")

    return SaveState(
        primary_snapshot=data[0x000:0x0C8],
        primary_live=data[0x0C8:0x190],
        record_flags=tuple(data[0x190:0x1D2]),
        text_descriptors=tuple(descriptors),
        resource_name_snapshot=_state_c_string(data, 0x466, "resource name"),
        resource_name_live=_state_c_string(data, 0x47A, "live resource name"),
        resource_extension_snapshot=_state_c_string(
            data, 0x48E, "resource extension"
        ),
        resource_extension_live=_state_c_string(
            data, 0x4A2, "live resource extension"
        ),
        translation=_u16(data, 0x4B6),
        music_enabled=_u16(data, 0x4B8),
        effects_enabled=_u16(data, 0x4BA),
        text_bank_snapshot=_u16(data, 0x4BC),
        text_bank_live=_u16(data, 0x4BE),
        three_byte_table_live=data[0x4C0:0x7C0],
        three_byte_table_snapshot=data[0x7C0:0xAC0],
    )


def parse_save(data: bytes) -> SaveIndex | SaveState:
    """Select the SV0 or state parser by the two exact on-disk sizes."""

    if len(data) == INDEX_SIZE:
        return parse_save_index(data)
    if len(data) == STATE_SIZE:
        return parse_save_state(data)
    raise SaveFormatError(
        f"unrecognized save size {len(data)}; expected {INDEX_SIZE} or {STATE_SIZE}"
    )


def _display_byte(value: int) -> str:
    if 0x20 <= value < 0x7F:
        return f"{value} ({chr(value)!r})"
    return str(value)


def _difference_count(left: bytes, right: bytes) -> int:
    return sum(a != b for a, b in zip(left, right))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path, help="path to an SV0-SV9 or SVQ file")
    parser.add_argument(
        "--descriptors",
        action="store_true",
        help="list all nonempty runtime text descriptors",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        parsed = parse_save(args.save.read_bytes())
    except (OSError, SaveFormatError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if isinstance(parsed, SaveIndex):
        print(f"save index: {len(parsed.slots)} slots, {INDEX_RECORD_SIZE} bytes each")
        for number, slot in enumerate(parsed.slots, 1):
            stale = sum(byte != 0 for byte in slot.stale_tail)
            note = f", {stale} nonzero stale-tail bytes" if stale else ""
            print(f"{number}: {slot.text!r}{note}")
        return 0

    active = sum(
        descriptor.selector != 0
        or descriptor.data_offset != 0
        or descriptor.data_span != 0
        for descriptor in parsed.text_descriptors
    )
    print(f"save state: {STATE_SIZE} bytes")
    print(
        "settings: "
        f"translation={parsed.translation}, music={parsed.music_enabled}, "
        f"effects={parsed.effects_enabled}"
    )
    print(
        "text bank: "
        f"snapshot={_display_byte(parsed.text_bank_snapshot)}, "
        f"live={_display_byte(parsed.text_bank_live)}"
    )
    print(
        "resource strings: "
        f"{parsed.resource_name_snapshot!r}/{parsed.resource_name_live!r}, "
        f"{parsed.resource_extension_snapshot!r}/"
        f"{parsed.resource_extension_live!r}"
    )
    print(
        f"text descriptors: {active} active of {len(parsed.text_descriptors)}; "
        f"{sum(bool(value) for value in parsed.record_flags)} nonzero flags"
    )
    print(
        "snapshot differences: "
        f"primary={_difference_count(parsed.primary_snapshot, parsed.primary_live)}, "
        f"three-byte-table="
        f"{_difference_count(parsed.three_byte_table_snapshot, parsed.three_byte_table_live)}"
    )
    if args.descriptors:
        for number, descriptor in enumerate(parsed.text_descriptors):
            if not any(
                (
                    descriptor.far_offset,
                    descriptor.far_segment,
                    descriptor.state,
                    descriptor.selector,
                    descriptor.data_offset,
                    descriptor.data_span,
                )
            ):
                continue
            print(
                f"{number:02d}: ptr={descriptor.far_segment:04x}:"
                f"{descriptor.far_offset:04x} state={descriptor.state:#04x} "
                f"selector={descriptor.selector:#04x} "
                f"data={descriptor.data_offset:#06x}+{descriptor.data_span:#06x}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
