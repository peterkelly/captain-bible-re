#!/usr/bin/env python3
"""Validate and inspect the recovered Captain Bible symbol catalog."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import re
import sys


CATALOG_FIELDS = (
    "kind",
    "offset",
    "name",
    "confidence",
    "subsystem",
    "evidence",
)
KINDS = {"function", "handler", "data"}
CONFIDENCE_LEVELS = {"verified", "high", "medium"}


class SymbolMapError(ValueError):
    """Raised when the catalog and Rizin script are inconsistent."""


@dataclass(frozen=True)
class Symbol:
    kind: str
    offset: int
    name: str
    confidence: str
    subsystem: str
    evidence: str


def load_catalog(path: Path) -> tuple[Symbol, ...]:
    """Load and structurally validate the tab-separated catalog."""

    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if tuple(reader.fieldnames or ()) != CATALOG_FIELDS:
                raise SymbolMapError("catalog has an unexpected header")
            rows = []
            for line_number, row in enumerate(reader, 2):
                try:
                    offset = int(row["offset"], 0)
                except ValueError as error:
                    raise SymbolMapError(
                        f"line {line_number} has an invalid offset"
                    ) from error
                symbol = Symbol(
                    kind=row["kind"],
                    offset=offset,
                    name=row["name"],
                    confidence=row["confidence"],
                    subsystem=row["subsystem"],
                    evidence=row["evidence"],
                )
                if symbol.kind not in KINDS:
                    raise SymbolMapError(
                        f"line {line_number} has unknown kind {symbol.kind!r}"
                    )
                if symbol.confidence not in CONFIDENCE_LEVELS:
                    raise SymbolMapError(
                        f"line {line_number} has unknown confidence "
                        f"{symbol.confidence!r}"
                    )
                if not 0 <= symbol.offset <= 0xFFFF:
                    raise SymbolMapError(
                        f"line {line_number} offset is outside the load module"
                    )
                if not symbol.name or not symbol.subsystem or not symbol.evidence:
                    raise SymbolMapError(
                        f"line {line_number} has an empty required field"
                    )
                rows.append(symbol)
    except OSError as error:
        raise SymbolMapError(str(error)) from error

    names = [symbol.name for symbol in rows]
    if len(names) != len(set(names)):
        raise SymbolMapError("catalog contains a duplicate symbol name")
    locations = [(symbol.kind, symbol.offset) for symbol in rows]
    if len(locations) != len(set(locations)):
        raise SymbolMapError("catalog contains a duplicate kind/offset pair")
    return tuple(rows)


def parse_rizin_script(path: Path) -> dict[str, set]:
    """Return function, handler, and data names declared by ``cb.rz``."""

    declarations: dict[str, set] = {
        "function": set(),
        "handler": set(),
        "data": set(),
    }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SymbolMapError(str(error)) from error
    for line in lines:
        if match := re.fullmatch(r"afn\s+(\S+)\s+@\s+(0x[0-9a-fA-F]+)", line):
            declarations["function"].add((int(match.group(2), 0), match.group(1)))
        elif match := re.fullmatch(r"fr\s+\S+\s+(\S+)", line):
            declarations["handler"].add(match.group(1))
        elif match := re.fullmatch(
            r"f\s+(\S+)\s+\S+\s+@\s+(0x[0-9a-fA-F]+)", line
        ):
            declarations["data"].add((int(match.group(2), 0), match.group(1)))
    return declarations


def parse_rizin_flags(path: Path) -> set[tuple[int, str]]:
    """Parse handler addresses from saved Rizin ``fl`` output."""

    flags = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SymbolMapError(str(error)) from error
    for line in lines:
        match = re.fullmatch(
            r"(0x[0-9a-fA-F]+)\s+\d+\s+(bin_handler_\S+)",
            line.strip(),
        )
        if match:
            flags.add((int(match.group(1), 0), match.group(2)))
    return flags


def validate_catalog(
    symbols: tuple[Symbol, ...],
    declarations: dict[str, set],
    handler_flags: set[tuple[int, str]] | None = None,
) -> None:
    """Require the catalog to cover every named Rizin symbol exactly."""

    functions = {
        (symbol.offset, symbol.name)
        for symbol in symbols
        if symbol.kind == "function"
    }
    handlers = {symbol.name for symbol in symbols if symbol.kind == "handler"}
    data = {
        (symbol.offset, symbol.name)
        for symbol in symbols
        if symbol.kind == "data"
    }
    for kind, catalog_values, script_values in (
        ("function", functions, declarations["function"]),
        ("handler", handlers, declarations["handler"]),
        ("data", data, declarations["data"]),
    ):
        if catalog_values != script_values:
            missing = sorted(script_values - catalog_values)
            extra = sorted(catalog_values - script_values)
            raise SymbolMapError(
                f"{kind} catalog mismatch: missing={missing}, extra={extra}"
            )
    if handler_flags is not None:
        catalog_flags = {
            (symbol.offset, symbol.name)
            for symbol in symbols
            if symbol.kind == "handler"
        }
        if catalog_flags != handler_flags:
            raise SymbolMapError("handler addresses differ from Rizin flag output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "catalog",
        nargs="?",
        type=Path,
        default=Path("analysis/symbol-map.tsv"),
    )
    parser.add_argument("--rizin-script", type=Path, default=Path("analysis/cb.rz"))
    parser.add_argument("--rizin-flags", type=Path)
    parser.add_argument("--kind", choices=sorted(KINDS))
    parser.add_argument("--confidence", choices=sorted(CONFIDENCE_LEVELS))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        symbols = load_catalog(args.catalog)
        declarations = parse_rizin_script(args.rizin_script)
        flags = parse_rizin_flags(args.rizin_flags) if args.rizin_flags else None
        validate_catalog(symbols, declarations, flags)
    except SymbolMapError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    counts = {
        kind: sum(symbol.kind == kind for symbol in symbols)
        for kind in sorted(KINDS)
    }
    confidence = {
        level: sum(symbol.confidence == level for symbol in symbols)
        for level in ("verified", "high", "medium")
    }
    print(
        f"symbols={len(symbols)} "
        + " ".join(f"{key}={value}" for key, value in counts.items())
        + " "
        + " ".join(f"{key}={value}" for key, value in confidence.items())
    )
    selected = symbols
    if args.kind:
        selected = tuple(symbol for symbol in selected if symbol.kind == args.kind)
    if args.confidence:
        selected = tuple(
            symbol for symbol in selected if symbol.confidence == args.confidence
        )
    for symbol in sorted(selected, key=lambda item: (item.offset, item.kind)):
        print(
            f"0x{symbol.offset:04x} {symbol.kind:<8} "
            f"{symbol.confidence:<8} {symbol.name} [{symbol.subsystem}] "
            f"{symbol.evidence}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
