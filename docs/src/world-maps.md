# World Maps

## Resource set and naming

`DD1.DAT` contains 21 `MAP` members: one for every combination of level
letter `A` through `G` and difficulty code `E`, `N`, or `D`. The codes mean
Easy, Normal, and Difficult, matching the three modes described by the
manual. Archive directory entries 215 through 235 contain this complete
cross product, and every member expands to exactly 768 bytes.

Scene opcode `0x78` supplies a level letter. Its `load_map_resource` helper at
load offset `0x034F` reads script variable zero as a difficulty index, selects one byte
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

- The high nibble is a four-direction connection mask: `0x10` is up, `0x20`
  is down, `0x40` is left, and `0x80` is right. It selects one of 16
  connection frames when the map screen is drawn.
- The low nibble selects a location kind. Shipped scripts replace it while
  preserving the high nibble. More precisely, opcode `0x7B` preserves the
  old high nibble and ORs it with the low byte of a script variable; the
  handler does not mask that variable to four bits. All shipped callers use
  only `0x00`, `0x05`, `0x0A`, `0x0B`, and `0x0C`, so they have the intended
  low-nibble effect. Several
  numeric kinds can be correlated with map glyphs and gameplay branches, but
  a complete symbolic enumeration is not yet justified.

Parameters A and B are also manipulated separately by scene commands. The
map screen uses them as text-record selectors for at least location kinds
`0x6` and `0xA`, consistent with the manual's statement that stations and
communication locations show verse references. Other meanings remain open.

## Room encoding and dispatch

A zero connection mask changes the meaning of low kinds `0x1` through `0xF`.
They form five room classes of three entrance orientations each:

```text
room_class     = (location_kind - 1) / 3
entrance_code  = (location_kind - 1) % 3
```

Both operations use integer quotient and remainder. The executable writes
them to script variables 13 and 14. A static table at load offset `0xED7A`
contains the same orientation sequence for neighbor detection.

| Low kinds | Class | Scene | Map letter |
|---|---|---|---|
| `0x1`--`0x3` | Victim | Level-specific `JELO`, `FEAR`, `CULT`, `LAW`, `RICH`, `DENY`, or `NAGE` | V |
| `0x4`--`0x6` | Trap | `ROOM1` | T |
| `0x7`--`0x9` | Prayer | `ROOM2` | P |
| `0xA`--`0xC` | Communications | `ROOM3` | C |
| `0xD`--`0xF` | Jump Tunnel | `ROOM4` | J |

The scene-resource identities provide independent confirmation. `ROOM1`
loads `TRAP`, `TRAP2`, and `TRAP3`; `ROOM2` loads `PRAY`; `ROOM3` loads
`COMM`, `COMM2`, and `FACE1`; and `ROOM4` loads `TUNNEL`, `TUNNEL2`, and
`MONST1`. The hall programs dispatch victim class zero to the seven named
victim scenes and patch the final digit of `room1` for the other four
classes. These five classes are also exactly the `T`, `P`, `C`, `J`, and `V`
rooms described by the manual and rendered by the map screen.

| Kind within each class | Room position from hall | Entrance side |
|---:|---|---|
| First (`1`, `4`, `7`, `A`, `D`) | Right / east | West |
| Second (`2`, `5`, `8`, `B`, `E`) | Left / west | East |
| Third (`3`, `6`, `9`, `C`, `F`) | Above / north | South |

There is no encoding for a room below a hall cell. The executable supports
all 15 class/orientation codes, but the 21 shipped maps use only 14: no map
contains a south-entry Jump Tunnel (`0xF`) with a zero connection mask.

Room codes and connected-hall codes are separate contexts. For example, a
zero-mask `0xA` is a Communications room, while kind `0xA` on a connected
hall cell participates in station and post-encounter behavior. Treating the
low nibble as one global enum would incorrectly merge these states.

The parameters are likewise class-specific. `process_current_map_cell`
copies the current room's parameter A and B to variables 17 and 18. Trap
scripts use parameter A as a study-prompt selector and clear it after the
interaction. When a Trap room is adjacent to a hall, its parameter B becomes
one of three contextual prompt values in variables 23 through 25; a correct
study result clears that byte in the adjacent cell. This identifies both
bytes as mutable encounter state in that class without assuming that they
have the same meaning in Prayer, Communications, or Jump Tunnel rooms.

## Connected hallway features

When the connection mask is nonzero, the low nibble describes the hallway
cell rather than a room. The following meanings have independent script,
resource, or transition evidence:

| Kind | Hall feature | Evidence |
|---:|---|---|
| `0x0` | Empty connected hallway | No feature branch or parameters. |
| `0x1` | Macho Cyber | Selects `COMBAT1`, whose enemy resources are `BIG*`. |
| `0x2` | Armored Cyber | Selects `COMBAT2`, whose enemy resource is `HELMET`. |
| `0x3` | Mantis Cyber | Selects `COMBAT3` and `MANTIS*`. |
| `0x4` | Snake Cyber | Selects `COMBAT4` and `SNAKE*`. |
| `0x5` | Spider Cyber | Selects `COMBAT5` and its internally named `CRAB` art. |
| `0x6` | Leech-covered Scripture station | Selects `COMBAT6` and `GUARD*`; victory restores a station. |
| `0x7` | Zapper Cyber | Selects `COMBAT7` and `ZAP*`; passing beneath it damages faith. |
| `0x9` | Hidden Spider trigger | A successful trigger replaces it with kind `0x5`. |
| `0xA` | Scripture station | Enables Get Verse using parameter A. |
| `0xB` | Cleared encounter | Written by ordinary combat victories. |
| `0xE` | Level exit | Every hall program branches from this kind to its exit sequence. |

The seven hall programs dynamically patch `SML1` to load `SML1` through
`SML7`, and their Confront Cyber actions enter `POWER`. That scene patches
`combat1` from the current kind and returns to `COMBAT1` through `COMBAT7`.
This joins the map kinds, hallway sprites, and combat resources without
depending only on visual resemblance. The manual supplies the player-facing
Cyber names. `CRAB` is the Spider: the separate kind-`0x9` ambush state
conditionally turns into kind `0x5`, matching the documented Spider that can
drop behind Captain Bible.

Kind `0x6` has the strongest transition evidence. Its special combat victory
writes kind `0xA`, copies parameter B to parameter A, and clears parameter B.
The result is a normal Scripture station whose verse selector is now in the
field used by Get Verse. This matches the manual's Leech Cyber, which sits on
top of Scripture stations. Kind `0x7` can be walked under, but its hall branch
applies base faith loss 400; defeating it restores full faith in `COMBAT7`.
Both behaviors match the Zapper description.

Cyber parameter A selects the lie used by the confrontation. The covered
station's parameter B is preserved as the verse selector revealed after the
Leech is defeated. A normal station uses parameter A, sets the corresponding
text-record state, and displays `Verse loaded: &` when Get Verse succeeds.

Connected kinds `0xC`, `0xD`, and `0xF` control visual or environmental hall
states, but their exact player-facing meanings remain unproven. Kind `0x8`
does not occur on a connected cell in any shipped map. The inspector leaves
all four unnamed rather than folding them into the entity table.

The hall action selectors now also have direct labels:

| Selector | Action |
|---|---|
| `.u`, `.d`, `.l`, `.r` | Move Up, Down, Left, or Right |
| `.c` | Confront Cyber |
| `.x` | Unlock |
| `.v` | Get Verse |

The three Unlock targets operate on a locked Trap-room door to the right,
left, or above the hall. They use the adjacent room's parameter B as the
study prompt and clear it after the correct verse is applied. This separates
the door lock from parameter A, which controls the encounter inside the Trap
room.

## Runtime state and scene commands

The loaded resource becomes mutable gameplay state. The following commands
have direct support in their handlers:

| Opcode | Operands | Effect |
|---:|---|---|
| `0x77` | none | Process the current cell, consulting adjacent cells and current state. |
| `0x78` | `B` | Load the selected level's map for the current difficulty. |
| `0x7B` | `H` | Preserve the current high nibble and OR in a script variable's low byte. Shipped values are all valid low-nibble kinds. |
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

Combat programs perform closely matching transitions at their victory
epilogues. `COMBAT1` through `COMBAT5` and `COMBAT7` replace the current low
kind with `0xB`. The guard encounter in `COMBAT6` instead writes kind `0xA`
and copies parameter B to parameter A. Every `RETREAT` action jumps around
these writes into the shared scene-exit path, so retreat preserves the
encounter cell. These scripts prove that `0xB` is a completed/cleared form for
ordinary combat locations and connect the special `0xA` transition to the
guard encounter, although the broader uses of both kinds remain more general
than those labels.

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
tools/inspect_map.py CB/DD1.DAT --map CE --rooms
tools/inspect_map.py CB/DD1.DAT --map CE --hall-features
```

The compact display prints the low location-kind nibble at every coordinate.
`--cells` adds the packed byte, named connection directions, kind, and both
parameters for every nonzero cell. `--rooms` lists decoded room class,
entrance side, and parameters. `--hall-features` lists only connected cells
with proven nonempty features; unresolved environmental kinds remain visible
in `--cells`. Compare a resource with the live grid in a state save with:

```sh
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

The parser requires an exact 768-byte grid and a valid level/difficulty name.
Tests cover all 21 archive members, row-major addressing, connection
directions, the complete encoded room domain, the 14 combinations present in
the corpus, room/victim scene resources, all seven script level selectors,
hall features and combat resources, the hidden-Spider transition, invalid
inputs, and the four saved mutations above.

## Relevant executable functions and data

| Load offset / DS offset | Current name or role |
|---:|---|
| `0x034F` | `load_map_resource` |
| `0x0457` | `normalize_map_cells` |
| `0x075F` | `show_map_screen` |
| `0x0C6C` | `process_current_map_cell` |
| `0xED7A` | 16-byte kind-to-entrance-code lookup table |
| `DS:5B16` | Live 768-byte grid |
| `DS:7290` / `DS:7292` | Current X / Y coordinates |
| `DS:72C4` | Sixteen explored-row bitmaps |
| `DS:76EC` | Checkpoint 768-byte grid |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
