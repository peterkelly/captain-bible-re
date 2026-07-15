# World Maps

## Resource set and naming

`DD1.DAT` contains 21 `MAP` members: one for every combination of level
letter `A` through `G` and difficulty code `E`, `N`, or `D`. The codes mean
Easy, Normal, and Difficult, matching the three modes described by the
manual. Archive directory entries 215 through 235 contain this complete
cross product, and every member expands to exactly 768 bytes.

Scene opcode `0x78` supplies a level letter. Its handler at load offset
`0x034F` reads script variable zero as a difficulty index, selects one byte
from the literal `END`, appends `.MAP`, and loads the resulting archive
member into the live grid at `DS:5B16`. Uses across the scene corpus supply
all seven letters. For example, level C on Easy mode loads `CE.MAP`.

## Grid layout

Each resource is a headerless, row-major 16×16 grid with three bytes per
cell:

```text
cell_offset = 3 * (16 * y + x)

+0  packed connection/location byte
+1  parameter A
+2  parameter B
```

Coordinates range from zero through 15. Disassembly repeatedly computes
`48*y + 3*x`, including accesses to the four neighboring cells by adding or
subtracting 3 for X and 48 for Y. The current X and Y coordinates are words
at `DS:7290` and `DS:7292`.

The first byte has two independently used nibbles:

- The high nibble selects one of 16 connection or shape frames when the map
  screen is drawn. It is conservatively called `connection_mask`; the
  direction represented by each individual bit has not yet been mapped.
- The low nibble selects a location kind. Scripts can replace it while
  preserving the high nibble. Several numeric kinds can be correlated with
  map glyphs and gameplay branches, but a complete symbolic enumeration is
  not yet justified.

Parameters A and B are also manipulated separately by scene commands. The
map screen uses them as text-record selectors for at least location kinds
`0x6` and `0xA`, consistent with the manual's statement that stations and
communication locations show verse references. Other meanings remain open.

## Runtime state and scene commands

The loaded resource becomes mutable gameplay state. The following commands
have direct support in their handlers:

| Opcode | Operands | Effect |
|---:|---|---|
| `0x77` | none | Process the current cell, consulting adjacent cells and current state. |
| `0x78` | `B` | Load the selected level's map for the current difficulty. |
| `0x7B` | `H` | Set the current cell's low location-kind nibble from a script variable while preserving its high nibble. |
| `0x7C` | `H` | Set parameter A from a script variable. |
| `0x7F` | `H` | Set parameter B from a script variable. |
| `0x87` | none | Normalize location cells after loading or state changes. |
| `0x89` | none | Mark the current coordinate explored. |

Opcode `0x89` updates a separate 16-word row bitmap at `DS:72C4`:

```text
explored_rows[y] |= 1 << x
```

The F2 map screen tests this bitmap while rendering its 16×16 display. This
agrees with the manual: explored areas appear gold, unexplored areas gray,
stations and communication points display verse references, and room types
are marked with the letters `P`, `J`, `T`, `C`, and `V`.

The normalization routine at `0x0457` proves that resource bytes are not
immutable identifiers. In one pass it changes low kind `0x6` to `0xA`, moves
parameter B to parameter A, and clears parameter B. In another relevant pass,
location kinds `0x1` through `0x9` become `0xB`. Further control-flow work is
needed to name the conditions and gameplay states behind those transitions.

## Save-state correlation

Both the live grid and its checkpoint copy are serialized in every 2,752-byte
state file. They occupy file offsets `0x4C0` and `0x7C0`, respectively. The
supplied `DDGAMES.SV3` and `DDGAMES.SV4` grids match `CE.MAP` except for four
field changes:

| Coordinate | Field | Resource | Saved |
|---|---:|---:|---:|
| `(2,0)` | parameter B | `0x38` | `0x00` |
| `(0,1)` | parameter A | `0x37` | `0x00` |
| `(1,1)` | packed byte | `0xA2` | `0xAB` |
| `(2,1)` | packed byte | `0xE5` | `0xEB` |

The two packed-byte mutations preserve their high nibbles and replace their
low kinds with `0xB`, exactly as the normalizer does. This byte-level match
independently identifies the saved 16×16×3 tables as world-map state. The
other supplied saves have zeroed grids and cannot be assigned to an archive
map from this field alone.

## Inspection tool

Inspect a resource directly from the archive:

```sh
tools/inspect_map.py CB/DD1.DAT --map CE
tools/inspect_map.py CB/DD1.DAT --map CE --cells
```

The compact display prints the low location-kind nibble at every coordinate.
`--cells` adds the packed byte, connection nibble, kind, and both parameters
for every nonzero cell. Compare a resource with the live grid in a state save
with:

```sh
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

The parser requires an exact 768-byte grid and a valid level/difficulty name.
Tests cover all 21 archive members, row-major addressing, all seven script
level selectors, invalid inputs, and the four saved mutations above.

## Relevant executable functions and data

| Load offset / DS offset | Current name or role |
|---:|---|
| `0x034F` | `load_map_resource` |
| `0x0457` | `normalize_map_cells` |
| `0x075F` | `show_map_screen` |
| `0x0C6C` | `process_current_map_cell` |
| `DS:5B16` | Live 768-byte grid |
| `DS:7290` / `DS:7292` | Current X / Y coordinates |
| `DS:72C4` | Sixteen explored-row bitmaps |
| `DS:76EC` | Checkpoint 768-byte grid |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
