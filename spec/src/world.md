# World model and exploration

## Levels and maps

The adventure contains seven levels, identified `A` through `G`, and three
difficulty variants: `E`asy, `N`ormal, and `D`ifficult. A map member is named
by level letter plus difficulty code and `.MAP`, for example `CE.MAP`.

Each map is exactly 768 bytes: a headerless, row-major 16×16 grid of
three-byte mutable cells.

```text
cell_offset = 3 * (16 * y + x)

+0  packed connections and location kind
+1  parameter A
+2  parameter B
```

Coordinates are 0 through 15. In byte zero, the high nibble is a connection
mask: `10` up, `20` down, `40` left, `80` right. The low nibble is interpreted
according to whether the connection mask is zero.

The loaded grid is live game state, not a read-only map asset. Encounters,
unlocked doors, exposed stations, and cleared locations modify it. Both live
and checkpoint copies are persisted.

## Hall cells

When at least one connection bit is set, known low-nibble kinds are:

| Kind | Feature and behavior |
|---:|---|
| `0` | Empty connected hall. |
| `1` | Macho Cyber; enters combat 1. |
| `2` | Armored Cyber; enters combat 2. |
| `3` | Mantis Cyber; enters combat 3. |
| `4` | Snake Cyber; enters combat 4. |
| `5` | Spider Cyber; enters combat 5. |
| `6` | Leech-covered Scripture station; enters combat 6. |
| `7` | Zapper Cyber; enters combat 7 and can drain faith while passed. |
| `9` | Hidden Spider trigger; a successful trigger changes it to kind `5`. |
| `A` | Available Scripture station; parameter A selects its verse. |
| `B` | Cleared encounter. |
| `E` | Level exit. |

Kind `8` is absent from shipped connected cells. Kinds `C`, `D`, and `F`
are used as contextual environmental or visual states but have no separately
required player-facing identity. A compatible engine MUST retain and pass
them to scene logic without remapping them.

For Cyber cells, parameter A selects the lie or study content. For kind `6`,
parameter B is the verse exposed by victory. Defeating combat 1–5 or 7 sets
the kind to `B`. Defeating combat 6 sets kind `A`, copies parameter B into A,
and clears B. Retreat leaves the cell unchanged.

## Side rooms

With a zero connection mask, kinds 1 through 15 encode five room classes and
three entrance orientations:

```text
room_class    = (kind - 1) / 3
entrance_code = (kind - 1) % 3
```

| Kinds | Class | Purpose |
|---|---|---|
| `1`–`3` | Victim | A level-specific captive and conversation. |
| `4`–`6` | Trap | A temptation/trap requiring study interaction. |
| `7`–`9` | Prayer | Prayer and spiritual instruction. |
| `A`–`C` | Communications | Communications and study content. |
| `D`–`F` | Jump Tunnel | Alternate movement challenge. |

Within every row, the first kind is a room east of the hall with a west-side
entrance, the second is west with an east-side entrance, and the third is
north with a south-side entrance. There is no room-below encoding. The seven
victim scenes are `JELO`, `FEAR`, `CULT`, `LAW`, `RICH`, `DENY`, and `NAGE`.

Parameters are class-specific mutable state. Current-cell processing copies A
and B into VM variables 17 and 18. In a Trap, A selects encounter study
content. The parameter B of an adjacent Trap represents its locked-door
prompt and is made available as variable 23 for right, 24 for left, or 25 for
above; a correct answer clears that byte. Other classes MUST retain their
parameters even when a new implementation does not attach a generic name to
them.

## Current-cell derivation

The current coordinates are variables 11 and 12. Processing a cell sets
variable 13 to the hall kind or room class, variable 14 to the room entrance
code or relevant neighboring kind, and variables 17, 18, 23, 24, and 25 as
described above. It also rebuilds contextual movement/action flags. An engine
MUST perform these derivations before dispatching the matching hall or room
scene.

Map-cell kind mutation preserves the high connection nibble. Opcode `7B`
technically ORs the complete low byte of its source variable without masking;
the shipped programs supply only `00`, `05`, `0A`, `0B`, or `0C`. Full VM
compatibility MUST preserve this unmasked behavior.

## Exploration map

Exploration state is sixteen 16-bit rows. Visiting `(x,y)` performs:

```text
explored[y] |= 1 << x
```

The F2 map displays the 16×16 layout, connections, known room letters
`V`, `T`, `P`, `C`, and `J`, and stations or communications references.
Explored areas are gold and unexplored areas gray. The view MUST not itself
mark new cells explored.

The runtime also has a separate opaque 16×16 byte table addressed as
`16 * y + x`. Opcode `8E` copies bits 0 through 4 of the current entry to
state flags `23` through `27`. Opcode `91` divides its zero-extended value by
an immediate and stores the signed remainder. This table is not the packed
three-byte `MAP` grid and MUST NOT be conflated with its cell byte zero. Its
broader gameplay label is unspecified; scene code can still observe it through
those two commands.

## Progression normalization

After loading or restoring a map, the engine runs the scene-requested
normalization command. It applies progression-dependent cell changes,
including conversion of a resolved covered station from kind `6` to `A`
with B moved to A, and conversion of resolved encounter kinds 1 through 9 to
`B` where the corresponding progression state requires it. Scene programs
remain authoritative about when normalization runs.
