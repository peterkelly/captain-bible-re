#!/usr/bin/env python3
"""Validate and summarize a Miles AIL/MIDPAK global timbre library."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


class MidpakAdFormatError(ValueError):
    """Raised when an AIL global timbre library is malformed."""


@dataclass(frozen=True)
class Timbre:
    patch: int
    bank: int
    offset: int
    length: int
    transpose: int
    modulator: bytes
    feedback_connection: int
    carrier: bytes

    @property
    def percussion(self) -> bool:
        return self.bank == 0x7F


@dataclass(frozen=True)
class TimbreLibrary:
    directory_end: int
    timbres: tuple[Timbre, ...]

    @property
    def melodic(self) -> tuple[Timbre, ...]:
        return tuple(timbre for timbre in self.timbres if not timbre.percussion)

    @property
    def percussion(self) -> tuple[Timbre, ...]:
        return tuple(timbre for timbre in self.timbres if timbre.percussion)


def parse_midpak_ad(data: bytes) -> TimbreLibrary:
    """Parse and strictly validate a two-operator AIL timbre library."""

    headers: list[tuple[int, int, int]] = []
    position = 0
    while True:
        if position + 2 > len(data):
            raise MidpakAdFormatError("missing directory terminator")
        patch, bank = data[position : position + 2]
        if patch == 0xFF or bank == 0xFF:
            directory_end = position + 2
            break
        if patch > 127:
            raise MidpakAdFormatError(
                f"patch {patch:#04x} at {position:#x} exceeds MIDI range"
            )
        if position + 6 > len(data):
            raise MidpakAdFormatError(f"truncated directory entry at {position:#x}")
        offset = int.from_bytes(data[position + 2 : position + 6], "little")
        headers.append((patch, bank, offset))
        position += 6

    if not headers:
        raise MidpakAdFormatError("timbre directory is empty")
    if headers[0][2] != directory_end:
        raise MidpakAdFormatError("first timbre does not follow the directory")

    identities = [(patch, bank) for patch, bank, _ in headers]
    if len(set(identities)) != len(identities):
        raise MidpakAdFormatError("duplicate patch/bank directory entry")

    timbres = []
    for index, (patch, bank, offset) in enumerate(headers):
        limit = headers[index + 1][2] if index + 1 < len(headers) else len(data)
        if offset + 2 > len(data):
            raise MidpakAdFormatError(f"timbre at {offset:#x} is truncated")
        length = int.from_bytes(data[offset : offset + 2], "little")
        if length != 14:
            raise MidpakAdFormatError(
                f"unsupported timbre length {length} at {offset:#x}"
            )
        if offset + length != limit:
            raise MidpakAdFormatError(
                f"timbre at {offset:#x} does not end at next offset {limit:#x}"
            )
        body = data[offset + 2 : offset + length]
        transpose = int.from_bytes(body[0:1], "little", signed=True)
        timbres.append(
            Timbre(
                patch=patch,
                bank=bank,
                offset=offset,
                length=length,
                transpose=transpose,
                modulator=body[1:6],
                feedback_connection=body[6],
                carrier=body[7:12],
            )
        )

    return TimbreLibrary(directory_end, tuple(timbres))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize a Miles AIL/MIDPAK .AD timbre bank."
    )
    parser.add_argument("input", type=Path, help="AIL/MIDPAK .AD file")
    parser.add_argument(
        "--list", action="store_true", help="list every patch and OPL register tuple"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        library = parse_midpak_ad(args.input.read_bytes())
    except (OSError, MidpakAdFormatError) as error:
        print(f"{args.input}: {error}", file=sys.stderr)
        return 1

    print(
        f"{args.input}: timbres={len(library.timbres)}, "
        f"melodic={len(library.melodic)}, percussion={len(library.percussion)}, "
        f"directory_end={library.directory_end:#x}"
    )
    if args.list:
        for timbre in library.timbres:
            kind = "percussion" if timbre.percussion else "melodic"
            print(
                f"patch={timbre.patch:03d} bank={timbre.bank:03d} "
                f"kind={kind:10s} offset={timbre.offset:#06x} "
                f"transpose={timbre.transpose:+d} "
                f"mod={timbre.modulator.hex()} "
                f"fb={timbre.feedback_connection:02x} "
                f"car={timbre.carrier.hex()}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
