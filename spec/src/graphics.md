# Graphics and Palette Rendering

## Logical display

The game renders into a 320-by-200 array of eight-bit palette indexes. The
active palette maps those indexes to 256 RGB colors. A host renderer MAY use a
texture, bitmap, software surface, or GPU pipeline, but scene coordinates and
hit targets always remain in logical pixels.

The final image SHOULD be scaled without filtering. Aspect correction is a
presentation option; it MUST NOT alter logical hit testing.

## `PAL` resources

A `PAL` member is exactly 768 bytes: 256 consecutive red, green, blue triplets.
Every component is in the range 0 through 63. There is no header.

To produce an eight-bit host component while preserving both endpoints, use:

```text
component8 = (component6 << 2) | (component6 >> 4)
```

Loading a palette replaces all 256 base entries. Scene effects may subsequently
modify a range. The engine MUST retain an editable current palette rather than
re-reading the immutable resource for every frame.

## `ART` resources

An `ART` member begins with an array of 12-byte frame descriptors:

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| `0x00` | 2 | signed | Horizontal origin or anchor |
| `0x02` | 2 | signed | Vertical origin or anchor |
| `0x04` | 2 | unsigned | Width in pixels |
| `0x06` | 2 | unsigned | Height in pixels |
| `0x08` | 4 | unsigned | Absolute pixel-data offset in this member |

There is no explicit frame count. The first descriptor's pixel offset marks
the end of the descriptor array, so:

```text
frame_count = first_pixel_offset / 12
```

Each frame owns exactly `width * height` row-major palette indexes. Pixel
blocks are contiguous in descriptor order and fill the remainder of the
member without padding. A parser MUST require a nonzero descriptor count,
12-byte table alignment, in-range offsets, contiguous blocks, and an exact end
at resource length.

Origins are signed anchor adjustments, not necessarily absolute screen
positions. A sprite may therefore begin left or above its logical entity
coordinate.

## Drawing modes

The scene runtime supplies frame number, loaded-art slot, X, Y, 8.8 scale, and
render flags. Frame numbers in display records are one-based; zero suppresses
drawing. The renderer subtracts one before indexing an `ART` descriptor.

Two drawing modes are required:

- **opaque:** copy every source index, including zero;
- **transparent-zero:** skip writes for source index zero.

Render-flag bits 0 and 1 flip the two image axes. Scaling uses `0x0100` as
native size. A compatible renderer MUST apply frame origin, scene coordinate,
scale, and flips consistently and clip output to the logical viewport.

## Composition and display records

Scene display entries are traversed in list order. Direct entries select an
art slot with the low seven bits of their slot byte. Slot bit 7 hides the
entry. An entry with a hidden slot or frame zero does not draw.

Animation entries obtain the same frame, art, position, scale, and flip values
from the current nine-byte animation step. UI overlays, text, and the pointer
are drawn by their active interface after scene composition.

## Palette operations

Scene programs can:

- replace the complete palette;
- fill an inclusive palette-mapping range from a script variable;
- advance a signed phase and rotate an inclusive palette range;
- schedule palette updates; and
- start a blackout effect before a transition.

Range endpoints are inclusive. The rotate operation wraps its phase within
the selected range. A blackout makes the next palette update all black and
advances the effect's countdown. Palette changes SHOULD be applied at frame
boundaries to avoid partially updated presentation.

## Text and UI graphics

Dialogue frames, action labels, maps, status icons, and most large UI elements
are ordinary artwork or scene-driven compositions. Text strings are CP437.
An implementation MAY substitute a metrically compatible bitmap-font renderer
when the font resource path is not exposed, but it MUST preserve wrapping,
selection regions, line order, and 320-by-200 layout closely enough that
scene-defined coordinates remain usable.
