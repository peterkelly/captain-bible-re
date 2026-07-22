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
content. The parameter B of any correctly oriented adjacent room is copied to
variable 23 for right, 24 for left, or 25 for above. Trap scripts use these
values as locked-door prompts, and a correct answer clears that byte. Other
classes MUST retain their parameters even when a new implementation does not
attach a generic name to them.

## Current-cell derivation

The current coordinates are variables 11 and 12. Processing starts by copying
the current A and B to variables 17 and 18, clearing variables 23 through 25,
copying the current low kind to variable 13, and clearing flags `00` through
`2F`.

For a zero-connection cell, it sets flag `10`, subtracts one from variable
13, and stores the signed quotient and remainder after division by three in
variables 13 and 14. This is the room class and entrance derivation above.
The all-zero cell consequently produces class `0` and entrance `-1`, matching
the original signed division even though shipped scene flow does not use that
value as a room.

For a connected hall cell, the following flags describe the current cell and
its immediately adjacent, correctly oriented rooms:

| Flag | Meaning |
|---:|---|
| `00` | Current cell connects down. |
| `01` | Current cell connects right. |
| `02` | A west-entrance room is immediately right. |
| `03` | Current cell connects left. |
| `04` | An east-entrance room is immediately left. |
| `05` | Current cell connects up. |
| `11` | A south-entrance room is immediately above. |
| `16`–`18` | Parameter B is nonzero for the rooms at right, left, and above. |
| `1F`–`21` | The rooms at right, left, and above are Trap-class rooms. |

The three adjacent rooms' B values, regardless of class, become variables 23,
24, and 25. A room is recognized only when its complete packed byte is below
`10`; connected cells with the same low kind are not rooms.

When flag `05` is clear, processing stops after the immediate context. When it
is set, the executable builds a forward perspective by scanning decreasing Y.
The scan is clipped at the top map boundary:

| Row relative to current | Direct cell | Right-side room | Left-side room |
|---:|---|---|---|
| `-1` | low kind to variable 14; connections right/left/up set `06`/`08`/`0A` | presence `07`, nonzero B `19` | presence `09`, nonzero B `1A` |
| `-2` | low kind to variable 15; connections right/left/up set `0B`/`0D`/`0F`; south-entrance room presence `12`, nonzero B `1B` | presence `0C`, nonzero B `1C` | presence `0E`, nonzero B `1D` |
| `-3` | south-entrance room presence `13`, nonzero B `1E` | not scanned | not scanned |

Variables 14 and 15 retain their prior values if their respective forward
rows are not scanned. The perspective flags do not require a continuous chain
of up-connection bits beyond the current cell; the current up bit alone gates
the complete bounded scan.

An engine MUST perform these derivations before dispatching the matching hall
or room scene.

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

For map levels other than `E`, map rendering visits all rows and columns in
row-major order. At `(x,y)`, the exploration bit chooses a one-based symbol
base of 4 when set and 25 when clear. A connected cell composites one-based
frame `base + (connections >> 4)`. A nonzero zero-mask room instead
composites `base + 16 + ((kind - 1) % 3)` for its entrance and, when explored,
one-based frame `47 + ((kind - 1) / 3)` for its class letter. These one-based
numbers are the DOS drawing-call convention; subtract one to index
`MAP.ART`.

Connected kinds `6` and `A` add a Scripture-state marker. Kind `A` takes its
text selector from parameter A; kind `6` takes it from parameter B. If the
matching text descriptor has nonzero state, one-based frame 4 is composited;
otherwise one-based frame 60 is used. A missing or zero selector counts as
not obtained.

Level `E` displays only source columns 8 through 15 at output columns 0
through 7 and tests exploration bits 8 through 15. It omits the frame-62
legend. Cells whose complete packed byte has remainder zero modulo three add
one-based frame 61 when explored or 62 when unexplored. For cells with
connection nibble `F`, kinds `D`, `F`, and all other kinds respectively use
adjustments 20, 21, and 19 added to the explored/unexplored base. Kinds `6`
and `A` then apply the same Scripture-state marker rule, except that their
parameter B or A selector is read from the corresponding cell in source
columns 0 through 7. This split-half lookup is intentional. The special
branch MUST not be approximated by cropping the ordinary 16-column rendering.

The runtime also has a separate opaque 16×16 byte table addressed as
`16 * y + x`. Opcode `8E` copies bits 0 through 4 of the current entry to
state flags `23` through `27`. Opcode `91` divides its zero-extended value by
an immediate and stores the signed remainder. This table is not the packed
three-byte `MAP` grid and MUST NOT be conflated with its cell byte zero. Its
broader gameplay label is unspecified; scene code can still observe it through
those two commands.

## Progression normalization

When a scene invokes the normalization command, the engine scans the complete
grid in column-major traversal order. Each cell is transformed independently:

| Cell condition | Result |
|---|---|
| Connection nibble is zero | Clear parameter B; leave packed kind and A unchanged. |
| Connected kind is `6` | Change kind to `A`, copy B to A, and clear B. |
| Connected kind is `1` through `9` other than `6` | Change kind to `B`; retain A and B. |
| Any other connected kind | Leave all three bytes unchanged. |

Every kind replacement preserves the connection nibble. The operation does
not consult a separate progression flag: scene programs remain authoritative
about when it runs. Implementations MUST NOT narrow these transformations to
only the current cell or to only a presumed encounter subtype.
