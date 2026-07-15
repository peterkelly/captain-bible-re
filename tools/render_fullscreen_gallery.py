#!/usr/bin/env python3
"""Render an annotated gallery of every full-screen Captain Bible ART frame."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

from extract_dd1 import DD1Archive
from inspect_bin import BinFormatError, decode_stream
from render_art import ArtResource, expand_vga_palette, parse_vga_palette


SCREEN_WIDTH = 320
SCREEN_HEIGHT = 200


class GalleryError(ValueError):
    """Raised when a full-screen frame has no unambiguous palette."""


@dataclass(frozen=True)
class FullscreenFrame:
    archive_index: int
    art_name: str
    frame_index: int
    palette_name: str
    pixels: bytes
    palette: bytes


def _command_regions(filename: str, size: int) -> tuple[tuple[int, int], ...]:
    if filename == "CP2.BIN":
        return ((0, 0x1D5A),)
    if filename == "ROOM3.BIN":
        return ((0, 0x0336), (0x0C96, 0x1754), (0x1768, size))
    return ((0, size),)


def infer_art_palettes(archive: DD1Archive) -> dict[str, tuple[str, ...]]:
    """Infer ART-to-PAL associations from linear resource-loading commands."""

    associations: dict[str, set[str]] = {}
    for entry in archive.entries:
        if entry.extension != "BIN":
            continue
        data = archive.extract(entry)
        for start, limit in _command_regions(entry.filename, len(data)):
            try:
                commands = decode_stream(data, start, limit)
            except BinFormatError as error:
                raise GalleryError(f"cannot decode {entry.filename}: {error}") from error
            palette_name: str | None = None
            for command in commands:
                if command.opcode in (0x4D, 0x6D):
                    value = command.operands[0].value
                    if isinstance(value, str):
                        palette_name = value.upper()
                elif command.opcode == 0x01 and palette_name is not None:
                    value = command.operands[0].value
                    if isinstance(value, str):
                        associations.setdefault(value.upper(), set()).add(
                            palette_name
                        )
    return {
        art_name: tuple(sorted(palette_names))
        for art_name, palette_names in associations.items()
    }


def discover_fullscreen_frames(archive: DD1Archive) -> tuple[FullscreenFrame, ...]:
    """Return every `(0, 0, 320, 200)` ART frame and its script-selected PAL."""

    associations = infer_art_palettes(archive)
    frames = []
    for entry in archive.entries:
        if entry.extension != "ART":
            continue
        art = ArtResource.from_bytes(archive.extract(entry))
        for frame in art.frames:
            dimensions = (frame.x, frame.y, frame.width, frame.height)
            if dimensions != (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT):
                continue

            art_name = entry.name.upper()
            palette_names = associations.get(art_name, ())
            if len(palette_names) != 1:
                raise GalleryError(
                    f"{entry.filename} has {len(palette_names)} inferred palettes: "
                    f"{', '.join(palette_names) or 'none'}"
                )
            palette_name = palette_names[0]
            matches = archive.matching(f"{palette_name}.PAL")
            if not matches:
                raise GalleryError(
                    f"palette {palette_name}.PAL for {entry.filename} is absent"
                )
            palette = parse_vga_palette(archive.extract(matches[0]))
            frames.append(
                FullscreenFrame(
                    archive_index=entry.index,
                    art_name=entry.filename,
                    frame_index=frame.index,
                    palette_name=f"{palette_name}.PAL",
                    pixels=frame.pixels,
                    palette=palette,
                )
            )
    return tuple(frames)


def _font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _render_frame(item: FullscreenFrame, scale: int) -> Image.Image:
    image = Image.frombytes("P", (SCREEN_WIDTH, SCREEN_HEIGHT), item.pixels)
    image.putpalette(expand_vga_palette(item.palette))
    image = image.convert("RGB")
    if scale != 1:
        image = image.resize(
            (SCREEN_WIDTH * scale, SCREEN_HEIGHT * scale),
            Image.Resampling.NEAREST,
        )
    return image


def render_gallery(
    frames: tuple[FullscreenFrame, ...], columns: int = 4, scale: int = 1
) -> Image.Image:
    """Create an annotated RGB contact sheet in archive order."""

    if not frames:
        raise GalleryError("no full-screen frames found")
    if columns <= 0 or scale <= 0:
        raise GalleryError("columns and scale must be positive")

    margin = 16 * scale
    gap = 12 * scale
    title_height = 34 * scale
    label_height = 42 * scale
    frame_width = SCREEN_WIDTH * scale
    frame_height = SCREEN_HEIGHT * scale
    rows = (len(frames) + columns - 1) // columns
    width = margin * 2 + columns * frame_width + (columns - 1) * gap
    height = (
        margin * 2
        + title_height
        + rows * (frame_height + label_height)
        + (rows - 1) * gap
    )

    gallery = Image.new("RGB", (width, height), (17, 20, 27))
    draw = ImageDraw.Draw(gallery)
    title_font = _font("DejaVuSans-Bold.ttf", 17 * scale)
    label_font = _font("DejaVuSans-Bold.ttf", 12 * scale)
    detail_font = _font("DejaVuSans.ttf", 11 * scale)
    draw.text(
        (margin, margin),
        f"Captain Bible — full-screen ART frames ({len(frames)})",
        fill=(245, 246, 250),
        font=title_font,
    )

    origin_y = margin + title_height
    for item_index, item in enumerate(frames):
        row, column = divmod(item_index, columns)
        x = margin + column * (frame_width + gap)
        y = origin_y + row * (frame_height + label_height + gap)
        gallery.paste(_render_frame(item, scale), (x, y))
        draw.rectangle(
            (x, y + frame_height, x + frame_width - 1, y + frame_height + label_height),
            fill=(29, 34, 45),
        )
        draw.text(
            (x + 8 * scale, y + frame_height + 4 * scale),
            f"{item.archive_index:03d} · {item.art_name} · frame {item.frame_index}",
            fill=(244, 246, 252),
            font=label_font,
        )
        draw.text(
            (x + 8 * scale, y + frame_height + 22 * scale),
            f"palette: {item.palette_name}",
            fill=(168, 180, 202),
            font=detail_font,
        )
    return gallery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="path to DD1.DAT")
    parser.add_argument("--output", type=Path, required=True, help="output PNG")
    parser.add_argument("--columns", type=int, default=4, help="gallery columns")
    parser.add_argument(
        "--scale", type=int, default=1, help="nearest-neighbor integer scale"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        archive = DD1Archive.from_path(args.archive)
        frames = discover_fullscreen_frames(archive)
        gallery = render_gallery(frames, args.columns, args.scale)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        gallery.save(args.output)
    except (GalleryError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"wrote {args.output}: {gallery.width}x{gallery.height}, {len(frames)} frames")
    for item in frames:
        print(
            f"{item.archive_index:03d} {item.art_name} "
            f"frame={item.frame_index} palette={item.palette_name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
