# Combat Runtime

## Architecture

Combat is implemented by seven scene programs, `COMBAT1.BIN` through
`COMBAT7.BIN`. The executable supplies generic animation, selectable-action,
thread, random-number, sound, and faith-loss operations; each BIN program
combines those primitives into an encounter. This is a script-driven system,
not a conventional enemy object with a health field in the ten-byte display
record.

Every combat program loads `COMBTAGS.ART`, `COMBAT.ART`, and one or more
enemy-specific ART resources:

| Program | Bytes | Commands | Animation sequences | Steps | Actions | Enemy ART bases |
|---|---:|---:|---:|---:|---:|---|
| `COMBAT1.BIN` | 3,300 | 625 | 33 | 182 | 4 | `BIG`, `BIG2`, `BIG3`, `BIG4` |
| `COMBAT2.BIN` | 7,230 | 973 | 30 | 594 | 4 | `HELMET` |
| `COMBAT3.BIN` | 4,381 | 782 | 38 | 260 | 4 | `MANTIS`, `MANTIS2`, `MANTIS3` |
| `COMBAT4.BIN` | 7,434 | 1,073 | 29 | 581 | 4 | `SNAKE`, `SNAKE2` |
| `COMBAT5.BIN` | 6,501 | 919 | 34 | 523 | 4 | `CRAB` |
| `COMBAT6.BIN` | 2,314 | 351 | 15 | 163 | 3 | `GUARD`, `GUARD2` |
| `COMBAT7.BIN` | 4,289 | 720 | 35 | 293 | 4 | `ZAP`, `ZAP2`, `SPRK` |
| **Total** | **35,449** | **5,443** | **214** | **2,596** | **27** | |

The programs branch on script variables and progression flags, including the
Sword and Shield power flags `0x30` and `0x31`. They use opcode `0x81` to
reduce the player's faith. Encounter outcomes, enemy phases, and exits are
therefore expressed as script control flow and persistent state changes.
No separate enemy-health structure has yet been found.

## Animation definitions

Opcode `0x06` begins an animation definition. Its word operand becomes the
sequence interval. The immediately following opcode-`0x07` commands are the
steps retained in the BIN stream; executing `0x07` merely advances over its
nine-byte payload.

Each step has this layout:

| Payload offset | Size | Meaning |
|---:|---:|---|
| `+0` | 1 | One-based ART frame. |
| `+1` | 1 | Loaded ART slot. |
| `+2` | 2 | Signed X coordinate. |
| `+4` | 2 | Signed Y coordinate. |
| `+6` | 2 | 8.8 scale; `0x0100` is native size. |
| `+8` | 1 | Render flags. |

The runtime animation table starts at `DS:6EBA`, has a 12-byte stride, and
is counted by the word at `DS:B114`. The recovered fields are:

| Record offset | Size | Meaning |
|---:|---:|---|
| `+0` | 2 | BIN offset of the first step. |
| `+2` | 2 | BIN offset of the current step. |
| `+4` | 2 | Sequence interval/countdown input. |
| `+6` | 2 | Linked or parent animation index. |
| `+8` | 1 | Animation mode/state. |
| `+9` | 1 | Associated render/display slot. |
| `+10` | 2 | Internal timing state; exact split remains unnamed. |

Opcode `0x08` starts a slot with no parent, while `0x5F` starts a slot with an
explicit link. Opcode `0x09` stops a slot and releases its render slot.
Opcode `0x3F` suspends the current BIN thread while an animation remains
active, except for the two nonblocking modes 5 and 6. Opcode `0x80` branches
when a chosen animation's state byte is nonzero.

The executable routines at `0x3B9B`, `0x3D08`, `0x3DA8`, `0x3F59`, and
`0x3FDF` resolve linked transforms, render one slot, update all slots, start a
slot, and stop a slot respectively. The updater advances through the BIN
steps in ten-byte command units and implements animation modes 1 through 10.

## Selectable action targets

Opcode `0x3A` appends a ten-byte action target to the table at `DS:480E`; the
word at `DS:6EA4` is its count:

| Record offset | Size | Meaning |
|---:|---:|---|
| `+0` | 2 | Absolute target offset in the current BIN program. |
| `+2` | 2 | Screen X coordinate. |
| `+4` | 2 | Screen Y coordinate. |
| `+6` | 2 | Offset of a selector string in the current BIN. |
| `+8` | 1 | Active flag. |
| `+9` | 1 | Reserved/padding. |

Opcode `0x3B` enables one record and `0x3C` disables it. Opcode `0x41`
enables action selection globally; `0x42` disables it and clears pending
selection state. The overlay routine at `0x6A23` scans active targets,
compares their coordinates with the pointer, decodes the selector string,
and draws the corresponding label. The keyboard path at `0x8558` searches
the same table. A selected record is dispatched through the BIN-thread start
routine at `0x7A5C`.

`COMBTAGS.ART` contains four label frames. Rendering all four with
`019_ZAP.PAL` identifies the selector mapping independently of the scripts:

| Selector | Frame label | Definitions in seven combat programs |
|---|---|---:|
| `.11` | `ATTACK` | 7 |
| `.12` | `DEFEND` | 6 |
| `.13` | `RETREAT` | 7 |
| `.14` | `COMBAT` | 7 |

`COMBAT6.BIN` is the only program without a `DEFEND` target. For example,
`COMBAT7.BIN` defines:

| Source | Target | X | Y | Action |
|---:|---:|---:|---:|---|
| `0x0C06` | `0x0EC8` | 151 | 61 | `ATTACK` |
| `0x0C11` | `0x0EAB` | 136 | 153 | `DEFEND` |
| `0x0C1C` | `0x1053` | 15 | 167 | `RETREAT` |
| `0x0C27` | `0x0FA7` | 157 | 62 | `COMBAT` |

These coordinates are screen hotspots rather than enemy bounding boxes.
The same generic table can represent selectable actions elsewhere, so its
runtime name is deliberately broader than “combat buttons.”

## BIN threads and synchronization

The command-stream scheduler uses 16-byte slots beginning at `DS:8D44`; the
current slot index is at `DS:7DB4`. The fields proven so far include the BIN
cursor at `+0`, a delay/timer at `+0x0C`, an active byte at `+0x0E`, and a
status byte at `+0x0F`.

Opcode `0x3E` activates a selected slot at an absolute BIN target and runs it
immediately. Opcode `0x61` clears a slot's active byte. This is the mechanism
used after an action target has supplied a branch destination. It is distinct
from the separate 16-byte record family created by opcode `0x02`, whose type
`0x02` entries also participate in the scene display/update list.

Opcode `0x59` waits for a digital effect to finish. When the digital driver
is unavailable, the same handler decrements a simulated 100-tick duration,
preserving script timing. Opcode `0x82` computes a runtime pseudorandom value
modulo its first operand and stores the remainder in the script variable
selected by its second operand. Together with animation waits, these
operations let the combat scripts sequence visual attacks, sounds, and
randomized branches without embedding those policies in an enemy structure.

## Inspection

Inspect animation definitions and action targets with:

```sh
tools/inspect_bin.py \
  build/dd1/all/358_COMBAT7.BIN --animations --actions
```

The summaries follow linear definition order. Calls and branches can skip or
repeat definitions, and enable/disable commands determine which action
targets are live at a particular moment.

## Dynamic-analysis boundary

The static model is supported by handler call flow, table strides, all seven
combat programs, and rendered `COMBTAGS` labels. An attempted visible,
silent QEMU navigation to the first encounter did not yield a usable combat
memory capture: automated input reached a black transition screen while the
CPU was in a loaded sound-driver segment. QEMU was stopped cleanly, and no
live-table claim is based on that run. Dynamic validation of the animation,
action-target, and thread tables remains open.

## Remaining questions

- Name the final two bytes of each animation slot and every mode's exact
  transition rule.
- Separate the opcode-`0x02` interactive/display record family from the true
  BIN scheduler slots field by field.
- Correlate each combat script's randomized branches with enemy phases,
  successful attacks, defense, retreat, and encounter completion.
- Capture the three runtime tables during a live encounter and compare them
  byte for byte with the static definitions.
