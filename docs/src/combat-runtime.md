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

| Program | Manual identity | Bytes | Commands | Animation sequences | Steps | Actions | Enemy ART bases |
|---|---|---:|---:|---:|---:|---:|---|
| `COMBAT1.BIN` | Macho | 3,300 | 625 | 33 | 182 | 4 | `BIG`, `BIG2`, `BIG3`, `BIG4` |
| `COMBAT2.BIN` | Armored | 7,230 | 973 | 30 | 594 | 4 | `HELMET` |
| `COMBAT3.BIN` | Mantis | 4,381 | 782 | 38 | 260 | 4 | `MANTIS`, `MANTIS2`, `MANTIS3` |
| `COMBAT4.BIN` | Snake | 7,434 | 1,073 | 29 | 581 | 4 | `SNAKE`, `SNAKE2` |
| `COMBAT5.BIN` | Spider | 6,501 | 919 | 34 | 523 | 4 | `CRAB` |
| `COMBAT6.BIN` | Leech | 2,314 | 351 | 15 | 163 | 3 | `GUARD`, `GUARD2` |
| `COMBAT7.BIN` | Zapper | 4,289 | 720 | 35 | 293 | 4 | `ZAP`, `ZAP2`, `SPRK` |
| **Total** | | **35,449** | **5,443** | **214** | **2,596** | **27** | |

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

The world-map chapter documents the independent hall-kind and transition
evidence for these manual identities. `COMBAT6.BIN` is the only program
without a `DEFEND` target. For example,
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

## Action and outcome control flow

The four actions are entry points into the same encounter program, not
numeric combat operations. `ATTACK` disables the current choices and runs an
enemy-phase-specific animation path. `DEFEND` changes the available timing
window; when Shield flag `0x31` is set, the scripts leave the attack option
available longer. `COMBAT` uses opcode `0x82` and branches on Sword flag
`0x30` and Shield flag `0x31` to choose successful, harmless, and
faith-damaging sequences. The exact visual phase that makes each enemy
vulnerable remains encoded in scene-local animation and counter variables.

Opcode `0x81` contains the base loss used on Normal difficulty. The seven
programs contain these loss sites:

| Program | Base faith-loss immediates | Victory map mutation | Retreat target and exit entry |
|---|---|---|---|
| `COMBAT1` | 533, 2,011 | kind `0xB` | `0x0C38 -> 0x0C9D` |
| `COMBAT2` | 107, 102, 502 | kind `0xB` | `0x1BAC -> 0x1BF6` |
| `COMBAT3` | 1,037, 531, 2,011, 1,703 | kind `0xB` | `0x10C3 -> 0x10D6` |
| `COMBAT4` | 596, 1,005 | kind `0xB` | `0x1C9D -> 0x1CC3` |
| `COMBAT5` | 213, 2,009 | kind `0xB` | `0x18F7 -> 0x1902` |
| `COMBAT6` | none | kind `0xA`; copy parameter B to A | `0x087B -> 0x087E` |
| `COMBAT7` | 233, 207 | kind `0xB`; restore faith | `0x1053 -> 0x105E` |

Each Retreat target is itself an unconditional jump to the common exit
entry. It therefore skips the victory-only map mutation. The table records
all static loss sites rather than claiming that every site executes in one
fight; branches choose among them. Easy halves each immediate, Difficult
multiplies it by four, and installation no-combat mode suppresses it.

`COMBAT7` contains the manual's exceptional Zapper reward directly. Its
victory subroutine alternates faith between 1 and 10,000 five times, producing
a visible meter flash and ending at full faith. This happens before kind
`0xB` is written to the defeated encounter's map cell.

## Shared encounter epilogue

Six programs set state flag `0x38` after defining their action table and
clear it in the common exit. The Game Options input routine tests the same
flag and disables the Automatic Combat menu target while it is set. Flag
`0x38` is therefore the combat-active lock, while flag `0x37` stores the
Automatic Combat setting itself. `COMBAT6` is exceptional: it has no
`DEFEND` target, never changes flag `0x38`, contains no faith-loss opcode,
and produces a different map transition. Its internally named `GUARD`
encounter is the Leech Cyber covering a Scripture station: victory reveals
the station and transfers its saved verse selector into the active field.

After victory or retreat, the programs clear current-cell parameter A and
select a hall scene. Variable 67 chooses the literal `GHALB` or `GHALS`
variants for two special cases. Otherwise opcode `0x7A` patches the first
byte of the inline `CHAL` string from variable 16, the current map-level
letter, yielding the appropriate `AHAL` through `GHAL` resource name.
Opcode `0x7E` starts a palette blackout immediately before these scene
changes.

All seven combat programs also expose a separate `POWER` scene-change entry.
`POWER.BIN` is the in-combat study/power interface, not a game-over scene. On
a successful selection it copies the current combat number, adds ASCII
`'0'`, patches the digit in the inline name `combat1`, and changes back to
that encounter. The caller path into this special entry has not yet been
fully recovered.

## Inspection

Inspect animation definitions and action targets with:

```sh
tools/inspect_bin.py \
  build/dd1/all/337_COMBAT7.BIN --animations --actions
```

The summaries follow linear definition order. Calls and branches can skip or
repeat definitions, and enable/disable commands determine which action
targets are live at a particular moment.

## Live COMBAT1 table validation

A visible, silent QEMU capture now validates the three runtime table families.
The route was controlled rather than a natural walk to an encounter: a genuine
hall quick-save contained snapshot/live scene names `MENU`/`CHAL`, and
`tools/patch_save_scene.py` changed only both 20-byte scene-name fields to
`COMBAT1`. The modified state round-tripped through the FAT image byte for
byte. Loading it with F9 produced the Macho combat screen, and the A key
started a visible green attack effect.

The first dump caught scene initialization between visible redraws, with
counts 0 and 1, so it is not used for table comparison. A second one-MiB
physical dump after the attack input had SHA-256
`becc98dd2eba0bad502f1bf6b7aef4ef2638fa48d0e0e62688ad879085bc1654`.
QEMU reported `DS=14E1`; `tools/inspect_runtime_tables.py` therefore read the
same data offsets documented above at physical base `0x14E10`.

The stable capture contains four action records and 33 animation records. All
four action target/X/Y/selector-offset tuples match the static COMBAT1
definitions. ATTACK, DEFEND, and RETREAT are active; the automatic COMBAT
target is present but inactive. Every animation record's first-step offset and
interval matches its corresponding BIN definition, 33 of 33. Current-step,
link, state, render-slot, and timing values are retained as live values rather
than forced to equal their initial definitions.

The first ten 16-byte scheduler records were also saved. Current slot is zero;
slots 0, 5, 7, and 8 have active byte 1. Slot 0 has cursor `0x0C35` and signed
delay -824 at the sampled instant. The remaining opaque bytes are emitted in
hex so later field naming will not lose evidence. The exact comparison command
is:

```sh
tools/inspect_runtime_tables.py \
  build/formal-captures/combat-after-a-memory.bin \
  --data-segment 0x14e1 \
  --bin build/dd1/all/343_COMBAT1.BIN
```

This validates the table addresses, strides, counts, and statically comparable
fields. It does not prove a natural map-to-encounter transition, nor does the
controlled state preserve a normal combat outcome: the patched checkpoint had
zero snapshot faith, and the run subsequently reached the “Don't Give Up!”
screen. Those provenance limits are intentional and recorded rather than
being generalized to ordinary play.

## Remaining questions

- Name the final two bytes of each animation slot and every mode's exact
  transition rule.
- Separate the opcode-`0x02` interactive/display record family from the true
  BIN scheduler slots field by field.
- Correlate every randomized branch with the exact enemy phase and rendered
  successful, harmless, or damaging sequence.
