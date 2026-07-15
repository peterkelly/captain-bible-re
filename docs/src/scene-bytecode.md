# Scene Bytecode

## Overview

The 62 expanded `BIN` members are the game's scene programs. Most are pure
bytecode streams with no header. They select art and palettes, start music,
change scenes, update variables, branch, call subroutines, and coordinate
animation. The executable's interpreter dispatches opcodes `0x01` through
`0x91` through a 145-entry near-pointer table at load offset `0x59AB`.

The operand layout has been recovered for every dispatched opcode. Linear
decoding identifies 25,837 commands in 64 code regions and uses 122 of the 145
possible opcodes. Semantic names remain conservative: operand boundaries are
known for the whole instruction set, while many handlers still need gameplay
correlation before their purpose can be named.

## Runtime model

`initialize_scene` at `0x6631` appends `.BIN` to a scene base name, loads that
archive member into far memory, installs its base and initial cursor, resets
scene-thread state, and calls `execute_bin_commands` at `0x451B` with file
offset zero. Later, `update_scene_threads` at `0x7997` resumes active command
streams by passing their saved file offsets back to the same interpreter.

Four words in the data segment hold the current input state:

| DS offset | Runtime example | Interpretation |
|---:|---:|---|
| `0x00F6` | `0x004B` | Current file-relative bytecode offset. |
| `0x00F8` | `0x4C13` | Segment containing the current bytecode cursor. |
| `0x00FA` | `0x0000` | Offset of the loaded resource's far-memory base. |
| `0x00FC` | `0x4C13` | Segment containing the resource base. |

The interpreter sets its cursor to `base + requested_offset`, fetches one
byte, converts opcode 1 to dispatch index 0, range-checks through `0x91`, and
calls the corresponding handler. Branch and call targets are absolute offsets
within the expanded `BIN` member, rather than relative displacements.

Three shared operand readers make the encoding unambiguous:

| Load offset | Current name | Operation |
|---:|---|---|
| `0x3A1E` | `bin_read_u8` | Read one byte and advance the far cursor. |
| `0x3A30` | `bin_read_u16` | Read one little-endian word. |
| `0x3A64` | `bin_read_cstring_offset` | Read a NUL-terminated string and return its base-relative offset; byte `0xFF` escapes to an explicit 16-bit offset. |

## Operand schema

The decoder records each opcode with a compact schema:

| Marker | Encoding |
|---|---|
| `B` | Unsigned byte. |
| `H` | Unsigned little-endian 16-bit word. |
| `z` | NUL-terminated CP437 string, or `FF` plus an explicit 16-bit resource-string offset. |
| `9` | Opaque nine-byte animation record skipped by opcode `0x07`. |
| `s` | An additional word only when the preceding `H`, interpreted as signed, is negative. |

The conditional `BHs` form is used by opcodes `0x11`, `0x12`, and `0x17`
through `0x1A`. For example, bytes `11 01 F8 FF E6 01` contain byte 1, signed
word -8, and therefore the extra word `0x01E6`.

The complete machine-readable table is `OPCODE_SCHEMAS` in
`tools/inspect_bin.py`. It contains one entry for every value from `0x01`
through `0x91`; tests extract the resources directly from `CB/DD1.DAT` and
exercise every known code region against that table.

## Identified commands

These handler meanings have direct static support from their callees or clear
control-flow behavior:

| Opcode | Operands | Current name | Evidence |
|---:|---|---|---|
| `0x01` | `z` | `load_art` | Passes the name to `load_art_resource`, which appends `.ART`. |
| `0x05` | none | `return_minus_one` | Terminates interpretation with return value -1. |
| `0x02` | `BHHH` | `create_scene_thread` | Initializes a thread slot and appends a type-`0x02` display record. |
| `0x03` | `BBHHB` | `add_native_scale_display_object` | Appends a directly rendered object with implicit scale `0x0100`. |
| `0x04` / `0x43` | `BBHHHB` | `add_scaled_display_object` | Appends a directly rendered object with frame, ART slot, X, Y, scale, and flags. |
| `0x06` | `H` | `begin_animation_sequence` | Creates animation state and appends a type-`0x06` display record. |
| `0x07` | `9` | `animation_step` | Advances over a fixed nine-byte step retained for later animation updates. |
| `0x0D` | `zz` | `change_scene` | Selects a new scene and secondary segment name. |
| `0x0F` | `H` | `adjust_thread_delay` | Updates the current command thread's wait value. |
| `0x1E` | `HH` | `copy_variable` | Copies one signed script-variable word to another. |
| `0x1F` | `HH` | `set_variable` | Stores an immediate in a script variable. |
| `0x20` | `HH` | `jump_if_zero` | Selects an absolute target when a variable is zero. |
| `0x21` | `HH` | `jump_if_nonzero` | Selects an absolute target when a variable is nonzero. |
| `0x22`–`0x29` | `HHH` | variable comparisons | Compare variable/variable or variable/immediate pairs and conditionally jump. |
| `0x2A`–`0x31` | `HH` | variable arithmetic | Add, subtract, multiply, or divide a destination by a variable or immediate. |
| `0x32` | `H` | `increment_variable` | Increments a numbered variable. |
| `0x33` | `H` | `decrement_variable` | Decrements a numbered variable. |
| `0x34` | `H` | `call` | Saves a return offset and jumps to an absolute target. |
| `0x35` | none | `return` | Resumes the saved bytecode return offset. |
| `0x36` / `0x37` | `B` | set/clear text-record state | Mutates persistent descriptor byte `+4` selected by record identifier. |
| `0x38` / `0x39` | `BH` | branch on text-record state | Selects a target when a record state is set / clear. |
| `0x3D` | `H` | `jump` | Replaces the cursor with an absolute file offset. |
| `0x4D` | `z` | `load_palette` | Calls `load_palette_resource`, which appends `.PAL`. |
| `0x52` | `B` | `play_music` | Builds `MUS###` or `IBM###` and loads an XMI member. |
| `0x55` | none | `snapshot_state` | Copies the live state into a retained buffer. |
| `0x57` | `BH` | `play_sound_effect` | Builds `D###.ABT`, decodes it, and starts playback at the supplied rate. |
| `0x58` | none | `stop_sound_effect` | Stops active digital playback and releases its PCM buffer. |
| `0x65` | `BB` | `clear_display_object_frames` | Sets the frame byte to zero across a consecutive display-record range. |
| `0x66` | `BBBB` | `advance_display_object_frames` | Increments and range-wraps frame bytes across consecutive records. |
| `0x6D` | `z` | `load_palette` | Uses the same palette-loading path as `0x4D`. |
| `0x70` | none | `unload_last_art` | Releases the most recently loaded art slot. |
| `0x73` / `0x74` | `BH` | branch on state flag | Selects a target when a boolean state flag is clear / set. |
| `0x75` / `0x76` | `B` | clear/set state flag | Mutates one identifier in the 128-bit state bank. |
| `0x77` | none | `process_current_map_cell` | Calls the current-cell handler, which consults the cell and its neighbors. |
| `0x78` | `B` | `load_map` | Combines a level letter with the current `E`/`N`/`D` difficulty code and loads a `.MAP` member. |
| `0x7B` | `H` | `set_current_map_cell_kind` | Replaces the low nibble of the current cell from a script variable. |
| `0x7C` | `H` | `set_current_map_cell_parameter_a` | Writes the current cell's second byte from a script variable. |
| `0x7F` | `H` | `set_current_map_cell_parameter_b` | Writes the current cell's third byte from a script variable. |
| `0x81` | `H` | `reduce_faith` | Subtracts a difficulty-scaled immediate from faith unless no-combat mode is active. |
| `0x85` / `0x86` | `B` | hide/show display object | Sets / clears the high hidden bit in a display record's ART-slot byte. |
| `0x87` | none | `normalize_map_cells` | Applies recovered location-kind and parameter transitions across the grid. |
| `0x88` | none | `clear_text_record_states` | Clears persistent byte `+4` in all 66 text descriptors. |
| `0x89` | none | `mark_current_map_cell_explored` | Sets the current X bit in the current Y exploration row. |
| `0x8F` / `0x90` | `HH` | variable bitwise AND | ANDs a destination with a variable / immediate. |

The suffix strings are present in the executable data segment and were also
checked in the QEMU process image: `.PAL` at `DS:0434`, `.ART` at `DS:0490`,
and `.BIN` at `DS:0721`. This corrects an early interpretation of bytes such
as `4D 54 49 54 4C 45 00` as the string `MTITLE`: byte `0x4D` is actually the
palette opcode followed by the string `TITLE`.

## Startup programs

The QEMU DOS trace and archive directory give this resource-load sequence:

```text
LOGO.BIN -> LOGO.PAL -> LOGO.ART -> D003.ABT
TITLE.BIN -> TITLE.PAL -> TITLE.ART -> TITLE2.ART -> MUS001.XMI
INTRO.BIN -> INTRO.ART
```

The scripts involved decode completely:

| Resource | Expanded bytes | Commands |
|---|---:|---:|
| `LOGO.BIN` | 640 | 114 |
| `TITLE.BIN` | 436 | 80 |
| `INTRO.BIN` | 184 | 39 |
| `MENU.BIN` | 2,004 | 99 |

`INTRO.BIN` begins by setting two small state values, loading `TITLE.PAL`,
loading `INTRO.ART`, and drawing the opening sequence. Opcode `0x52` selects
music index 1, which produces `MUS001.XMI`. At file offset `0x009A`, opcode
`0x0D` carries strings `dome` and `seg` to enter the first gameplay scene.

The runtime dump contains all 184 `INTRO.BIN` bytes at physical address
`0x4C130`. The base pointer `4C13:0000` appears at physical address `0x14F0A`,
stored as offset word `0000` at `DS:00FA` and segment word `4C13` at
`DS:00FC`. The live cursor is `4C13:004B`; resource offset
`0x004B` begins opcode `0x42` and is exactly the boundary after the preceding
`return_minus_one` command. This ties the static decoder's command boundaries
to live interpreter state.

## Mixed code and data

Sixty members decode linearly from byte zero through end of file. Two members
contain non-code regions:

- `CP2.BIN` has commands from `0x0000` through `0x1D5A`, followed by a
  251-byte structured data trailer.
- `ROOM3.BIN` has command regions `0x0000..0x0336`,
  `0x0C96..0x1754`, and `0x1768..0x19DB`. A 2,400-byte zero-filled block and
  a 20-byte zero-filled block separate them.

Opcode zero is invalid. The decoder deliberately reports it instead of
guessing that arbitrary padding or embedded tables are executable commands.
The later `ROOM3.BIN` entry points are therefore decoded explicitly rather
than reached by a single linear sweep.

## Inspection tool

After extracting the archive, inspect a complete stream with:

```sh
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN
```

Use explicit bounds for embedded regions:

```sh
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x0c96 --limit 0x1754
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x1768
```

Output includes the file-offset range, opcode, current semantic name, and
typed operands. Variable operands show both their word index and encoded byte
offset, with recovered names such as `var[21:faith]@0x002a`. Other words with
their high bit set are displayed in both unsigned hexadecimal and signed
decimal forms. Unidentified handlers retain names such as `opcode_3a`,
preserving useful structure without assigning speculative semantics.

Add `--objects` to append a linear summary of commands which define display
records. The [scene-display-object chapter](scene-objects.md) documents the
ten-byte runtime record, renderer flags, QEMU validation, and the important
caveat that branches can skip or repeat definitions.

## Executable routines

| Load offset | Current name |
|---:|---|
| `0x034F` | `load_map_resource` |
| `0x0457` | `normalize_map_cells` |
| `0x075F` | `show_map_screen` |
| `0x0C6C` | `process_current_map_cell` |
| `0x3AD2` | `reset_scene_display_records` |
| `0x3AFF` | `render_scene_display_records` |
| `0x3A1E` | `bin_read_u8` |
| `0x3A30` | `bin_read_u16` |
| `0x3A64` | `bin_read_cstring_offset` |
| `0x4001` | `load_palette_resource` |
| `0x4091` | `play_music_resource` |
| `0x451B` | `execute_bin_commands` |
| `0x6631` | `initialize_scene` |
| `0x7997` | `update_scene_threads` |
| `0xB948` | `release_render_slot` |
| `0xBCAC` | `render_scene_display_object` |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
