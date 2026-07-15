#!/usr/bin/env python3
"""Inspect and unpack Captain Bible's Microsoft EXEPACK executable.

The script intentionally uses only the Python standard library.  It produces a
normal MZ executable suitable for Rizin and can compare that executable, after
DOS relocation, with a QEMU physical-memory dump.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


MZ_MAGIC = 0x5A4D
EXEPACK_SIGNATURE = 0x4252
MZ_FIXED_HEADER_SIZE = 28
STUB_END_MARKER = b"\xcd\x21\xb8\xff\x4c\xcd\x21"


def paragraphs(length: int) -> int:
    return (length + 15) // 16


def pages(length: int) -> int:
    return (length + 511) // 512


def decode_mz_size(last_page_bytes: int, page_count: int) -> int:
    if last_page_bytes == 0:
        return page_count * 512
    if page_count == 0 or last_page_bytes > 511:
        raise ValueError("invalid MZ file-size fields")
    return (page_count - 1) * 512 + last_page_bytes


def encode_mz_size(length: int) -> tuple[int, int]:
    return length % 512, pages(length)


@dataclass(frozen=True)
class Relocation:
    offset: int
    segment: int

    @property
    def linear(self) -> int:
        return self.segment * 16 + self.offset


@dataclass(frozen=True)
class MZExecutable:
    min_alloc: int
    max_alloc: int
    ss: int
    sp: int
    checksum: int
    ip: int
    cs: int
    overlay: int
    body: bytes
    relocations: tuple[Relocation, ...]
    header_size: int
    declared_size: int


@dataclass(frozen=True)
class ExepackHeader:
    real_ip: int
    real_cs: int
    scratch: int
    exepack_size: int
    real_sp: int
    real_ss: int
    destination_paragraphs: int
    skip_paragraphs: int
    header_size: int


@dataclass(frozen=True)
class UnpackResult:
    executable: MZExecutable
    header: ExepackHeader
    stub_size: int
    compressed_size: int


def parse_mz(data: bytes) -> MZExecutable:
    if len(data) < MZ_FIXED_HEADER_SIZE:
        raise ValueError("file is shorter than the fixed MZ header")

    fields = struct.unpack_from("<14H", data)
    (
        magic,
        last_page_bytes,
        page_count,
        relocation_count,
        header_paragraphs,
        min_alloc,
        max_alloc,
        ss,
        sp,
        checksum,
        ip,
        cs,
        relocation_offset,
        overlay,
    ) = fields
    if magic != MZ_MAGIC:
        raise ValueError(f"bad MZ signature 0x{magic:04x}")

    declared_size = decode_mz_size(last_page_bytes, page_count)
    header_size = header_paragraphs * 16
    if declared_size > len(data):
        raise ValueError("MZ header declares more bytes than the file contains")
    if header_size < MZ_FIXED_HEADER_SIZE or header_size > declared_size:
        raise ValueError("invalid MZ header length")

    relocation_end = relocation_offset + relocation_count * 4
    if relocation_offset < MZ_FIXED_HEADER_SIZE or relocation_end > header_size:
        raise ValueError("MZ relocation table lies outside the header")
    relocations = tuple(
        Relocation(*struct.unpack_from("<HH", data, relocation_offset + i * 4))
        for i in range(relocation_count)
    )

    return MZExecutable(
        min_alloc=min_alloc,
        max_alloc=max_alloc,
        ss=ss,
        sp=sp,
        checksum=checksum,
        ip=ip,
        cs=cs,
        overlay=overlay,
        body=data[header_size:declared_size],
        relocations=relocations,
        header_size=header_size,
        declared_size=declared_size,
    )


def parse_exepack_header(raw: bytes) -> ExepackHeader:
    if len(raw) not in (16, 18):
        raise ValueError(f"unsupported EXEPACK header length {len(raw)}")
    words = struct.unpack(f"<{len(raw) // 2}H", raw)
    if len(raw) == 16:
        real_ip, real_cs, scratch, size, sp, ss, destination, signature = words
        skip = 1
    else:
        real_ip, real_cs, scratch, size, sp, ss, destination, skip, signature = words
    if signature != EXEPACK_SIGNATURE:
        raise ValueError(f"bad EXEPACK signature 0x{signature:04x}")
    if skip == 0:
        raise ValueError("EXEPACK skip-paragraph count may not be zero")
    return ExepackHeader(
        real_ip=real_ip,
        real_cs=real_cs,
        scratch=scratch,
        exepack_size=size,
        real_sp=sp,
        real_ss=ss,
        destination_paragraphs=destination,
        skip_paragraphs=skip,
        header_size=len(raw),
    )


def locate_stub_end(stub_and_relocations: bytes) -> int:
    """Return the known-stub length, including its 22-byte error message."""
    marker = stub_and_relocations.find(STUB_END_MARKER)
    if marker < 0:
        raise ValueError("could not locate the end of the EXEPACK stub")
    end = marker + len(STUB_END_MARKER) + 22
    if end > len(stub_and_relocations):
        raise ValueError("truncated EXEPACK error message")
    return end


def parse_packed_relocations(raw: bytes) -> tuple[Relocation, ...]:
    relocations: list[Relocation] = []
    cursor = 0
    for group in range(16):
        if cursor + 2 > len(raw):
            raise ValueError("truncated EXEPACK relocation group")
        count = struct.unpack_from("<H", raw, cursor)[0]
        cursor += 2
        if cursor + count * 2 > len(raw):
            raise ValueError("truncated EXEPACK relocation entries")
        for _ in range(count):
            offset = struct.unpack_from("<H", raw, cursor)[0]
            cursor += 2
            relocations.append(Relocation(offset=offset, segment=group * 0x1000))
    if cursor != len(raw):
        raise ValueError("unexpected bytes after EXEPACK relocation table")
    return tuple(relocations)


def decompress_exepack(
    compressed: bytes, compressed_size: int, uncompressed_size: int
) -> bytes:
    work = bytearray(compressed)
    if len(work) < uncompressed_size:
        work.extend(bytes(uncompressed_size - len(work)))

    source = compressed_size
    destination = uncompressed_size
    skipped = 0
    while source > 0 and skipped < 15 and work[source - 1] == 0xFF:
        source -= 1
        skipped += 1

    while True:
        if source < 3:
            raise ValueError("EXEPACK command stream underflow")
        source -= 1
        command = work[source]
        source -= 2
        length = struct.unpack_from("<H", work, source)[0]

        if command & 0xFE == 0xB0:
            if source < 1 or destination < length:
                raise ValueError("invalid EXEPACK fill command")
            source -= 1
            destination -= length
            work[destination : destination + length] = bytes([work[source]]) * length
        elif command & 0xFE == 0xB2:
            if source < length or destination < length:
                raise ValueError("invalid EXEPACK copy command")
            source -= length
            destination -= length
            # Copy backwards because source and destination may overlap.
            for index in range(length - 1, -1, -1):
                work[destination + index] = work[source + index]
        else:
            raise ValueError(f"unknown EXEPACK command 0x{command:02x}")

        if command & 1:
            break

    if compressed_size < destination:
        raise ValueError("EXEPACK decompression left an unwritten gap")
    return bytes(work[:uncompressed_size])


def unpack_exepack(packed: MZExecutable) -> UnpackResult:
    if packed.relocations:
        raise ValueError("outer EXEPACK executable unexpectedly has relocations")

    header_offset = packed.cs * 16
    header_end = header_offset + packed.ip
    if header_end > len(packed.body):
        raise ValueError("EXEPACK header lies outside the MZ load module")
    header = parse_exepack_header(packed.body[header_offset:header_end])

    block_end = header_offset + header.exepack_size
    if block_end > len(packed.body):
        raise ValueError("EXEPACK block lies outside the MZ load module")
    stub_and_relocations = packed.body[header_end:block_end]
    stub_size = locate_stub_end(stub_and_relocations)
    relocations = parse_packed_relocations(stub_and_relocations[stub_size:])

    skipped_bytes = (header.skip_paragraphs - 1) * 16
    compressed_size = header_offset - skipped_bytes
    uncompressed_size = header.destination_paragraphs * 16 - skipped_bytes
    body = decompress_exepack(
        packed.body[:header_offset], compressed_size, uncompressed_size
    )

    min_alloc = paragraphs(len(packed.body)) + packed.min_alloc - paragraphs(len(body))
    if min_alloc < 0:
        min_alloc = 0
    executable = MZExecutable(
        min_alloc=min_alloc,
        max_alloc=packed.max_alloc,
        ss=header.real_ss,
        sp=header.real_sp,
        checksum=0,
        ip=header.real_ip,
        cs=header.real_cs,
        overlay=packed.overlay,
        body=body,
        relocations=relocations,
        header_size=0,
        declared_size=0,
    )
    return UnpackResult(
        executable=executable,
        header=header,
        stub_size=stub_size,
        compressed_size=compressed_size,
    )


def mz_checksum(data: bytes) -> int:
    padded = data if len(data) % 2 == 0 else data + b"\x00"
    total = sum(struct.unpack(f"<{len(padded) // 2}H", padded)) & 0xFFFF
    return (~total) & 0xFFFF


def serialize_mz(executable: MZExecutable) -> bytes:
    header_size = pages(MZ_FIXED_HEADER_SIZE + 4 * len(executable.relocations)) * 512
    total_size = header_size + len(executable.body)
    last_page_bytes, page_count = encode_mz_size(total_size)
    fixed = struct.pack(
        "<14H",
        MZ_MAGIC,
        last_page_bytes,
        page_count,
        len(executable.relocations),
        header_size // 16,
        executable.min_alloc,
        executable.max_alloc,
        executable.ss,
        executable.sp,
        0,
        executable.ip,
        executable.cs,
        MZ_FIXED_HEADER_SIZE,
        executable.overlay,
    )
    relocations = b"".join(
        struct.pack("<HH", item.offset, item.segment)
        for item in executable.relocations
    )
    result = bytearray(
        fixed
        + relocations
        + bytes(header_size - len(fixed) - len(relocations))
        + executable.body
    )
    struct.pack_into("<H", result, 18, mz_checksum(result))
    return bytes(result)


def relocated_body(executable: MZExecutable, load_segment: int) -> bytes:
    body = bytearray(executable.body)
    for relocation in executable.relocations:
        address = relocation.linear
        if address + 2 > len(body):
            raise ValueError(f"relocation 0x{address:x} lies outside the load module")
        value = struct.unpack_from("<H", body, address)[0]
        struct.pack_into("<H", body, address, (value + load_segment) & 0xFFFF)
    return bytes(body)


def compare_memory(
    executable: MZExecutable, memory: bytes, load_segment: int
) -> tuple[int, int, int]:
    expected = relocated_body(executable, load_segment)
    physical = load_segment * 16
    actual = memory[physical : physical + len(expected)]
    if len(actual) != len(expected):
        raise ValueError("memory dump does not contain the complete load module")
    differences = [
        index
        for index, pair in enumerate(zip(expected, actual))
        if pair[0] != pair[1]
    ]
    first_difference = differences[0] if differences else len(expected)
    return len(expected), first_difference, len(differences)


def hexadecimal(value: int) -> str:
    return f"0x{value:x}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="packed DOS executable")
    parser.add_argument("--output", type=Path, help="write the unpacked MZ executable")
    parser.add_argument("--memory-dump", type=Path, help="QEMU physical-memory dump")
    parser.add_argument(
        "--load-segment",
        type=lambda value: int(value, 0),
        help="DOS load segment used for --memory-dump (for example, 0x627)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if (args.memory_dump is None) != (args.load_segment is None):
        raise SystemExit("--memory-dump and --load-segment must be used together")

    packed_bytes = args.input.read_bytes()
    packed = parse_mz(packed_bytes)
    result = unpack_exepack(packed)
    unpacked_bytes = serialize_mz(result.executable)

    print(f"input_sha256={hashlib.sha256(packed_bytes).hexdigest()}")
    print(f"packed_file_size={len(packed_bytes)}")
    print(f"packed_header_size={packed.header_size}")
    print(f"packed_entry={packed.cs:04x}:{packed.ip:04x}")
    print(f"exepack_header_offset={hexadecimal(packed.header_size + packed.cs * 16)}")
    print(f"exepack_header_size={result.header.header_size}")
    print(f"exepack_block_size={result.header.exepack_size}")
    print(f"exepack_stub_size={result.stub_size}")
    print(f"compressed_load_size={result.compressed_size}")
    print(f"unpacked_load_size={len(result.executable.body)}")
    print(f"real_entry={result.executable.cs:04x}:{result.executable.ip:04x}")
    print(f"real_stack={result.executable.ss:04x}:{result.executable.sp:04x}")
    print(f"relocation_count={len(result.executable.relocations)}")
    print(f"unpacked_min_alloc={hexadecimal(result.executable.min_alloc)}")
    print(f"unpacked_file_size={len(unpacked_bytes)}")
    print(f"unpacked_sha256={hashlib.sha256(unpacked_bytes).hexdigest()}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(unpacked_bytes)
        print(f"output={args.output}")

    if args.memory_dump is not None:
        memory = args.memory_dump.read_bytes()
        compared, identical_prefix, different = compare_memory(
            result.executable, memory, args.load_segment
        )
        print(f"memory_load_segment={hexadecimal(args.load_segment)}")
        print(f"memory_bytes_compared={compared}")
        print(f"memory_identical_prefix={hexadecimal(identical_prefix)}")
        print(f"memory_different_bytes={different}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
