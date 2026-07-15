#!/usr/bin/env python3
"""Inspect and extract Captain Bible's DD1.DAT resource container."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys


ENTRY = struct.Struct("<8s4sIII")
MAGIC = b"GC"


class DD1FormatError(ValueError):
    """Raised when a DD1 container violates its on-disk invariants."""


@dataclass(frozen=True)
class DD1Entry:
    index: int
    name: str
    extension: str
    marker: int
    offset: int
    expanded_size: int
    stored_size: int

    @property
    def filename(self) -> str:
        if self.extension:
            return f"{self.name}.{self.extension}"
        return self.name


def _decode_ascii_field(raw: bytes, label: str) -> str:
    value, separator, padding = raw.partition(b"\0")
    if separator and any(padding):
        raise DD1FormatError(f"nonzero padding in {label}")
    try:
        return value.decode("ascii")
    except UnicodeDecodeError as error:
        raise DD1FormatError(f"non-ASCII {label}") from error


def decode_gc_dictionary(source: bytes, expected_size: int) -> bytes:
    """Decode the marker-1 dictionary stream after its two-byte GC magic."""

    position = 0
    output = bytearray()
    prefixes = [-1] * 0x1001
    suffixes = bytearray(0x1001)
    for value in range(0x100):
        suffixes[value] = value

    def read_byte(context: str) -> int:
        nonlocal position
        if position >= len(source):
            raise DD1FormatError(f"truncated compressed stream ({context})")
        value = source[position]
        position += 1
        return value

    while len(output) < expected_size:
        first_code = read_byte("initial literal")
        prefixes[0x100] = first_code
        output.append(first_code)
        next_code = 0x101
        plane_bytes: list[int] = []
        plane_bit = 8

        while next_code < 0x1001 and len(output) < expected_size:
            if plane_bit == 8:
                plane_count = 0
                code_limit = 0x100
                while next_code > code_limit:
                    plane_count += 1
                    code_limit <<= 1
                plane_bytes = [
                    read_byte("high-bit plane") for _ in range(plane_count)
                ]
                plane_bit = 0

            code = read_byte("code low byte")
            for bit, value in enumerate(plane_bytes):
                code |= (value & 1) << (8 + bit)
                plane_bytes[bit] >>= 1
            plane_bit += 1

            if code >= next_code:
                raise DD1FormatError(
                    f"dictionary code is not defined yet: {code:#x}"
                )
            prefixes[next_code] = code

            suffix_chain: list[int] = []
            cursor = code
            depth = 0
            while prefixes[cursor] != -1:
                suffix_chain.append(cursor)
                cursor = prefixes[cursor]
                depth += 1
                if depth > 0x1000:
                    raise DD1FormatError("cycle in compressed dictionary")

            first_character = suffixes[cursor]
            suffixes[next_code - 1] = first_character
            output.append(first_character)
            for cursor in reversed(suffix_chain):
                output.append(suffixes[cursor])
            if len(output) > expected_size:
                raise DD1FormatError("compressed member exceeds expanded size")
            next_code += 1

    if position != len(source):
        raise DD1FormatError(
            f"compressed member has {len(source) - position} trailing bytes"
        )
    return bytes(output)


class DD1Archive:
    def __init__(self, data: bytes, entries: list[DD1Entry]) -> None:
        self.data = data
        self.entries = entries

    @classmethod
    def from_bytes(cls, data: bytes) -> "DD1Archive":
        if len(data) < 2:
            raise DD1FormatError("container is shorter than its entry count")

        count = struct.unpack_from("<H", data)[0]
        directory_size = 2 + count * ENTRY.size
        if directory_size > len(data):
            raise DD1FormatError("directory extends past the end of the file")

        entries: list[DD1Entry] = []
        expected_offset = directory_size
        for index in range(count):
            position = 2 + index * ENTRY.size
            raw_name, raw_kind, offset, expanded_size, stored_size = (
                ENTRY.unpack_from(data, position)
            )
            name = _decode_ascii_field(raw_name, f"entry {index} name")
            extension = _decode_ascii_field(
                raw_kind[1:], f"entry {index} extension"
            )
            marker = raw_kind[0]

            if not name:
                raise DD1FormatError(f"entry {index} has an empty name")
            if marker not in (0, 1):
                raise DD1FormatError(
                    f"entry {index} has unsupported marker {marker:#x}"
                )
            if offset != expected_offset:
                raise DD1FormatError(
                    f"entry {index} starts at {offset:#x}, "
                    f"expected {expected_offset:#x}"
                )
            if stored_size < len(MAGIC):
                raise DD1FormatError(f"entry {index} is shorter than GC magic")
            end = offset + stored_size
            if end > len(data):
                raise DD1FormatError(f"entry {index} extends past end of file")
            if data[offset : offset + len(MAGIC)] != MAGIC:
                raise DD1FormatError(f"entry {index} is missing GC magic")
            if marker == 0 and stored_size != expanded_size + len(MAGIC):
                raise DD1FormatError(
                    f"raw entry {index} size does not include only GC magic"
                )

            entries.append(
                DD1Entry(
                    index=index,
                    name=name,
                    extension=extension,
                    marker=marker,
                    offset=offset,
                    expanded_size=expanded_size,
                    stored_size=stored_size,
                )
            )
            expected_offset = end

        if expected_offset != len(data):
            raise DD1FormatError(
                f"container has {len(data) - expected_offset} trailing bytes"
            )
        return cls(data, entries)

    @classmethod
    def from_path(cls, path: Path) -> "DD1Archive":
        return cls.from_bytes(path.read_bytes())

    def matching(self, filename: str) -> list[DD1Entry]:
        folded = filename.casefold()
        return [
            entry for entry in self.entries if entry.filename.casefold() == folded
        ]

    def extract(self, entry: DD1Entry) -> bytes:
        payload = self.data[entry.offset : entry.offset + entry.stored_size]
        body = payload[len(MAGIC) :]
        if entry.marker == 0:
            result = body
        else:
            result = decode_gc_dictionary(body, entry.expanded_size)
        if len(result) != entry.expanded_size:
            raise DD1FormatError(
                f"{entry.filename} expanded to {len(result)} bytes, "
                f"expected {entry.expanded_size}"
            )
        return result


def print_entries(archive: DD1Archive) -> None:
    print("index marker offset stored expanded filename")
    for entry in archive.entries:
        print(
            f"{entry.index:03d} {entry.marker} {entry.offset:08x} "
            f"{entry.stored_size:7d} {entry.expanded_size:8d} "
            f"{entry.filename}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="path to DD1.DAT")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list members")
    action.add_argument("--extract", metavar="NAME.EXT", help="extract by name")
    action.add_argument("--index", type=int, help="extract by directory index")
    action.add_argument(
        "--extract-all", type=Path, metavar="DIRECTORY", help="extract all members"
    )
    parser.add_argument("--output", type=Path, help="output for one member")
    args = parser.parse_args(argv)
    if (args.extract is not None or args.index is not None) and args.output is None:
        parser.error("--extract and --index require --output")
    if args.output is not None and args.extract is None and args.index is None:
        parser.error("--output requires --extract or --index")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        archive = DD1Archive.from_path(args.archive)
        if args.extract is not None:
            matches = archive.matching(args.extract)
            if not matches:
                raise DD1FormatError(f"member not found: {args.extract}")
            if len(matches) > 1:
                indices = ", ".join(str(entry.index) for entry in matches)
                raise DD1FormatError(
                    f"member is ambiguous: {args.extract} (indices {indices})"
                )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(archive.extract(matches[0]))
        elif args.index is not None:
            if args.index < 0 or args.index >= len(archive.entries):
                raise DD1FormatError(f"entry index out of range: {args.index}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(archive.extract(archive.entries[args.index]))
        elif args.extract_all is not None:
            args.extract_all.mkdir(parents=True, exist_ok=True)
            for entry in archive.entries:
                filename = f"{entry.index:03d}_{entry.filename}"
                (args.extract_all / filename).write_bytes(archive.extract(entry))
        else:
            print_entries(archive)
    except (DD1FormatError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
