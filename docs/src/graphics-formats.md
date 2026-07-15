# Palette and Artwork Formats

## `PAL`: VGA DAC entries

Every one of the 37 `PAL` members is exactly 768 bytes: 256 consecutive
red/green/blue triplets. Each component is in the inclusive range 0 through
63, matching the VGA's six-bit DAC. There is no header. The host renderer
expands a component with bit replication,
`eight_bit = (six_bit << 2) | (six_bit >> 4)`, so both endpoints remain exact.

The executable confirms this interpretation in two independent paths:

- `vga_load_palette_bios` at `0xA017` invokes video BIOS function `1012h` with
  256 entries, start index 0, and a far pointer to the triplets.
- `vga_write_palette_range` at `0xA032` waits for vertical retrace through port
  `03DAh`, writes a starting index to `03C8h`, then sends three unmodified bytes
  per entry to `03C9h`.

There are 35 unique palette payloads. The two copies of `GANTRY.PAL` are
identical, and `RICH.PAL` is identical to `1.PAL`. The game also changes
palette ranges at runtime for fades and color cycling, so a base `PAL` preview
does not necessarily reproduce every animated color at a particular instant.

## `ART`: descriptors and indexed pixels

An `ART` member begins with one or more fixed 12-byte frame descriptors. It has
no explicit descriptor count; the first descriptor's pixel offset is also the
end of the descriptor table, so the count is `first_offset / 12`.

| Descriptor offset | Size | Type | Meaning |
|---:|---:|---|---|
| `0x00` | 2 | signed little-endian | Horizontal origin or anchor offset. |
| `0x02` | 2 | signed little-endian | Vertical origin or anchor offset. |
| `0x04` | 2 | unsigned little-endian | Width in pixels. |
| `0x06` | 2 | unsigned little-endian | Height in pixels. |
| `0x08` | 4 | unsigned little-endian | Absolute pixel-data offset in this member. |

Each descriptor is followed indirectly by exactly `width * height` bytes of
row-major, eight-bit palette indices. Pixel blocks are contiguous in
descriptor order and occupy the rest of the resource without padding.

This layout validates without exception across all 143 `ART` members:

| Property | Value |
|---|---:|
| Total frame descriptors | 1,178 |
| Total indexed pixels | 4,850,699 |
| Largest frame table | 63 frames in `MAP.ART` |
| Full 320×200 frames at origin `(0, 0)` | 11 |

Signed origins matter. For example, `RUN.ART` frame 0 has origin `(-28, -5)`
and size 46×61; these values position a running sprite relative to an entity,
not directly on the screen. `LOGO.ART` demonstrates a multi-piece screen:

| Frame | X | Y | Width | Height | Pixel offset |
|---:|---:|---:|---:|---:|---:|
| 0 | 88 | 54 | 124 | 74 | `0x48` |
| 1 | 94 | 80 | 112 | 107 | `0x2420` |
| 2 | 147 | 9 | 138 | 165 | `0x52F0` |
| 3 | 207 | 15 | 101 | 51 | `0xABE2` |
| 4 | -3 | -3 | 7 | 9 | `0xC001` |
| 5 | 22 | 138 | 275 | 30 | `0xC040` |

The descriptor itself does not specify transparency. The draw-call flags
choose the copy operation. `blit_rect_transparent_zero` at `0xA106` tests each
source byte and advances the destination without writing when the index is 0.
`blit_rect_opaque` at `0xA136` copies every byte. The fast VGA copy at
`0xA0C9` copies rows into segment `A000h` using a 320-byte screen stride.

## QEMU framebuffer validation

`INTRO.ART` consists of one descriptor `(0, 0, 320, 200, 12)`. Compared its
64,000 pixel bytes directly with physical VGA memory at `0xA0000` in the
preserved startup dump. Of those bytes, 63,648 are identical. Every one of the
352 differences falls in one of two known live overlays visible in the QEMU
screenshot:

| Overlay | Differing pixels | Difference bounding box |
|---|---:|---|
| Animated floppy/save icon | 333 | X 297–316, Y 1–17 |
| Mouse cursor at screen center | 19 | X 154–166, Y 94–106 |

After excluding those rectangles, the extracted resource and live VGA memory
are byte-for-byte identical. This establishes the descriptor dimensions,
row-major order, one-byte pixels, and mode-13h screen placement independently
of visual interpretation.

The runtime screenshot also maps each used pixel index to a consistent RGB
value. Most static entries match `TITLE.PAL`; entries 243 through 254 differ
because the opening text cycles that palette range while the story is shown.

## Rendering tool

`tools/render_art.py` validates the complete descriptor and pixel layout and
requires a separately extracted `PAL` for rendering. List descriptors with:

```sh
tools/render_art.py build/dd1/all/003_LOGO.ART --list
```

Composite all frames at their signed origins on a 320×200 canvas:

```sh
tools/render_art.py \
  build/dd1/all/003_LOGO.ART \
  --palette build/dd1/all/002_LOGO.PAL \
  --canvas --scale 2 \
  --output build/graphics/logo.png
```

Render one animation frame or all frames separately:

```sh
tools/render_art.py \
  build/dd1/all/082_RUN.ART \
  --palette build/dd1/all/025_TITLE.PAL \
  --frame 0 --scale 2 \
  --output build/graphics/run-0.png

tools/render_art.py \
  build/dd1/all/082_RUN.ART \
  --palette build/dd1/all/025_TITLE.PAL \
  --all-frames build/graphics/run-frames \
  --scale 2
```

Individual frames use index 0 as PNG transparency by default, matching the
color-keyed game path. `--opaque-zero` preserves it as a visible palette color
and selects opaque composition. `--width` and `--height` change canvas size;
`--scale` applies nearest-neighbor integer scaling.

## Executable routines

| Load offset | Current name | Evidence |
|---:|---|---|
| `0x9FF7` | `vga_set_dac_entry` | Writes an index to `03C8h` and one RGB triplet to `03C9h`. |
| `0xA017` | `vga_load_palette_bios` | Loads 256 triplets with BIOS video function `1012h`. |
| `0xA032` | `vga_write_palette_range` | Writes a caller-selected range during vertical retrace. |
| `0xA0C9` | `blit_rect_to_vga` | Copies an opaque rectangle with a 320-byte destination stride. |
| `0xA106` | `blit_rect_transparent_zero` | Copies rows while skipping pixel value 0. |
| `0xA136` | `blit_rect_opaque` | Copies rows without a color key. |
| `0xB620` | `update_palette_effect` | Applies bounded component offsets and submits changed palette ranges. |
| `0xB99C` | `draw_art_frame_opaque` | Indexes a far ART pointer by `frame * 12` and uses width, height, and pixel offset. |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
