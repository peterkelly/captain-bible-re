# Save-Game Formats

Captain Bible keeps one nine-entry label index and up to ten independent game
states per player prefix. The executable contains no file header, version
number, checksum, or compression for either format. Parsing therefore depends
on the exact file sizes and fixed block order recovered from the read and write
routines.

## Player prefixes and filenames

At startup, `game_main` copies `DDGAMES` into the active prefix. Every command
line argument that does not begin with `-` replaces it using `strcpy`. Both save
routines then construct a filename by copying that prefix to a local buffer and
appending a mutable static suffix initially containing `.SV0`.

| Use | Suffix | Example with default prefix |
|---|---|---|
| Slot-label index | `.SV0` | `DDGAMES.SV0` |
| Normal slots | `.SV1` through `.SV9` | `DDGAMES.SV4` |
| Quick save | `.SVQ` | `DDGAMES.SVQ` |

The save-slot menu writes the selected index plus ASCII `1` into the suffix.
The main event loop writes `Q` before an F10 quick save or F9 quick load and
restores `0` afterward. Thus quick save is a tenth state without an entry in
the nine-label index.

Scene opcode `0x8D` reuses this exact active-prefix plus mutable-suffix
construction. Its sole shipped site is `TITLE.BIN:0x012C`, while the suffix is
`.SV0`, so it probes the player's label index in `rb` mode. Its missing-file
target `0x012F` equals the next command, so the shipped title program enters
`INTRO` whether the open succeeds or fails.

The manual requires an extensionless legal DOS name of at most eight
characters, or permits a complete path such as `d:\players\jimmy`. That is a
user-facing constraint, not executable validation: the parser copies the
argument verbatim and does not check its length, characters, path, or number of
non-option arguments. A player prefix separates only filenames; it is not
stored inside the state.

## `SV0` label index

The index is exactly 243 bytes: nine consecutive 27-byte character buffers.
Each buffer is interpreted as a CP437 C string.

```text
offset = (slot - 1) * 27

+0x00  char label[27]
```

If the file cannot be opened, `read_save_index` initializes all nine buffers
with `strcpy("(EMPTY)")`. Because `strcpy` stops after the first NUL and does
not clear the rest of a 27-byte destination, bytes after that NUL are not part
of the label and can retain old data. The supplied index demonstrates this:
every visible label is `EMPTY`, but eight records have nonzero stale-tail
bytes. The supplied spelling also lacks the parentheses in the executable's
literal, so it was likely prepared or sanitized separately.

The game writes the complete 243-byte array whenever it writes a state. It
does not include slot labels in `.SV1` through `.SV9` themselves.

## State-file layout

`write_save_state` emits 15 `fwrite` calls totaling exactly 2,752 bytes.
`read_save_state` performs corresponding `fread` calls in the same order. All
nine supplied state files have this size.

| File offset | Size | DS offset | Interpretation |
|---:|---:|---:|---|
| `0x000` | 200 | `7BF2` | Checkpoint copy of 100 script-variable words |
| `0x0C8` | 200 | `727A` | Live 100-word script state |
| `0x190` | 66 | `3A66` | Checkpoint copy of descriptor state bytes |
| `0x1D2` | 660 | `B194` | 66 live ten-byte text descriptors |
| `0x466` | 20 | `6EA6` | Checkpoint resource-name C-string buffer |
| `0x47A` | 20 | `B83E` | Live resource-name C-string buffer |
| `0x48E` | 20 | `8938` | Checkpoint extension C-string buffer |
| `0x4A2` | 20 | `AEFE` | Live extension C-string buffer |
| `0x4B6` | 2 | `007C` | Bible translation index |
| `0x4B8` | 2 | `0048` | Music enabled flag |
| `0x4BA` | 2 | `004A` | Sound-effects enabled flag |
| `0x4BC` | 2 | `9FB0` | Checkpoint text-bank character |
| `0x4BE` | 2 | `0080` | Live text-bank character |
| `0x4C0` | 768 | `5B16` | Live 16×16×3-byte world map |
| `0x7C0` | 768 | `76EC` | Checkpoint copy of the world map |
| **Total** | **2,752** | | |

“Checkpoint” is based on executable copy direction, not just similarity. At
new-session initialization and a scene-bytecode checkpoint command,
`copy_live_state_to_save_buffers` copies the live 200-byte block, each
descriptor's byte at offset 4, the two C strings, current text-bank word, and
all 16×16 three-byte table cells into the checkpoint buffers. The inverse
routine restores those fields and reloads the selected text bank. The normal
and quick save paths serialize both versions; they do not take a fresh
checkpoint immediately before writing.

The [script-state chapter](game-state.md) documents the primary block's 100
signed words, embedded 128-bit flag bank, identified variables, powerups,
victim flags, and interpreter commands. The
[world-map chapter](world-maps.md) documents the table's row-major cell
layout, packed connection/location byte, scene commands, exploration state,
and archive-resource correlation. The detailed semantics of the primary state
and several map kinds and parameters remain open.

## Runtime text descriptors

The 660-byte block is 66 records of ten bytes:

| Record offset | Size | Meaning |
|---:|---:|---|
| `+0` | 2 | Far-pointer offset |
| `+2` | 2 | Far-pointer segment |
| `+4` | 1 | Persistent gameplay state byte |
| `+5` | 1 | Text-record selector |
| `+6` | 2 | Offset in the companion `DDL` stream |
| `+8` | 2 | Span in the companion `DDL` stream |

The preceding 66-byte block is exactly the checkpoint copy of byte `+4` from
each descriptor. The text-bank loader reconstructs the process-dependent far
pointers and structural fields after a load while preserving the state byte.
Consequently, pointer values observed on disk are not stable format
identifiers.

All supplied saves select bank `C`. Their first 46 descriptor records match
the recovered NIV bank C index exactly in selector, `DDL` offset, and span;
the remaining 20 structural records are zero. All 66 state bytes are also
zero. This independently connects the save layout to the verse-index format.

## Supplied-save observations

Static comparison of `DDGAMES.SV1` through `DDGAMES.SV9` found:

- `SV6` and `SV8` are byte-for-byte identical.
- 2,477 of the 2,752 offsets are constant across all nine files.
- The live and checkpoint 16×16 maps match within every file. They are all
  zero except in `SV3` and `SV4`, which each have 112 nonzero bytes. Those two
  grids match `CE.MAP` except for four field mutations, including two kind
  changes that exactly follow the executable's map-normalization rule.
- The checkpoint/live resource strings decode as `LOGO`, `LOGO`, `seg`, and
  `seg`. Bytes after their first NUL can be stale and are not semantic.
- Translation is 1, music and effects are enabled, and both bank values are
  ASCII `C` in every file.
- Each primary block pair differs at byte 56; `SV9` additionally differs at
  byte 54. This is evidence that both serialized blocks matter, not evidence
  that either copy is damaged.
- Descriptor far-pointer segments differ in `SV9`, consistent with addresses
  being reconstructed runtime state rather than portable identifiers.

Pairwise comparisons alone do not yet assign gameplay meaning to the 275
offsets that vary across this small corpus. Controlled saves after specific
game actions are needed for that stage.

## Error behavior

The state reader returns failure if the requested state file cannot be opened.
Once open succeeds, it issues all 15 reads but does not check their individual
return counts before refreshing audio/text state and returning success. The
format has no integrity marker, so a truncated or modified file may partially
overwrite memory rather than producing a clean format error. The host-side
inspector is intentionally stricter.

## Inspection tool

`tools/inspect_save.py` selects the index or state parser by exact size,
decodes C-string buffers, reports snapshot differences and settings, and can
list live text descriptors:

```sh
tools/inspect_save.py CB/DDGAMES.SV0
tools/inspect_save.py CB/DDGAMES.SV3 --descriptors
tools/inspect_save.py CB/DDGAMES.SV9 --variables
```

The parser rejects every size other than 243 or 2,752 bytes. Its tests cover
all ten supplied files, stale label tails, exact snapshot relationships,
scalar meanings, script variables and flags, descriptor state copies, and the
full NIV bank C structural match.

## Relevant executable functions

| Load offset | Current name | Role |
|---:|---|---|
| `0x2B6F` | `choose_save_slot` | Build the nine-label menu and change `.SV0` to the chosen slot suffix. |
| `0x7D8E` | `copy_live_state_to_save_buffers` | Refresh checkpoint fields from live state. |
| `0x7E41` | `copy_save_buffers_to_live_state` | Restore checkpoint fields and reload text. |
| `0x7F01` | `write_save_index` | Write nine 27-byte label buffers. |
| `0x7F58` | `read_save_index` | Read the index or initialize `(EMPTY)` labels. |
| `0x7FD7` | `write_save_state` | Write the index and the 15 state blocks. |
| `0x815A` | `initialize_empty_save_slot` | Replace an empty label with the `Game 1` through `Game 9` default. |
| `0x81A5` | `save_selected_slot` | Initialize the selected label, then write the state. |
| `0x81AC` | `read_save_state` | Read the index and all 15 state blocks. |
