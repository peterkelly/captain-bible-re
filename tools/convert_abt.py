#!/usr/bin/env python3
"""Decode Captain Bible ABT sound effects and optionally write WAV files."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
import wave


class AbtFormatError(ValueError):
    """Raised when an ABT header or compressed command is invalid."""


@dataclass(frozen=True)
class AbtAudio:
    sample_rate: int
    block_samples: int
    codec_id: int
    auxiliary: int
    samples: bytes
    command_counts: tuple[tuple[str, int], ...]


def _require(data: bytes, position: int, size: int) -> None:
    if position + size > len(data):
        raise AbtFormatError(
            f"compressed command at {position:#x} needs {size} byte(s), "
            f"but only {len(data) - position} remain"
        )


def _signed_byte(value: int) -> int:
    return value if value < 0x80 else value - 0x100


def _delta_table(bits: int, step: int) -> tuple[int, ...]:
    factor = {1: 1, 2: 2, 4: 8}[bits]
    value = (-factor * step) & 0xFF
    result = []
    for _ in range(1 << bits):
        result.append(_signed_byte(value))
        value = (value + step) & 0xFF
        if value == 0:
            value = step
    return tuple(result)


def decode_abt(data: bytes) -> AbtAudio:
    """Decode one complete ABT member into unsigned eight-bit PCM."""

    if len(data) < 9:
        raise AbtFormatError("ABT input is shorter than its nine-byte header")

    sample_count = int.from_bytes(data[0:2], "little")
    sample_rate = int.from_bytes(data[2:4], "little")
    block_samples = data[4]
    codec_id = data[5]
    auxiliary = int.from_bytes(data[6:8], "little")
    if sample_count == 0:
        raise AbtFormatError("ABT sample count is zero")
    if sample_rate == 0:
        raise AbtFormatError("ABT sample rate is zero")
    if block_samples == 0:
        raise AbtFormatError("ABT delta-block sample count is zero")

    position = 9
    sample = data[8]
    output = bytearray((sample,))
    counts: Counter[str] = Counter()

    while len(output) < sample_count:
        _require(data, position, 1)
        control = data[position]
        position += 1

        if control & 0x80:
            sample = (control << 1) & 0xFF
            output.append(sample)
            counts["absolute"] += 1
            continue

        if control & 0x40:
            run_length = control & 0x3F
            if len(output) + run_length > sample_count:
                raise AbtFormatError("run-length command exceeds sample count")
            output.extend(bytes((sample,)) * run_length)
            counts["run"] += 1
            continue

        mode = control >> 4
        bits = 1 if mode == 1 else 2 if mode == 2 else 4
        packed_bits = block_samples * bits
        if packed_bits % 8:
            raise AbtFormatError(
                "delta-block sample count does not fill whole input bytes"
            )
        encoded_size = packed_bits // 8
        if len(output) + block_samples > sample_count:
            raise AbtFormatError("delta block exceeds sample count")
        _require(data, position, encoded_size)

        step = (control & 0x0F) + 1
        table = _delta_table(bits, step)
        mask = (1 << bits) - 1
        for packed in data[position : position + encoded_size]:
            for shift in range(8 - bits, -1, -bits):
                delta = table[(packed >> shift) & mask]
                sample = max(0, min(255, sample + delta))
                output.append(sample)
        position += encoded_size
        counts[f"delta{bits}"] += 1

    if len(output) != sample_count:
        raise AbtFormatError("decoded sample count does not match the header")
    if position != len(data):
        raise AbtFormatError(
            f"ABT stream has {len(data) - position} unused trailing byte(s)"
        )

    return AbtAudio(
        sample_rate=sample_rate,
        block_samples=block_samples,
        codec_id=codec_id,
        auxiliary=auxiliary,
        samples=bytes(output),
        command_counts=tuple(sorted(counts.items())),
    )


def write_wav(path: Path, audio: AbtAudio) -> None:
    """Write decoded unsigned eight-bit mono samples to a RIFF/WAVE file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(1)
        output.setframerate(audio.sample_rate)
        output.writeframes(audio.samples)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decode a Captain Bible ABT sound effect."
    )
    parser.add_argument("input", type=Path, help="expanded ABT resource")
    parser.add_argument("--output", type=Path, help="optional output WAV path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        audio = decode_abt(args.input.read_bytes())
    except (OSError, AbtFormatError) as error:
        print(f"{args.input}: {error}", file=sys.stderr)
        return 1

    duration = len(audio.samples) / audio.sample_rate
    counts = ", ".join(f"{name}={count}" for name, count in audio.command_counts)
    print(
        f"{args.input}: {len(audio.samples)} samples, "
        f"{audio.sample_rate} Hz, {duration:.3f} seconds"
    )
    print(
        f"block={audio.block_samples}, codec={audio.codec_id}, "
        f"auxiliary={audio.auxiliary}, commands: {counts}"
    )
    if args.output is not None:
        try:
            write_wav(args.output, audio)
        except OSError as error:
            print(f"{args.output}: {error}", file=sys.stderr)
            return 1
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
