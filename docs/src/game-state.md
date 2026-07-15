# Script State and Progression

## Primary-state structure

The 200-byte live block at `DS:727A` is the scene interpreter's shared state.
New-game initialization writes 100 zero words with `rep stosw`, and the save
system copies exactly those 100 words to and from the checkpoint block at
`DS:7BF2`. Values are signed 16-bit integers where arithmetic or comparison
requires a sign.

BIN operands do not store variable ordinals. They store even byte offsets
from `DS:727A`; the interpreter shifts an offset right once before indexing
the word array. Thus operand `0x002A` identifies variable 21:

```text
address = DS:727A + encoded_offset
index   = encoded_offset / 2
```

Across all 64 recovered BIN code regions, the core variable instructions
reference 39 of the 100 slots. Every one of their encoded operands is even
and below 200. Many high-numbered slots are scene-local temporaries rather
than persistent player attributes.

## Identified variables

| Index | Byte offset | DS address | Current meaning | Evidence |
|---:|---:|---:|---|---|
| 0 | `0x00` | `727A` | Difficulty: 0 Easy, 1 Normal, 2 Difficult | Difficulty input writes these values; map loading indexes `END`; faith damage branches on the same values. |
| 11 | `0x16` | `7290` | Current map X | Used in every `3*x` cell calculation and exploration-bit update. |
| 12 | `0x18` | `7292` | Current map Y | Used in every `48*y` cell calculation and as the exploration-row index. |
| 16 | `0x20` | `729A` | Current map level letter | `load_map_resource` compares and caches its level argument here. |
| 17 | `0x22` | `729C` | Current cell parameter A | `process_current_map_cell` copies cell byte `+1` here. |
| 18 | `0x24` | `729E` | Current cell parameter B | `process_current_map_cell` copies cell byte `+2` here. |
| 21 | `0x2A` | `72A4` | Faith in hundredths of a percent | Initialized and clamped to 10,000; the F3 display divides by 100. |

The first gameplay entry in `FIRST.BIN` demonstrates the interface directly:
it stores X=0 in offset `0x16`, Y=6 in offset `0x18`, and faith=10,000 in
offset `0x2A` before processing the current map cell.

## Variable bytecode

The core instruction family is now recovered. In this table, `var` operands
are encoded byte offsets, `value` is a signed immediate where relevant, and
`target` is an absolute BIN file offset.

| Opcode | Operands | Effect |
|---:|---|---|
| `0x1E` | `source, destination` | Copy a variable. |
| `0x1F` | `value, destination` | Store an immediate value. |
| `0x20` / `0x21` | `var, target` | Jump if zero / nonzero. |
| `0x22` / `0x24` | `left, right, target` | Jump if two variables are equal / unequal. |
| `0x23` / `0x25` | `var, value, target` | Jump if a variable equals / does not equal an immediate. |
| `0x26` / `0x28` | `left, right, target` | Signed jump if `left` is greater than / less than `right`. |
| `0x27` / `0x29` | `var, value, target` | Signed jump if a variable is greater than / less than an immediate. |
| `0x2A` / `0x2B` | `source-or-value, destination` | Add a variable / immediate to the destination. |
| `0x2C` / `0x2D` | `source-or-value, destination` | Subtract a variable / immediate from the destination. |
| `0x2E` / `0x2F` | `source-or-value, destination` | Signed multiply the destination by a variable / immediate. |
| `0x30` / `0x31` | `source-or-value, destination` | Signed divide the destination by a variable / immediate. |
| `0x32` / `0x33` | `var` | Increment / decrement. |
| `0x8F` / `0x90` | `source-or-value, destination` | Bitwise-AND the destination with a variable / immediate. |

The disassembler annotates known operands with both forms, for example
`var[21:faith]@0x002a`. This also prevents immediate values and jump targets
from being mistaken for variable numbers.

## Boolean state flags

Variables 3 through 10, at `DS:7280..728F`, are also treated as a 128-bit
flag bank. Identifier `n` selects word `n >> 4` and mask
`1 << (n & 15)`. Dedicated helpers test, set, and clear one identifier using
mask and inverted-mask tables in the executable.

| Opcode | Operands | Effect |
|---:|---|---|
| `0x73` | `flag, target` | Jump if the flag is clear. |
| `0x74` | `flag, target` | Jump if the flag is set. |
| `0x75` | `flag` | Clear the flag. |
| `0x76` | `flag` | Set the flag. |

The scene corpus uses 78 distinct identifiers through `0x55`. They mix
temporary navigation/action state with durable progression. When the current
map cell is processed, the executable clears the first three flag words
(`0x00..0x2F`) and rebuilds movement and action availability from the cell
and its neighbors. Flags at `0x30` and above survive that operation.

Five durable identifiers map exactly to the F4 through F8 status icons:

| Flag | Capability |
|---:|---|
| `0x30` | Sword |
| `0x31` | Shield |
| `0x32` | No Trap |
| `0x33` | Candle |
| `0x34` | Flight |

The seven victim scenes each set a distinct rescue flag at successful
progression points:

| Flag | Scene / victim identifier |
|---:|---|
| `0x3A` | `JELO` |
| `0x3B` | `FEAR` |
| `0x3C` | `CULT` |
| `0x3D` | `LAW` |
| `0x3E` | `RICH` |
| `0x3F` | `DENY` |
| `0x40` | `NAGE` |

`GANTRY.BIN` tests those seven flags and mirrors the set members into
`0x42..0x48` before the Unibot sequence. The bytecode proves the one-to-one
transition, although the later flags' most precise gameplay label remains
open.

## Faith

Faith is variable 21 and uses a 0–10,000 scale, so one displayed percentage
point is 100 internal units. The status renderer clamps values above 10,000
and below zero before selecting meter artwork. The F3 detail screen divides
by 100 and displays two decimal digits, with a separate full-faith string for
10,000.

Opcode `0x81` passes an immediate loss to `reduce_faith` at `0x3979`:

- Easy divides the loss by two.
- Normal applies it unchanged.
- Difficult multiplies it by four.
- No-combat mode suppresses the subtraction.

This directly supports the manual's statement that Easy mode loses faith
less readily and connects the installation no-combat option to the same
damage path.

## Text-record progression state

Each loaded text descriptor has a persistent byte at record offset `+4`.
The save chapter describes its compact checkpoint copy and serialized live
records. The bytecode interpreter addresses these bytes by the descriptor's
one-byte selector:

| Opcode | Operands | Effect |
|---:|---|---|
| `0x36` | `selector` | Set the matching record's state byte and select it. |
| `0x37` | `selector` | Clear the matching record's state byte. |
| `0x38` | `selector, target` | Jump if the matching state byte is set. |
| `0x39` | `selector, target` | Jump if the matching state byte is clear. |
| `0x88` | none | Clear all 66 loaded state bytes. |

This is the persistent bridge between dialogue/study records and scene
control flow. The exact user-facing meaning varies by record: the same
mechanism can represent an obtained verse, completed interaction, or another
text-related condition.

## Save inspection

Show named, nonzero, or checkpoint-different variables and decode the flag
bank with:

```sh
tools/inspect_save.py CB/DDGAMES.SV9 --variables
```

The supplied saves have no active boolean flags. Both copies keep variable
16 at -1. Their live copies vary at general-purpose variable 28, and `SV9`
also has variable 27 set to 5; static evidence does not justify assigning
gameplay meanings to those temporary slots.

## Relevant executable functions

| Load offset | Current name |
|---:|---|
| `0x1191` | `initialize_script_state` |
| `0x3979` | `reduce_faith` |
| `0x43F5` | `test_state_flag` |
| `0x4413` | `set_state_flag` |
| `0x4433` | `clear_state_flag` |
| `0x5B24` | `get_text_record_state` |
| `0x5B76` | `set_text_record_state` |
| `0x5BBF` | `clear_text_record_state` |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
