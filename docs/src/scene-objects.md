# Scene Display Objects

## Scope and terminology

The scene runtime maintains a 100-entry display list which connects BIN
commands to animation, command threads, ART frames, and the renderer. Some
records visually represent characters, enemies, or props, but the structure
itself is a display list. Calling every entry a gameplay entity would be
misleading: the same list also contains animation-group and thread records.

The recovered model is based on the bytecode handlers, the scene update and
render paths, and a live QEMU capture of `LOGO.BIN`.

## Runtime layout

The list count is a word at `DS:00E2`. Records begin at `DS:A2AC`, have a
ten-byte stride, and are addressed as `A2AC + index * 10`. The update routine
at load offset `0x3AFF` rejects counts greater than 100, establishing the
capacity.

For directly rendered record types `0x03` and `0x43`, the layout is:

| Offset | Size | Meaning |
|---:|---:|---|
| `+0` | 2 | Signed X coordinate. |
| `+2` | 2 | Signed Y coordinate. |
| `+4` | 2 | 8.8 scale; `0x0100` is native size. |
| `+6` | 1 | Loaded ART slot. Bit 7 is also the hidden marker. |
| `+7` | 1 | One-based ART frame number; zero suppresses drawing. |
| `+8` | 1 | Render flags; bits 0 and 1 flip the two axes. |
| `+9` | 1 | Display-record type. |

This assignment follows the arguments passed to the renderer at `0xBCAC`.
That routine selects a loaded ART resource with the low seven bits of byte
`+6`, subtracts one from the frame number, applies coordinates and scale, and
derives the two flip bits from byte `+8`. An ART-slot byte in `0x80..0xEF`,
or frame zero, releases/suppresses the render slot instead of drawing it.

Visibility is therefore encoded in the ART-slot byte rather than the separate
render-flags byte. The slot byte should not be modeled as a plain array index
without masking or checking its high bit.

## Record types

Four type values are written by the recovered scene handlers:

| Type | Producer | Role |
|---:|---|---|
| `0x02` | Opcode `0x02` | Connects one of the 16-byte scene-command thread slots to the display/update list. |
| `0x03` | Opcode `0x03` | Direct ART-frame object with an implicit native scale of `0x0100`. |
| `0x43` | Opcodes `0x04` and `0x43` | Direct ART-frame object with an explicit scale. |
| `0x06` | Opcode `0x06` | Connects an animation sequence to the display/update list. |

The update routine handles type `0x02` through the scene-thread path. Types
`0x03` and `0x43` are submitted directly to the object renderer. Type
`0x06` is owned by the animation-sequence path. The ten-byte fields not used
by a type can contain zero or stale data and must not be interpreted as a
direct object's coordinates.

## Scene commands

The definition and direct frame-control commands are:

| Opcode | Operands | Effect |
|---:|---|---|
| `0x02` | `thread, x, y, scale` | Initializes a 16-byte command-thread slot and appends a type-`0x02` display record. |
| `0x03` | `frame, art, x, y, flags` | Appends a native-scale type-`0x03` display object; unused by shipped scripts. |
| `0x04` / `0x43` | `frame, art, x, y, scale, flags` | Appends a scaled type-`0x43` display object. |
| `0x06` | `delay` | Begins an animation sequence and appends a type-`0x06` display record. |
| `0x07` | nine-byte record | Supplies an animation step retained within the BIN stream. |
| `0x65` | `first, count` | Sets frame byte `+7` to zero for a consecutive display-record range; unused by shipped scripts. |
| `0x66` | `first, count, minimum, maximum` | Increments each selected frame and resets values outside the inclusive range to `minimum`; unused by shipped scripts. |
| `0x85` | `index` | Sets ART-slot bit 7, hiding a direct display object. |
| `0x86` | `index` | Clears ART-slot bit 7, showing a direct display object. |

The animation step is not copied when opcode `0x07` executes. The handler
advances over its nine bytes; the animation state created by opcode `0x06`
retains a BIN-stream location and consumes the records later. This explains
why the command decoder originally could establish the nine-byte boundary
before the animation lifecycle was understood.

The animation slot and step layouts, lifecycle commands, and linked-transform
path are now documented in the [combat-runtime chapter](combat-runtime.md).

Victim scenes use `0x85` and `0x86` on groups of display indices when their
visual state changes. For example, `NAGE.BIN` hides a set of crystal-related
objects in a subroutine selected by progression flags. This is evidence for
display visibility, not by itself for entity death or activation state.

## Lifecycle

`initialize_scene` calls the reset routine at `0x3AD2` before loading and
executing the next BIN resource. The reset routine visits every current
display index, releases its render slot, and sets the count to zero.

During scene updates, `0x3AFF` walks the current list:

- type `0x02` invokes the associated thread/update slot;
- types `0x03` and `0x43` pass the recovered ten-byte fields to `0xBCAC`;
- other supported types are serviced by their dedicated animation paths.

The main frame update calls those controller paths separately, but call order
is not layer order. Each path writes into the render slot reserved by its
mixed display-record index. Direct rendering passes `index + 1` at
`0x3B72`--`0x3B76`; animation rendering passes its saved display index plus
one at `0x3D64`--`0x3D6B`; scene-thread movement does the same at
`0x763D`--`0x7642`. The dirty-region compositor at `0xC000` then advances
through the 26-byte render slots in increasing order.

This distinction supplies the opening oval mask. In `LOGO.BIN`, the moving
`RUN.ART` controller is display record 4, while the direct dome and bridge
pieces are records 7 through 9. The later scenery covers the character outside
the oval as it enters and leaves. It is display-list occlusion rather than a
separate geometric clipping primitive. Regrouping records as direct,
animation, and movement passes incorrectly forces the character above the
mask.

The list is runtime scene state and is reconstructed from the BIN program. It
is not serialized in the save file.

## QEMU validation

The game was started with the repository's visible and silent trace mode:

```sh
./run.sh --trace-dos
```

At the Bridgestone logo screen, QEMU reported `DS=14E1`. A one-megabyte
physical-memory dump therefore placed the count at physical `0x14EF2` and
the record table at physical `0x1F0BC`. The live count was 13.

The three directly rendered records were:

| Index | X | Y | Scale | Flags | Frame | ART slot | Type |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 303 | 0 | `0x0100` | 1 | 4 | 1 | `0x43` |
| 8 | 3 | 0 | `0x0100` | 0 | 4 | 1 | `0x43` |
| 9 | 3 | 0 | `0x0100` | 0 | 1 | 1 | `0x43` |

These values exactly match the three `0x43` commands at BIN offsets
`0x0122`, `0x012C`, and `0x0136`. Records 0–3 and 10 are the five animation
sequences begun by opcode `0x06`; records 4–6 and 11–12 are the five scene
threads created by opcode `0x02`. Thus all 13 definitions in the linear
startup path match the live type order and count.

The dump and screen capture are retained as ignored analysis artifacts under
`build/qemu-trace/`.

## Inspector

Show the normal command listing followed by its linear display definitions:

```sh
tools/inspect_bin.py build/dd1/all/001_LOGO.BIN --objects
```

The summary includes source offset, type, and all definition fields known for
that type. It follows linear file order; branches and calls can skip or repeat
definitions at runtime, so indices outside a straight startup sequence are
not guaranteed live indices.

## Controller timer rate

The hardware initialization at load offset `0x3600` installs the interrupt-8
handler at `0xAAE4`. It programs PIT channel zero in mode 3 with divisor
`0x26D7` (9,943), producing approximately 120 interrupts per second. Each
interrupt increments the counter at `0x4B66`. The elapsed-delta helper at
`0x00B6` multiplies that counter by 24 and caps the result at 400 before the
frame controller at `0x7A8D` distributes it to animations, scene threads, and
movement. The resulting controller rate is approximately 2,880 units per
second, not one unit per millisecond.

## Remaining questions

- The opcode-`0x02` 16-byte interactive/display record still needs names for
  every field and a clearer distinction from the true BIN scheduler table.
- Combat targeting uses a separate ten-byte screen-action table. No evidence
  yet connects direct display objects to collision or enemy health.
- The last two bytes of each 12-byte animation slot and several detailed mode
  transitions remain unnamed.
- A display record can visually represent a character, but no identity or
  gameplay-stat field exists in this ten-byte structure.

## Relevant executable functions

| Load offset | Current name |
|---:|---|
| `0x3AD2` | `reset_scene_display_records` |
| `0x3AFF` | `render_scene_display_records` |
| `0x451B` | `execute_bin_commands` |
| `0x6631` | `initialize_scene` |
| `0xB948` | `release_render_slot` |
| `0xBCAC` | `render_scene_display_object` |

Offsets use the unpacked load-module convention.
