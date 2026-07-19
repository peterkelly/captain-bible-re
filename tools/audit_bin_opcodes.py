#!/usr/bin/env python3
"""Independently audit Captain Bible's complete BIN opcode table."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys

from extract_dd1 import DD1Archive
from inspect_bin import (
    OPCODE_NAMES,
    OPCODE_SCHEMAS,
    SCRIPT_VARIABLE_OPERANDS,
    code_regions,
    decode_stream,
)


ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = 0x451B
TARGET_JUMP = 0x4526
CONTINUE_LOOP = 0x4535
EPILOGUE = 0x5AD0
DISPATCH_TABLE = 0x59AB
DISPATCH_COUNT = 0x91
ALLOWED_EXTRA_PATHS = {
    # An already-active modal dialogue suspends and retries the same command
    # without consuming its text pointer.  Once the modal state clears, the
    # handler consumes the pointer before continuing.
    0x52A3: {""},
}
SHARED_HANDLER_SYMBOLS = {
    0x14: "bin_handler_show_dialogue",
    0x17: "bin_handler_add_edge_transition_handler",
    0x18: "bin_handler_add_edge_transition_handler",
    0x19: "bin_handler_add_edge_transition_handler",
    0x1A: "bin_handler_add_edge_transition_handler",
    0x48: "bin_handler_show_dialogue",
    0x4E: "bin_handler_show_dialogue",
}
READER_EVENTS = {
    0x3A1E: "B",
    0x3A30: "H",
    0x3A64: "p",
}
RAW_NINE_PATTERN = re.compile(r"^add word \[0xf6\], 0x0?9$")
CASE_RENAME_PATTERN = re.compile(
    r"^fr case\.0x4552\.(\d+) (bin_handler_[a-z0-9_]+)$"
)


class OpcodeAuditError(RuntimeError):
    """Raised when independent opcode evidence disagrees with the catalog."""


@dataclass(frozen=True)
class SymbolEntry:
    address: int
    name: str
    confidence: str
    evidence: str


@dataclass(frozen=True)
class AuditRow:
    opcode: int
    handler: int
    handler_symbol: str
    confidence: str
    schema: str
    static_paths: tuple[str, ...]
    name: str
    variable_operands: tuple[int, ...]
    uses: int
    resources: tuple[str, ...]
    first_site: str


def _parse_json_output(output: str) -> object:
    starts = [
        position
        for marker in ("{", "[")
        if (position := output.find(marker)) >= 0
    ]
    if not starts:
        raise OpcodeAuditError("Rizin did not return JSON")
    return json.loads(output[min(starts) :])


def _run_rizin_json(
    executable: Path, rizin_script: Path, command: str
) -> object:
    completed = subprocess.run(
        [
            "rizin",
            "-q",
            "-b",
            "16",
            "-e",
            "scr.color=false",
            "-i",
            str(rizin_script),
            "-c",
            command,
            "-c",
            "q",
            str(executable),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode:
        raise OpcodeAuditError(
            f"Rizin failed with status {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return _parse_json_output(completed.stdout)


def load_static_analysis(
    executable: Path, rizin_script: Path
) -> tuple[tuple[int, ...], dict[int, dict[str, object]]]:
    dispatch_data = _run_rizin_json(
        executable,
        rizin_script,
        f"pxhj {DISPATCH_COUNT * 2} @ {DISPATCH_TABLE:#x}",
    )
    if not isinstance(dispatch_data, list) or len(dispatch_data) != DISPATCH_COUNT:
        raise OpcodeAuditError(
            f"dispatch table has {len(dispatch_data)} entries; "
            f"expected {DISPATCH_COUNT}"
        )
    dispatch = tuple(int(address) for address in dispatch_data)

    function_data = _run_rizin_json(
        executable, rizin_script, f"pdfj @ {INTERPRETER:#x}"
    )
    if not isinstance(function_data, dict) or not isinstance(
        function_data.get("ops"), list
    ):
        raise OpcodeAuditError("Rizin did not return interpreter instructions")
    operations = {
        int(operation["offset"]): operation
        for operation in function_data["ops"]
        if isinstance(operation, dict) and "offset" in operation
    }
    return dispatch, operations


def expected_paths(schema: str) -> tuple[str, ...]:
    """Expand a declared schema into every possible operand-reader path."""

    paths = {""}
    for field in schema:
        if field in "BHzp9":
            paths = {path + field for path in paths}
        elif field == "s":
            paths |= {path + "H" for path in paths}
        else:
            raise OpcodeAuditError(f"unknown schema field {field!r}")
    return tuple(sorted(paths))


def _successors(
    address: int, operation: dict[str, object]
) -> tuple[int, ...]:
    operation_type = operation.get("type")
    if operation_type == "jmp":
        return (int(operation["jump"]),)
    if operation_type == "cjmp":
        return (int(operation["jump"]), int(operation["fail"]))
    if operation_type in ("ret", "trap", "ill", "irjmp"):
        return ()
    next_address = operation.get("fail")
    if next_address is None:
        next_address = address + int(operation["size"])
    return (int(next_address),)


def cyclic_u8_reader_sites(
    operations: dict[int, dict[str, object]]
) -> frozenset[int]:
    """Return u8 reader call sites inside loops that consume C strings."""

    graph = {
        address: tuple(
            successor
            for successor in _successors(address, operation)
            if successor in operations
            and successor not in (TARGET_JUMP, CONTINUE_LOOP, EPILOGUE)
        )
        for address, operation in operations.items()
    }
    index = 0
    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    cyclic: set[int] = set()

    def visit(address: int) -> None:
        nonlocal index
        indices[address] = index
        lowlinks[address] = index
        index += 1
        stack.append(address)
        on_stack.add(address)
        for successor in graph[address]:
            if successor not in indices:
                visit(successor)
                lowlinks[address] = min(lowlinks[address], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[address] = min(lowlinks[address], indices[successor])
        if lowlinks[address] != indices[address]:
            return
        component: set[int] = set()
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == address:
                break
        is_cycle = len(component) > 1 or any(
            member in graph[member] for member in component
        )
        if not is_cycle:
            return
        for member in component:
            operation = operations[member]
            if (
                operation.get("type") == "call"
                and int(operation.get("jump", -1)) == 0x3A1E
            ):
                cyclic.add(member)

    for address in graph:
        if address not in indices:
            visit(address)
    return frozenset(cyclic)


def observed_paths(
    handler: int,
    operations: dict[int, dict[str, object]],
    cyclic_u8_sites: frozenset[int],
) -> tuple[str, ...]:
    """Walk all interpreter CFG paths and return their operand-reader calls."""

    pending = [(handler, "", frozenset())]
    visited: set[tuple[int, str, frozenset[int]]] = set()
    completed: set[str] = set()
    escaped: set[int] = set()

    while pending:
        address, events, consumed_loops = pending.pop()
        state = (address, events, consumed_loops)
        if state in visited:
            continue
        visited.add(state)

        if address in (TARGET_JUMP, CONTINUE_LOOP, EPILOGUE):
            completed.add(events)
            continue
        operation = operations.get(address)
        if operation is None:
            escaped.add(address)
            continue

        opcode = str(operation.get("opcode", ""))
        event = READER_EVENTS.get(int(operation.get("jump", -1)))
        if address in cyclic_u8_sites:
            event = "z"
        if operation.get("type") == "call" and event is not None:
            if address not in consumed_loops:
                events += event
                if address in cyclic_u8_sites:
                    consumed_loops |= {address}
        elif RAW_NINE_PATTERN.match(opcode):
            events += "9"
        if len(events) > 16:
            raise OpcodeAuditError(
                f"handler {handler:#06x} accumulated implausible reader path {events}"
            )

        operation_type = operation.get("type")
        if operation_type in ("ret", "trap", "ill"):
            completed.add(events)
        elif operation_type == "jmp":
            pending.append((int(operation["jump"]), events, consumed_loops))
        elif operation_type == "cjmp":
            pending.append((int(operation["jump"]), events, consumed_loops))
            pending.append((int(operation["fail"]), events, consumed_loops))
        elif operation_type == "irjmp":
            escaped.add(address)
        else:
            next_address = operation.get("fail")
            if next_address is None:
                next_address = address + int(operation["size"])
            pending.append((int(next_address), events, consumed_loops))

    if escaped:
        locations = ", ".join(f"{address:#06x}" for address in sorted(escaped))
        raise OpcodeAuditError(
            f"handler {handler:#06x} escaped the interpreter CFG at {locations}"
        )
    if not completed:
        raise OpcodeAuditError(f"handler {handler:#06x} has no terminating CFG path")
    return tuple(sorted(completed))


def load_symbols(path: Path) -> dict[int, SymbolEntry]:
    symbols: dict[int, SymbolEntry] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line or line.startswith("kind\t"):
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            raise OpcodeAuditError(f"{path}:{line_number}: malformed symbol row")
        kind, address, name, confidence, subsystem, evidence = fields
        if kind != "handler":
            continue
        if subsystem != "bytecode":
            raise OpcodeAuditError(
                f"{path}:{line_number}: handler is outside bytecode subsystem"
            )
        entry = SymbolEntry(int(address, 0), name, confidence, evidence)
        if entry.address in symbols:
            raise OpcodeAuditError(
                f"{path}:{line_number}: duplicate handler {entry.address:#x}"
            )
        symbols[entry.address] = entry
    return symbols


def load_case_renames(path: Path) -> dict[int, str]:
    renames: dict[int, str] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        match = CASE_RENAME_PATTERN.match(line)
        if match is None:
            continue
        opcode = int(match.group(1))
        if opcode < 1 or opcode > DISPATCH_COUNT:
            raise OpcodeAuditError(f"{path}:{line_number}: invalid opcode {opcode}")
        if opcode in renames:
            raise OpcodeAuditError(f"{path}:{line_number}: duplicate opcode rename")
        renames[opcode] = match.group(2)
    return renames


def load_corpus(
    archive_path: Path,
) -> tuple[Counter[int], dict[int, set[str]], dict[int, str], int, int]:
    archive = DD1Archive.from_path(archive_path)
    counts: Counter[int] = Counter()
    resources: dict[int, set[str]] = defaultdict(set)
    first_sites: dict[int, str] = {}
    command_count = 0
    region_count = 0
    for entry in archive.entries:
        if entry.extension != "BIN":
            continue
        data = archive.extract(entry)
        for start, limit in code_regions(entry.filename, len(data)):
            commands = decode_stream(data, start, limit)
            region_count += 1
            command_count += len(commands)
            for command in commands:
                counts[command.opcode] += 1
                resources[command.opcode].add(entry.filename)
                first_sites.setdefault(
                    command.opcode, f"{entry.filename}@{command.offset:#06x}"
                )
    return counts, resources, first_sites, command_count, region_count


def audit(
    executable: Path,
    archive_path: Path,
    rizin_script: Path,
    symbol_map: Path,
) -> tuple[AuditRow, ...]:
    dispatch, operations = load_static_analysis(executable, rizin_script)
    symbols = load_symbols(symbol_map)
    renames = load_case_renames(rizin_script)
    counts, resources, first_sites, command_count, region_count = load_corpus(
        archive_path
    )

    if set(OPCODE_SCHEMAS) != set(range(1, DISPATCH_COUNT + 1)):
        raise OpcodeAuditError("declared schemas do not cover all dispatch values")
    if set(OPCODE_NAMES) != set(OPCODE_SCHEMAS):
        raise OpcodeAuditError("opcode names and schemas cover different values")
    if set(dispatch) != set(symbols):
        missing = set(dispatch) - set(symbols)
        extra = set(symbols) - set(dispatch)
        raise OpcodeAuditError(
            "handler symbol addresses disagree with dispatch table: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )
    if command_count != 25_829 or region_count != 64 or len(counts) != 122:
        raise OpcodeAuditError(
            f"unexpected corpus: {command_count} commands, {region_count} regions, "
            f"{len(counts)} used opcodes"
        )

    renamed_addresses: dict[int, str] = {}
    for opcode, name in renames.items():
        address = dispatch[opcode - 1]
        previous = renamed_addresses.setdefault(address, name)
        if previous != name:
            raise OpcodeAuditError(
                f"handler {address:#06x} has conflicting Rizin names"
            )
    if renamed_addresses != {address: entry.name for address, entry in symbols.items()}:
        raise OpcodeAuditError("Rizin handler names disagree with the symbol map")

    rows: list[AuditRow] = []
    path_cache: dict[int, tuple[str, ...]] = {}
    cyclic_u8_sites = cyclic_u8_reader_sites(operations)
    for opcode, handler in enumerate(dispatch, 1):
        declared = expected_paths(OPCODE_SCHEMAS[opcode])
        if handler not in path_cache:
            path_cache[handler] = observed_paths(
                handler, operations, cyclic_u8_sites
            )
        observed = path_cache[handler]
        missing_paths = set(declared) - set(observed)
        extra_paths = set(observed) - set(declared)
        if missing_paths or extra_paths != ALLOWED_EXTRA_PATHS.get(handler, set()):
            raise OpcodeAuditError(
                f"opcode {opcode:#04x} at {handler:#06x}: declared schema "
                f"{OPCODE_SCHEMAS[opcode]!r} gives {declared}, static CFG gives "
                f"{observed}"
            )
        variable_operands = SCRIPT_VARIABLE_OPERANDS.get(opcode, ())
        minimum_operand_count = min(len(path) for path in declared)
        if any(position >= minimum_operand_count for position in variable_operands):
            raise OpcodeAuditError(
                f"opcode {opcode:#04x} has invalid variable operand positions"
            )
        symbol = symbols[handler]
        expected_symbol = SHARED_HANDLER_SYMBOLS.get(
            opcode, f"bin_handler_{OPCODE_NAMES[opcode]}"
        )
        if symbol.name != expected_symbol:
            raise OpcodeAuditError(
                f"opcode {opcode:#04x} name {OPCODE_NAMES[opcode]!r} disagrees "
                f"with handler symbol {symbol.name!r}"
            )
        rows.append(
            AuditRow(
                opcode=opcode,
                handler=handler,
                handler_symbol=symbol.name,
                confidence=symbol.confidence,
                schema=OPCODE_SCHEMAS[opcode] or "-",
                static_paths=observed or ("-",),
                name=OPCODE_NAMES[opcode],
                variable_operands=variable_operands,
                uses=counts[opcode],
                resources=tuple(sorted(resources[opcode])),
                first_site=first_sites.get(opcode, "-"),
            )
        )
    return tuple(rows)


def format_report(rows: tuple[AuditRow, ...]) -> str:
    lines = [
        "opcode\thandler\thandler_symbol\tconfidence\tschema\tstatic_paths\t"
        "name\tvariable_operands\tuses\tresources\tfirst_site"
    ]
    for row in rows:
        lines.append(
            "\t".join(
                (
                    f"0x{row.opcode:02x}",
                    f"0x{row.handler:04x}",
                    row.handler_symbol,
                    row.confidence,
                    row.schema,
                    "/".join(path or "-" for path in row.static_paths),
                    row.name,
                    ",".join(str(position) for position in row.variable_operands)
                    or "-",
                    str(row.uses),
                    ",".join(row.resources) or "-",
                    row.first_site,
                )
            )
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare every BIN opcode schema with its static executable CFG and "
            "shipped-resource usage."
        )
    )
    parser.add_argument(
        "--executable",
        type=Path,
        default=ROOT / "build/analysis/CB_UNPACKED.EXE",
    )
    parser.add_argument("--archive", type=Path, default=ROOT / "CB/DD1.DAT")
    parser.add_argument(
        "--rizin-script", type=Path, default=ROOT / "analysis/cb.rz"
    )
    parser.add_argument(
        "--symbol-map", type=Path, default=ROOT / "analysis/symbol-map.tsv"
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        help="write the complete TSV audit report to this path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = audit(
            args.executable,
            args.archive,
            args.rizin_script,
            args.symbol_map,
        )
    except (OSError, OpcodeAuditError, ValueError) as error:
        print(f"opcode audit failed: {error}", file=sys.stderr)
        return 1

    report = format_report(rows)
    if args.write_report is not None:
        args.write_report.write_text(report)
    used = sum(row.uses > 0 for row in rows)
    handlers = len({row.handler for row in rows})
    commands = sum(row.uses for row in rows)
    print(
        f"opcode audit OK: {len(rows)} opcodes, {handlers} handlers, "
        f"{used} used opcodes, {commands} commands"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
