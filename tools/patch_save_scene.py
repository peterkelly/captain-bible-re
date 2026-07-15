#!/usr/bin/env python3
"""Patch both saved scene-name fields in a Captain Bible state file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


STATE_SIZE = 2752
SCENE_FIELD_SIZE = 20
SCENE_FIELD_OFFSETS = (0x466, 0x47A)


def encode_scene_name(name: str) -> bytes:
    """Encode a NUL-terminated scene name for a 20-byte save field."""

    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("scene name must contain only ASCII characters") from error
    if not encoded:
        raise ValueError("scene name must not be empty")
    if len(encoded) >= SCENE_FIELD_SIZE:
        raise ValueError("scene name must be at most 19 ASCII bytes")
    return encoded + bytes(SCENE_FIELD_SIZE - len(encoded))


def patch_scene(data: bytes, name: str) -> bytes:
    """Return a save state with its snapshot and live scene names replaced."""

    if len(data) != STATE_SIZE:
        raise ValueError(f"save state is {len(data)} bytes; expected {STATE_SIZE}")
    field = encode_scene_name(name)
    patched = bytearray(data)
    for offset in SCENE_FIELD_OFFSETS:
        patched[offset : offset + SCENE_FIELD_SIZE] = field
    return bytes(patched)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path, help="input SV1-SV9 or SVQ file")
    parser.add_argument("scene", help="replacement scene base name")
    parser.add_argument("output", type=Path, help="output save path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = args.save.read_bytes()
        patched = patch_scene(data, args.scene)
        args.output.write_bytes(patched)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
