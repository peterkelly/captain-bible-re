#!/usr/bin/env python3
"""Validate and summarize Captain Bible's XMIDI resources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


class XmiFormatError(ValueError):
    """Raised when an IFF/XMIDI structure or event is invalid."""


@dataclass(frozen=True)
class IffChunk:
    tag: bytes
    offset: int
    size: int
    form_type: bytes | None
    payload: bytes
    children: tuple["IffChunk", ...]


@dataclass(frozen=True)
class XmiSequence:
    timbres: tuple[tuple[int, int], ...]
    event_count: int
    note_count: int
    meta_count: int
    total_delay: int
    padding: int


@dataclass(frozen=True)
class XmiFile:
    declared_sequences: int
    sequences: tuple[XmiSequence, ...]


def _parse_chunks(data: bytes, start: int, limit: int) -> tuple[IffChunk, ...]:
    chunks = []
    position = start
    while position < limit:
        if position + 8 > limit:
            raise XmiFormatError(f"truncated IFF chunk header at {position:#x}")
        tag = data[position : position + 4]
        size = int.from_bytes(data[position + 4 : position + 8], "big")
        body = position + 8
        end = body + size
        padded_end = end + (size & 1)
        if padded_end > limit:
            raise XmiFormatError(f"IFF chunk {tag!r} at {position:#x} overflows")

        form_type = None
        children: tuple[IffChunk, ...] = ()
        if tag in (b"FORM", b"CAT "):
            if size < 4:
                raise XmiFormatError(f"container {tag!r} has no form type")
            form_type = data[body : body + 4]
            children = _parse_chunks(data, body + 4, end)
        chunks.append(
            IffChunk(
                tag=tag,
                offset=position,
                size=size,
                form_type=form_type,
                payload=data[body:end],
                children=children,
            )
        )
        position = padded_end
    if position != limit:
        raise XmiFormatError("IFF region did not end on a chunk boundary")
    return tuple(chunks)


def _read_vlq(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if position >= len(data):
            raise XmiFormatError("truncated XMIDI variable-length quantity")
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, position
    raise XmiFormatError("XMIDI variable-length quantity exceeds four bytes")


def _require_event_bytes(data: bytes, position: int, size: int) -> None:
    if position + size > len(data):
        raise XmiFormatError(f"truncated XMIDI event at {position:#x}")


def _parse_events(data: bytes) -> tuple[int, int, int, int, int]:
    position = 0
    event_count = 0
    note_count = 0
    meta_count = 0
    total_delay = 0
    reached_end = False

    while position < len(data):
        if reached_end:
            trailing = data[position:]
            if any(trailing):
                raise XmiFormatError("nonzero bytes follow the end-of-track event")
            return event_count, note_count, meta_count, total_delay, len(trailing)

        while position < len(data) and data[position] < 0x80:
            total_delay += data[position]
            position += 1
        if position >= len(data):
            raise XmiFormatError("XMIDI delay is not followed by an event")

        status = data[position]
        position += 1
        high = status & 0xF0
        if 0x80 <= status <= 0xEF:
            parameter_count = 1 if high in (0xC0, 0xD0) else 2
            _require_event_bytes(data, position, parameter_count)
            position += parameter_count
            if high == 0x90:
                _, position = _read_vlq(data, position)
                note_count += 1
        elif status in (0xF0, 0xF7):
            size, position = _read_vlq(data, position)
            _require_event_bytes(data, position, size)
            position += size
        elif status == 0xFF:
            _require_event_bytes(data, position, 1)
            meta_type = data[position]
            position += 1
            size, position = _read_vlq(data, position)
            _require_event_bytes(data, position, size)
            position += size
            meta_count += 1
            if meta_type == 0x2F:
                if size != 0:
                    raise XmiFormatError("end-of-track event has a payload")
                reached_end = True
        else:
            raise XmiFormatError(f"unsupported XMIDI status {status:#04x}")
        event_count += 1

    if not reached_end:
        raise XmiFormatError("XMIDI event stream has no end-of-track event")
    return event_count, note_count, meta_count, total_delay, 0


def parse_xmi(data: bytes) -> XmiFile:
    """Validate the IFF/XMIDI structure and return sequence summaries."""

    top = _parse_chunks(data, 0, len(data))
    if len(top) != 2:
        raise XmiFormatError("XMIDI file must contain XDIR FORM and XMID CAT")

    directory, catalog = top
    if (directory.tag, directory.form_type) != (b"FORM", b"XDIR"):
        raise XmiFormatError("first chunk is not a FORM XDIR directory")
    if len(directory.children) != 1 or directory.children[0].tag != b"INFO":
        raise XmiFormatError("XDIR does not contain exactly one INFO chunk")
    info = directory.children[0].payload
    if len(info) != 2:
        raise XmiFormatError("XDIR INFO size is not two bytes")
    declared_sequences = int.from_bytes(info, "little")

    if (catalog.tag, catalog.form_type) != (b"CAT ", b"XMID"):
        raise XmiFormatError("second chunk is not a CAT XMID catalog")
    forms = catalog.children
    if len(forms) != declared_sequences:
        raise XmiFormatError("XDIR sequence count does not match XMID forms")

    sequences = []
    for form in forms:
        if (form.tag, form.form_type) != (b"FORM", b"XMID"):
            raise XmiFormatError("XMID catalog child is not FORM XMID")
        if tuple(chunk.tag for chunk in form.children) != (b"TIMB", b"EVNT"):
            raise XmiFormatError("XMID form does not contain TIMB then EVNT")
        timbre_data = form.children[0].payload
        if len(timbre_data) % 2:
            raise XmiFormatError("TIMB chunk has an incomplete patch/bank pair")
        timbres = tuple(
            (timbre_data[index], timbre_data[index + 1])
            for index in range(0, len(timbre_data), 2)
        )
        event_stats = _parse_events(form.children[1].payload)
        sequences.append(XmiSequence(timbres, *event_stats))

    return XmiFile(declared_sequences, tuple(sequences))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize a Captain Bible XMI resource."
    )
    parser.add_argument("input", type=Path, help="expanded XMI resource")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        xmi = parse_xmi(args.input.read_bytes())
    except (OSError, XmiFormatError) as error:
        print(f"{args.input}: {error}", file=sys.stderr)
        return 1

    print(f"{args.input}: {xmi.declared_sequences} sequence(s)")
    for index, sequence in enumerate(xmi.sequences):
        print(
            f"sequence {index}: timbres={len(sequence.timbres)}, "
            f"events={sequence.event_count}, notes={sequence.note_count}, "
            f"meta={sequence.meta_count}, delay={sequence.total_delay}, "
            f"padding={sequence.padding}"
        )
        print(
            "  patches: "
            + ", ".join(f"{patch}:{bank}" for patch, bank in sequence.timbres)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
