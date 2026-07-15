#!/usr/bin/env python3
"""Inspect Captain Bible's 16x16 three-byte MAP resources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from extract_dd1 import DD1Archive
from inspect_save import parse_save_state


MAP_WIDTH = 16
MAP_HEIGHT = 16
CELL_SIZE = 3
MAP_SIZE = MAP_WIDTH * MAP_HEIGHT * CELL_SIZE
LEVELS = tuple("ABCDEFG")
DIFFICULTIES = {
    "E": "Easy",
    "N": "Normal",
    "D": "Difficult",
}
CONNECTION_DIRECTIONS = (
    (0x10, "up"),
    (0x20, "down"),
    (0x40, "left"),
    (0x80, "right"),
)
ROOM_CLASSES = (
    "victim",
    "trap",
    "prayer",
    "communications",
    "jump-tunnel",
)
ROOM_ENTRANCE_SIDES = (
    "west",
    "east",
    "south",
)
HALL_FEATURES = {
    0x1: "macho-cyber",
    0x2: "armored-cyber",
    0x3: "mantis-cyber",
    0x4: "snake-cyber",
    0x5: "spider-cyber",
    0x6: "leech-covered-station",
    0x7: "zapper-cyber",
    0x9: "hidden-spider-trigger",
    0xA: "scripture-station",
    0xB: "cleared-encounter",
    0xE: "level-exit",
}


class MapFormatError(ValueError):
    """Raised when a MAP resource has an invalid structure or name."""


@dataclass(frozen=True)
class MapCell:
    x: int
    y: int
    packed: int
    parameter_a: int
    parameter_b: int

    @property
    def connection_mask(self) -> int:
        return self.packed & 0xF0

    @property
    def location_kind(self) -> int:
        return self.packed & 0x0F

    @property
    def connection_directions(self) -> tuple[str, ...]:
        return tuple(
            direction
            for bit, direction in CONNECTION_DIRECTIONS
            if self.connection_mask & bit
        )

    @property
    def room_class(self) -> str | None:
        if self.connection_mask or not 1 <= self.location_kind <= 15:
            return None
        return ROOM_CLASSES[(self.location_kind - 1) // 3]

    @property
    def room_entrance_side(self) -> str | None:
        if self.room_class is None:
            return None
        return ROOM_ENTRANCE_SIDES[(self.location_kind - 1) % 3]

    @property
    def hall_feature(self) -> str | None:
        if not self.connection_mask:
            return None
        return HALL_FEATURES.get(self.location_kind)


@dataclass(frozen=True)
class WorldMap:
    cells: tuple[MapCell, ...]

    def cell(self, x: int, y: int) -> MapCell:
        if not 0 <= x < MAP_WIDTH or not 0 <= y < MAP_HEIGHT:
            raise IndexError(f"map coordinate ({x}, {y}) is outside 16x16")
        return self.cells[y * MAP_WIDTH + x]

    def to_bytes(self) -> bytes:
        return bytes(
            value
            for cell in self.cells
            for value in (cell.packed, cell.parameter_a, cell.parameter_b)
        )


@dataclass(frozen=True)
class MapDifference:
    x: int
    y: int
    field: int
    original: int
    current: int


def parse_map(data: bytes) -> WorldMap:
    """Parse one exact 768-byte MAP resource or saved live grid."""

    if len(data) != MAP_SIZE:
        raise MapFormatError(f"map is {len(data)} bytes; expected {MAP_SIZE}")
    cells = []
    for index in range(MAP_WIDTH * MAP_HEIGHT):
        offset = index * CELL_SIZE
        y, x = divmod(index, MAP_WIDTH)
        cells.append(
            MapCell(
                x=x,
                y=y,
                packed=data[offset],
                parameter_a=data[offset + 1],
                parameter_b=data[offset + 2],
            )
        )
    return WorldMap(tuple(cells))


def normalize_map_name(value: str) -> str:
    """Normalize a two-character level/difficulty identifier."""

    name = value.upper()
    if name.endswith(".MAP"):
        name = name[:-4]
    if len(name) != 2 or name[0] not in LEVELS or name[1] not in DIFFICULTIES:
        raise MapFormatError(
            f"invalid map {value!r}; expected level A-G plus difficulty E/N/D"
        )
    return name


def load_archive_map(archive: DD1Archive, name: str) -> WorldMap:
    """Extract and parse a named MAP member from DD1.DAT."""

    name = normalize_map_name(name)
    matches = [
        entry
        for entry in archive.entries
        if entry.name == name and entry.extension == "MAP"
    ]
    if len(matches) != 1:
        raise MapFormatError(f"expected one {name}.MAP member, found {len(matches)}")
    return parse_map(archive.extract(matches[0]))


def compare_maps(original: WorldMap, current: WorldMap) -> tuple[MapDifference, ...]:
    """Return field-level differences between two maps."""

    differences = []
    for expected, actual in zip(original.cells, current.cells):
        for field, (left, right) in enumerate(
            zip(
                (expected.packed, expected.parameter_a, expected.parameter_b),
                (actual.packed, actual.parameter_a, actual.parameter_b),
            )
        ):
            if left != right:
                differences.append(
                    MapDifference(expected.x, expected.y, field, left, right)
                )
    return tuple(differences)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="path to DD1.DAT")
    parser.add_argument(
        "--map",
        dest="map_name",
        required=True,
        help="map identifier, such as CE or CE.MAP",
    )
    parser.add_argument(
        "--cells",
        action="store_true",
        help="list all nonzero cells after the compact kind grid",
    )
    parser.add_argument(
        "--rooms",
        action="store_true",
        help="list decoded room cells and their entrance sides",
    )
    parser.add_argument(
        "--hall-features",
        action="store_true",
        help="list decoded nonempty features on connected hall cells",
    )
    parser.add_argument(
        "--compare-save",
        type=Path,
        help="compare the resource with the live grid in a state save",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        name = normalize_map_name(args.map_name)
        world_map = load_archive_map(DD1Archive.from_path(args.archive), name)
        saved_map = None
        if args.compare_save is not None:
            state = parse_save_state(args.compare_save.read_bytes())
            saved_map = parse_map(state.three_byte_table_live)
    except (OSError, MapFormatError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"{name}.MAP: level {name[0]}, {DIFFICULTIES[name[1]]}, "
        f"{MAP_WIDTH}x{MAP_HEIGHT}x{CELL_SIZE} bytes"
    )
    print("location-kind grid (low nibble):")
    print("   " + "".join(f"{x:X}" for x in range(MAP_WIDTH)))
    for y in range(MAP_HEIGHT):
        print(
            f"{y:02X} "
            + "".join(f"{world_map.cell(x, y).location_kind:X}" for x in range(16))
        )

    if args.cells:
        print("nonzero cells:")
        for cell in world_map.cells:
            if not any((cell.packed, cell.parameter_a, cell.parameter_b)):
                continue
            print(
                f"({cell.x:02d},{cell.y:02d}) packed={cell.packed:#04x} "
                f"connections={cell.connection_mask >> 4:#x}"
                f"[{','.join(cell.connection_directions) or '-'}] "
                f"kind={cell.location_kind:#x} "
                f"a={cell.parameter_a:#04x} b={cell.parameter_b:#04x}"
            )

    if args.rooms:
        print("room cells:")
        for cell in world_map.cells:
            if cell.room_class is None:
                continue
            print(
                f"({cell.x:02d},{cell.y:02d}) class={cell.room_class} "
                f"entrance={cell.room_entrance_side} "
                f"kind={cell.location_kind:#x} "
                f"a={cell.parameter_a:#04x} b={cell.parameter_b:#04x}"
            )

    if args.hall_features:
        print("decoded hall features:")
        for cell in world_map.cells:
            if cell.hall_feature is None:
                continue
            print(
                f"({cell.x:02d},{cell.y:02d}) feature={cell.hall_feature} "
                f"directions={','.join(cell.connection_directions)} "
                f"kind={cell.location_kind:#x} "
                f"a={cell.parameter_a:#04x} b={cell.parameter_b:#04x}"
            )

    if saved_map is not None:
        differences = compare_maps(world_map, saved_map)
        print(f"save differences: {len(differences)} byte fields")
        for difference in differences:
            print(
                f"({difference.x:02d},{difference.y:02d}) "
                f"field={difference.field} "
                f"{difference.original:#04x}->{difference.current:#04x}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
