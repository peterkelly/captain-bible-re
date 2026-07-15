#!/usr/bin/env python3
"""Inspect the Unibot navigation graph embedded in CP2.BIN."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys


CP2_SIZE = 0x1E55
NEXT_NODE_OFFSET = 0x1D55
CELL_TYPE_OFFSET = 0x1DD5
TRANSITION_VALUE_OFFSET = 0x1DF5
MAP_COORDINATE_OFFSET = 0x1E15
NODE_COUNT = 16
HEADING_NAMES = ("north", "east", "south", "west")
BLOCKED_NODE = 100
CELL_TYPES = {
    0: "road",
    1: "pylon",
    2: "tower",
}
PYLON_NUMBERS = {
    3: 1,
    5: 2,
    7: 3,
    8: 4,
    10: 5,
    11: 6,
    13: 7,
}


class UnibotMapError(ValueError):
    """Raised when CP2.BIN does not contain the recovered graph layout."""


@dataclass(frozen=True)
class UnibotNode:
    index: int
    exits: tuple[int | None, ...]
    cell_type: str
    transition_value: int
    map_x: int
    map_y: int
    pylon_number: int | None = None


@dataclass(frozen=True)
class UnibotMap:
    nodes: tuple[UnibotNode, ...]

    def node(self, index: int) -> UnibotNode:
        if not 0 <= index < len(self.nodes):
            raise IndexError(f"Unibot node {index} is outside 0..15")
        return self.nodes[index]


def _unpack_words(data: bytes, offset: int, count: int) -> tuple[int, ...]:
    return struct.unpack_from(f"<{count}h", data, offset)


def parse_unibot_map(data: bytes) -> UnibotMap:
    """Parse and validate the four tables at the end of CP2.BIN."""

    if len(data) != CP2_SIZE:
        raise UnibotMapError(
            f"CP2.BIN is {len(data)} bytes; expected {CP2_SIZE}"
        )
    next_nodes = _unpack_words(data, NEXT_NODE_OFFSET, NODE_COUNT * 4)
    cell_types = _unpack_words(data, CELL_TYPE_OFFSET, NODE_COUNT)
    transition_values = _unpack_words(
        data,
        TRANSITION_VALUE_OFFSET,
        NODE_COUNT,
    )
    coordinates = _unpack_words(data, MAP_COORDINATE_OFFSET, NODE_COUNT * 2)

    nodes = []
    for index in range(NODE_COUNT):
        raw_exits = next_nodes[index * 4 : index * 4 + 4]
        if any(
            value != BLOCKED_NODE and not 0 <= value < NODE_COUNT
            for value in raw_exits
        ):
            raise UnibotMapError(f"node {index} has an invalid exit {raw_exits}")
        cell_type_value = cell_types[index]
        if cell_type_value not in CELL_TYPES:
            raise UnibotMapError(
                f"node {index} has unknown cell type {cell_type_value}"
            )
        nodes.append(
            UnibotNode(
                index=index,
                exits=tuple(
                    None if value == BLOCKED_NODE else value
                    for value in raw_exits
                ),
                cell_type=CELL_TYPES[cell_type_value],
                transition_value=transition_values[index],
                map_x=coordinates[index * 2],
                map_y=coordinates[index * 2 + 1],
                pylon_number=PYLON_NUMBERS.get(index),
            )
        )

    world = UnibotMap(tuple(nodes))
    for node in world.nodes:
        for heading, destination in enumerate(node.exits):
            if destination is None:
                continue
            reverse_heading = (heading + 2) % 4
            if world.node(destination).exits[reverse_heading] != node.index:
                raise UnibotMapError(
                    f"edge {node.index}->{destination} is not reciprocal"
                )
    if {node.index for node in world.nodes if node.cell_type == "pylon"} != set(
        PYLON_NUMBERS
    ):
        raise UnibotMapError("pylon nodes do not match the script dispatcher")
    if [node.index for node in world.nodes if node.cell_type == "tower"] != [14]:
        raise UnibotMapError("expected Tower at node 14")
    return world


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to expanded CP2.BIN")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        world = parse_unibot_map(args.input.read_bytes())
    except (OSError, UnibotMapError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("CP2.BIN Unibot graph: 16 nodes, headings north/east/south/west")
    for node in world.nodes:
        exits = " ".join(
            f"{heading}={'-' if destination is None else destination:>2}"
            for heading, destination in zip(HEADING_NAMES, node.exits)
        )
        pylon = f" pylon={node.pylon_number}" if node.pylon_number else ""
        print(
            f"node={node.index:02d} type={node.cell_type:<5}{pylon:<9} "
            f"map=({node.map_x},{node.map_y}) "
            f"transition={node.transition_value:>4} {exits}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
