#!/usr/bin/env python3
"""Inspect and render Captain Bible ART resources with VGA PAL files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys

from PIL import Image


ART_RECORD = struct.Struct("<hhHHI")
PALETTE_SIZE = 256 * 3


class ArtFormatError(ValueError):
    """Raised when an ART or PAL resource violates its on-disk invariants."""


@dataclass(frozen=True)
class ArtFrame:
    index: int
    x: int
    y: int
    width: int
    height: int
    data_offset: int
    pixels: bytes


@dataclass(frozen=True)
class ArtResource:
    frames: tuple[ArtFrame, ...]

    @classmethod
    def from_bytes(cls, data: bytes) -> "ArtResource":
        if len(data) < ART_RECORD.size:
            raise ArtFormatError("ART resource is shorter than one descriptor")

        first_data_offset = struct.unpack_from("<I", data, 8)[0]
        if first_data_offset < ART_RECORD.size:
            raise ArtFormatError("first pixel offset precedes the descriptor table")
        if first_data_offset % ART_RECORD.size:
            raise ArtFormatError("first pixel offset is not descriptor-aligned")
        if first_data_offset > len(data):
            raise ArtFormatError("descriptor table extends past end of resource")

        frame_count = first_data_offset // ART_RECORD.size
        frames: list[ArtFrame] = []
        expected_offset = first_data_offset
        for index in range(frame_count):
            position = index * ART_RECORD.size
            x, y, width, height, data_offset = ART_RECORD.unpack_from(
                data, position
            )
            if width == 0 or height == 0:
                raise ArtFormatError(f"frame {index} has a zero dimension")
            if data_offset != expected_offset:
                raise ArtFormatError(
                    f"frame {index} starts at {data_offset:#x}, "
                    f"expected {expected_offset:#x}"
                )
            pixel_count = width * height
            end = data_offset + pixel_count
            if end > len(data):
                raise ArtFormatError(f"frame {index} extends past end of resource")
            frames.append(
                ArtFrame(
                    index=index,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    data_offset=data_offset,
                    pixels=data[data_offset:end],
                )
            )
            expected_offset = end

        if expected_offset != len(data):
            raise ArtFormatError(
                f"ART resource has {len(data) - expected_offset} trailing bytes"
            )
        return cls(tuple(frames))

    @classmethod
    def from_path(cls, path: Path) -> "ArtResource":
        return cls.from_bytes(path.read_bytes())


def parse_vga_palette(data: bytes) -> bytes:
    """Validate and return 256 packed VGA six-bit RGB triplets."""

    if len(data) != PALETTE_SIZE:
        raise ArtFormatError(
            f"PAL resource is {len(data)} bytes, expected {PALETTE_SIZE}"
        )
    invalid = next((value for value in data if value > 0x3F), None)
    if invalid is not None:
        raise ArtFormatError(f"PAL component exceeds six bits: {invalid:#x}")
    return data


def load_vga_palette(path: Path) -> bytes:
    return parse_vga_palette(path.read_bytes())


def expand_vga_palette(palette: bytes) -> list[int]:
    """Expand six-bit DAC components to an eight-bit Pillow palette."""

    return [(value << 2) | (value >> 4) for value in palette]


def compose_canvas(
    art: ArtResource,
    width: int = 320,
    height: int = 200,
    transparent_zero: bool = True,
) -> bytes:
    """Composite every frame in directory order using its signed origin."""

    if width <= 0 or height <= 0:
        raise ArtFormatError("canvas dimensions must be positive")

    canvas = bytearray(width * height)
    for frame in art.frames:
        source_x = max(0, -frame.x)
        source_y = max(0, -frame.y)
        source_end_x = min(frame.width, width - frame.x)
        source_end_y = min(frame.height, height - frame.y)
        if source_x >= source_end_x or source_y >= source_end_y:
            continue

        for y in range(source_y, source_end_y):
            source_start = y * frame.width + source_x
            source_end = y * frame.width + source_end_x
            target_start = (frame.y + y) * width + frame.x + source_x
            row = frame.pixels[source_start:source_end]
            if transparent_zero:
                for offset, value in enumerate(row):
                    if value:
                        canvas[target_start + offset] = value
            else:
                canvas[target_start : target_start + len(row)] = row
    return bytes(canvas)


def save_indexed_png(
    pixels: bytes,
    width: int,
    height: int,
    palette: bytes,
    output: Path,
    scale: int,
    transparent_zero: bool,
) -> None:
    if scale <= 0:
        raise ArtFormatError("scale must be positive")
    image = Image.frombytes("P", (width, height), pixels)
    image.putpalette(expand_vga_palette(palette))
    if scale != 1:
        image = image.resize(
            (width * scale, height * scale), Image.Resampling.NEAREST
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    save_options = {"transparency": 0} if transparent_zero else {}
    image.save(output, **save_options)


def print_frames(art: ArtResource) -> None:
    print("index x y width height data_offset")
    for frame in art.frames:
        print(
            f"{frame.index:03d} {frame.x:6d} {frame.y:6d} "
            f"{frame.width:5d} {frame.height:6d} {frame.data_offset:08x}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path, help="path to an extracted ART file")
    parser.add_argument("--palette", type=Path, help="path to a 768-byte PAL file")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list frame descriptors")
    action.add_argument("--frame", type=int, help="render one frame by index")
    action.add_argument(
        "--canvas", action="store_true", help="composite frames on a canvas"
    )
    action.add_argument(
        "--all-frames", type=Path, metavar="DIRECTORY", help="render every frame"
    )
    parser.add_argument("--output", type=Path, help="PNG output for one render")
    parser.add_argument("--width", type=int, default=320, help="canvas width")
    parser.add_argument("--height", type=int, default=200, help="canvas height")
    parser.add_argument("--scale", type=int, default=1, help="nearest-neighbor scale")
    parser.add_argument(
        "--opaque-zero",
        action="store_true",
        help="draw palette index 0 instead of treating it as transparent",
    )
    args = parser.parse_args(argv)

    rendering = args.frame is not None or args.canvas or args.all_frames is not None
    if rendering and args.palette is None:
        parser.error("rendering requires --palette")
    if (args.frame is not None or args.canvas) and args.output is None:
        parser.error("--frame and --canvas require --output")
    if args.output is not None and not (args.frame is not None or args.canvas):
        parser.error("--output requires --frame or --canvas")
    if args.scale <= 0:
        parser.error("--scale must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        art = ArtResource.from_path(args.art)
        if args.frame is None and not args.canvas and args.all_frames is None:
            print_frames(art)
            return 0

        palette = load_vga_palette(args.palette)
        transparent_zero = not args.opaque_zero
        if args.frame is not None:
            if args.frame < 0 or args.frame >= len(art.frames):
                raise ArtFormatError(f"frame index out of range: {args.frame}")
            frame = art.frames[args.frame]
            save_indexed_png(
                frame.pixels,
                frame.width,
                frame.height,
                palette,
                args.output,
                args.scale,
                transparent_zero,
            )
        elif args.canvas:
            pixels = compose_canvas(
                art,
                args.width,
                args.height,
                transparent_zero=transparent_zero,
            )
            save_indexed_png(
                pixels,
                args.width,
                args.height,
                palette,
                args.output,
                args.scale,
                False,
            )
        else:
            args.all_frames.mkdir(parents=True, exist_ok=True)
            for frame in art.frames:
                filename = (
                    f"{frame.index:03d}_x{frame.x:+d}_y{frame.y:+d}_"
                    f"{frame.width}x{frame.height}.png"
                )
                save_indexed_png(
                    frame.pixels,
                    frame.width,
                    frame.height,
                    palette,
                    args.all_frames / filename,
                    args.scale,
                    transparent_zero,
                )
    except (ArtFormatError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
