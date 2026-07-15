# Static Analysis Findings

## Working with the disassembly

Generate the unpacked executable and apply the current symbol map:

```sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE
rizin -b 16 -i analysis/cb.rz build/analysis/CB_UNPACKED.EXE
```

Rizin's first recursive pass identifies approximately 340 candidate functions.
Several large candidates cross jump tables or data and are false merges, so
the names below are limited to routines whose implementation and call sites
provide direct evidence.

## Program entry and `main`

The real entry at `0xCB5C` is Microsoft C startup code. It checks for DOS 2.0,
resizes the process allocation, clears BSS, constructs `argc`, `argv`, and
`envp`, and calls the near function at `0x8A82` with all three values. That
function is therefore `main`.

The high-level static flow is:

1. If `argv[0]` has a drive-qualified path, `0x8A09` changes to that drive and
   directory.
2. `main` initializes resource-name buffers including `LOGO`, `seg`, and
   `DDGAMES`, then parses all remaining arguments.
3. `0x3363` verifies VGA, reads `SOUND.5`, loads the configured `SOUND.1`
   through `SOUND.4` drivers, opens `DD1.DAT`, and initializes subsystems.
4. `0x7F58` reads the save index, and `0xB818` loads `RUN.ART` as resource slot
   253.
5. `0x7D2B` creates a new session and initializes the menu/game state.
6. `main` repeatedly updates audio and dispatches states 0, 1, and 2 to the
   menu/game loop, reset path, and restore path. It has no ordinary return.

## Command-line parser

The parser in `main` lowercases the option letter and handles exactly the six
switches described by `MANUAL.TXT`:

| Switch | Static behavior |
|---|---|
| `-t` | Sets the no-mature-topics flag. |
| `-bX` | Maps K to 0, N to 1, R to 2, and L or T to 3. |
| `-c` | Sets the no-combat flag. |
| `-idirectory` | Copies the suffix after `-i` and appends a backslash for configuration and sound-driver paths. |
| `-sXfilename` | Initializes data, applies translation X, and calls the export routine with the filename after X. |
| `-gXX` | Computes `10 * argv[i][2] + argv[i][3] - 0x210`, the decimal two-digit export mask. |

An argument without a leading hyphen replaces the `DDGAMES` save prefix and
implements the manual's per-player name/path option. An unknown switch calls
the game's message path with `Huh?`.

## Text export

Function `0x5F92` opens the requested file in text-write mode. It parses the
game's record tags and writes labeled sections. Direct bit tests recover the
full `-gXX` mask:

| Bit | Value | Output |
|---:|---:|---|
| 0 | 1 | Lie/verse number (`#00` template) |
| 1 | 2 | `CYBER LIE:` |
| 2 | 4 | `PARAPHRASE:` / lock text |
| 3 | 8 | `CONVERSATION WITH VICTIM:` |
| 4 | 16 | Communications-room material, represented by several record tags |
| 5 | 32 | `VERSE:` |

The routine writes the heading `CAPTAIN BIBLE IN DOME OF DARKNESS`, iterates
the available records/buildings, and uses Microsoft C `fread`/write and text
stream helpers. This is implementation evidence for the manual's export
feature rather than merely a string search. The text-format chapter documents
the extensionless verse indexes, companion `DDL*` streams, loader, inspector,
and complete QEMU export validation.

## Save files

The default player prefix is `DDGAMES`; a non-option argument replaces it.
The `.SV0` index is nine 27-byte label buffers, normal states are `.SV1`
through `.SV9`, and F10/F9 use the independent `.SVQ` state. Static copy
direction separates checkpoint and live fields in each fixed 2,752-byte state.
The scalar fields include translation, music, effects, and checkpoint/live
text-bank values; the 66 ten-byte descriptors connect exactly to the recovered
text resources. The [save-game format chapter](save-formats.md) gives the full
15-block layout, filename logic, supplied-file comparison, error behavior, and
reproducible inspector.

## Input and hardware support

`0x90D4` uses BIOS video interrupt `10h` functions `1A00h` and `12h` to classify
the display adapter. Startup requires return value 2 and otherwise prints
`VGA not detected.`

`0x8E0A` checks interrupt vector `33h` and calls the mouse reset function.
Functions at `0x8D50` and `0x8D5D` show and hide the mouse cursor. `0x8D79`
reads mouse motion and buttons, clamps coordinates to 320×200, and accumulates
button press/release bits. The event combiner at `0x7BED` merges this with the
keyboard path and returns internal event codes used by `0x875D`, including
Escape, Enter/click, pointer movement, and the four extended arrow codes.

The executable also contains wrappers around DOS interrupt `21h`, BIOS video
interrupt `10h`, keyboard interrupt `16h`, and a loaded-driver interface on
interrupt `66h`. Sound data and XMI filenames indicate that the driver layer
will require a separate focused pass before its entry points can be named with
the same confidence.

## Installation lock file and sound drivers

Startup reads all four bytes of `SOUND.5` into a local structure. The fields
are installation policy rather than sound-hardware selection:

| Offset | Size | Use |
|---:|---:|---|
| `0` | 2 | Bible-translation lock, applied only when no command-line lock was supplied; `0070h` means unlocked. |
| `2` | 1 | Mature-topic marker; only `DBh` permits mature topics, otherwise the no-mature flag is forced. |
| `3` | 1 | Value ORed into the no-combat flag. |

The supplied file is `01 00 00 00`: translation value 1, forced no-mature
mode, and no installation-level combat restriction. This also explains why
`-b`, `-t`, and `-c` cannot relax installation locks: startup preserves an
already selected command-line translation and ORs the two restriction flags.

The following four files are independent driver components loaded into far
memory. `SETSOUND.BAT` records their original configured names:

| Installed file | Original name | Identification |
|---|---|---|
| `SOUND.1` | `soundrv.com` | DIGPAK Sound Blaster 16 digital driver, Audio Solution 3.40 |
| `SOUND.2` | `midpak.adv` | Miles Design Sound Blaster Pro FM music driver |
| `SOUND.3` | `tmidpak.com` | MIDPAK resident music package, Audio Solution 3.0 |
| `SOUND.4` | `midpak.ad` | MIDPAK timbre/instrument data |

The dynamic trace confirms that `load_file_into_far_memory` at `0xACDA`
opens each file, measures it with seek calls, allocates its paragraph-rounded
size, reads it in chunks, and closes it.

## Main resource archive

The lookup routine at `0x99AB` uppercases the requested base name and
extension, scans an in-memory table in 24-byte steps, seeks the persistent
`DD1.DAT` handle to the record's 32-bit offset, and verifies the two-byte `GC`
payload signature. The loader at `0x97D0` then selects either the raw far-copy
path at `0x9BEF` or the dictionary decoder at `0x9CA4` from the record marker.

The latter initializes 256 literal dictionary entries, reconstructs codes
from groups of low bytes plus high-bit plane bytes, and expands prefix/suffix
chains through `0x9D98`. Static reconstruction plus extraction of every
declared member establishes the full directory and compression format; see
the dedicated `DD1.DAT` chapter.

## Palette and artwork rendering

All `PAL` resources are raw 256-entry VGA DAC tables. The BIOS palette path at
`0xA017` uses video function `1012h`; the retrace-synchronized path at `0xA032`
writes the same six-bit RGB triplets through ports `03C8h` and `03C9h`.

Every `ART` frame has a 12-byte descriptor containing signed X/Y origins,
unsigned width/height, and a 32-bit pixel offset. The direct frame routine at
`0xB99C` multiplies the requested index by 12, reads width at offset 4, height
at 6, and the far pixel displacement at 8. The pixel body is row-major and
eight bits per pixel. Low-level blitters provide both opaque copying and an
index-0 transparent path. The graphics-format chapter records validation of
all 143 resources and the exact QEMU framebuffer comparison.

## Scene bytecode interpreter

The 62 `BIN` members contain scene programs interpreted by `0x451B`. The
routine reads opcodes `0x01` through `0x91` and dispatches through a 145-entry
handler table at `0x59AB`. Shared readers at `0x3A1E`, `0x3A30`, and `0x3A64`
consume bytes, little-endian words, and NUL-terminated strings from a far
resource cursor. Static handler analysis recovers the operand layout for all
145 commands; 122 opcodes occur across 25,837 decoded commands.

`initialize_scene` at `0x6631` appends `.BIN`, loads the resource, and starts
the interpreter at file offset zero. `update_scene_threads` at `0x7997`
resumes stored file offsets. Directly identified handlers load `.ART` and
`.PAL` members, select XMI music, change scenes, manage timing, manipulate
variables, and implement absolute jumps, calls, and returns. The dedicated
scene-bytecode chapter documents the complete structural schema, startup
sequence, mixed code/data regions, inspection tool, and QEMU memory check.

## Scene display objects

Scene programs append up to 100 ten-byte display records at `DS:A2AC`, with
the current count at `DS:00E2`. Direct object records contain signed X/Y,
8.8 scale, an ART-slot/visibility byte, one-based ART frame, render flags,
and a type byte. Other types connect animation sequences or command threads
to the same update list. The ART-slot high bit hides an object; two low bits
in the separate flags byte flip its axes.

The reset function at `0x3AD2` releases every render slot and clears the count
when changing scenes. The update function at `0x3AFF` dispatches records by
type, and `0xBCAC` submits direct objects to the ART renderer. A visible,
silent QEMU capture of `LOGO.BIN` contained 13 records whose type order and
direct fields exactly match all 13 linear display definitions in the script.
The dedicated scene-display-object chapter documents the layout, commands,
QEMU addresses, inspector output, and boundary between display state and
scripted gameplay state.

## Combat animation and actions

The seven `COMBAT*.BIN` programs contain 214 animation definitions with 2,596
nine-byte steps and 27 selectable action targets. Animation runtime records
begin at `DS:6EBA` with a 12-byte stride; they retain the first/current BIN
step offsets, timing, linked slot, mode, and render slot. Dedicated opcodes
start, link, stop, wait for, and branch on those animations.

Selectable actions use a separate ten-byte table at `DS:480E`. Each record
contains an absolute BIN target, screen coordinates, a selector-string
offset, and an active byte. The first ART resource in every combat is
`COMBTAGS`; rendering its four frames identifies selectors `.11` through
`.14` as `ATTACK`, `DEFEND`, `RETREAT`, and `COMBAT`. Pointer and keyboard
paths search active targets and start a BIN scheduler slot at the selected
target.

Random branches, the Sword and Shield flags, opcode-`0x81` faith loss, and
map/progression changes live in script state. Every Retreat target jumps
around the victory mutation into a shared exit. Six ordinary combats mark
the current map cell as kind `0xB`; the exceptional guard program uses kind
`0xA`, copies parameter B to A, omits faith loss, and never sets the
combat-active flag. `COMBAT7` implements the Zapper reward by ending a meter
flash at faith 10,000. No enemy-health field exists in the display or
action-target records. The combat-runtime chapter documents the tables,
commands, action outcomes, shared epilogue, and remaining dynamic validation
boundary.

## Conversation and choice flow

Scene scripts construct dialogue menus in a separate transient table. Opcode
`0x45` clears the table, opcode `0x44` appends a six-byte target/text record,
and opcode `0x46` presents the menu and suspends the scene thread. The record
count is at `DS:B428`; records begin at `DS:B116` and contain an absolute BIN
target followed by a far pointer to the inline choice text. The generic text
menu at `0x2556` returns the selected target through `DS:7CBA`, allowing the
interpreter to resume directly at the chosen branch.

Dialogue opcodes `0x14`, `0x48`, and `0x4E` share a presentation handler but
serve distinct channels dominated by the adversary, other characters, and
Captain Bible. Corpus analysis finds 40 choice definitions and 597 dialogue
commands. A visible, silent QEMU capture of the five-choice `BOSS.BIN` menu
matched every target and far text pointer from the static decode. Selecting
the final row wrote target `0x095C` and displayed the dialogue stored at that
exact branch.

Conversation scripts also invoke the study-Bible browser. Opcode `0x7D`
selects a victim-conversation, paraphrase, or cyber-lie prompt, and opcode
`0x49` requests the browser. A correct descriptor sets state flag `0x14`;
leaving without the expected match sets `0x15`. The conversation-flow
chapter documents the command lifecycle, runtime structures, BOSS memory
correlation, study integration, and remaining boundaries.

## World-map state

The archive contains 21 exact 768-byte map resources: levels A through G for
Easy, Normal, and Difficult modes. Opcode `0x78` constructs their names and
loads one into a mutable row-major 16×16×3-byte grid. Address calculations in
the executable use `48*y + 3*x`; the first cell byte contains independently
used connection and location-kind nibbles, followed by two parameters.

The map screen also consults a 16-word exploration bitmap. Scene commands can
process the current cell, mutate each cell field, normalize location kinds,
and mark coordinates explored. The supplied `SV3` and `SV4` grids match
`CE.MAP` except for four explained field changes. The dedicated world-map
chapter gives the format, opcodes, save correlation, and inspection tool. It
also decodes connection directions, five room classes and orientations, the
seven hallway Cybers, Scripture stations, hidden Spider triggers, cleared
encounters, level exits, and locked-room actions while keeping three
environmental kinds explicitly unresolved.

## Script state and progression

The two 200-byte save blocks are checkpoint and live copies of 100 signed
script-variable words. BIN commands encode variables as even byte offsets
within this block and provide copy, immediate assignment, signed comparison,
branching, arithmetic, increment/decrement, and bitwise operations. Static
handlers and complete-corpus validation identify 39 variables used by that
core family.

Words 3 through 10 double as a 128-bit state-flag bank. Dedicated scene
commands branch on, set, and clear flags. The executable rebuilds transient
map flags `0x00..0x2F`, while flags `0x30..0x34` are the five powerups and
seven victim scenes set distinct rescue flags `0x3A..0x40`. Variable 21 is
faith on a 0–10,000 scale; opcode `0x81` applies difficulty-scaled loss.
Separate text-descriptor state bytes connect obtained or completed text
records to scene branches. The script-state chapter documents the complete
recovered families and remaining semantic boundaries.

## Digital effects and XMIDI music

Opcode `0x57` passes an effect number and rate to `0x417F`. That routine
formats `D###.ABT`, loads it from the archive, allocates the decoded sample
count from the first word, calls the built-in decoder at `0x92E0`, and submits
the resulting PCM state to the DIGPAK interface on interrupt `66h`.

The decoder implements absolute samples, run-length commands, and packed
one-, two-, or four-bit adaptive delta blocks. Its helpers at `0x93BE`,
`0x94CB`, and `0x956E` add signed table deltas to the preceding sample and
clamp to unsigned eight-bit PCM. All 41 resources decode exactly to 412,282
samples at 9,000 Hz. A QEMU breakpoint immediately before playback captured
`D003.ABT`'s live 9,064-byte buffer; it is byte-identical to the host decoder.

Music function `0x4091` chooses `MUS###.XMI` or `IBM###.XMI`. All 32 resources
are IFF/XMIDI files with `FORM XDIR`, one `INFO` sequence count, `CAT XMID`,
and one `FORM XMID` containing `TIMB` and `EVNT`. The audio-format chapter
documents both formats and their reproducible tools.

## High-confidence function map

| Load offset | Name |
|---:|---|
| `0x034F` | `load_map_resource` |
| `0x0457` | `normalize_map_cells` |
| `0x075F` | `show_map_screen` |
| `0x0C6C` | `process_current_map_cell` |
| `0x1191` | `initialize_script_state` |
| `0x1B6C` | `start_palette_blackout` |
| `0x1B86` | `enter_game_over_scene` |
| `0x1C88` | `show_study_bible` |
| `0x2556` | `select_from_text_menu` |
| `0x2933` | `show_dialogue_message` |
| `0x3363` | `initialize_hardware_and_data` |
| `0x3979` | `reduce_faith` |
| `0x3A1E` / `0x3A30` | Read byte/word BIN operands |
| `0x3A64` | `bin_read_cstring_offset` |
| `0x3AD2` | `reset_scene_display_records` |
| `0x3AFF` | `render_scene_display_records` |
| `0x3B9B` | `resolve_animation_transform` |
| `0x3D08` | `render_animation_slot` |
| `0x3DA8` | `update_animation_slots` |
| `0x3F59` | `start_animation_slot` |
| `0x3FDF` | `stop_animation_slot` |
| `0x4001` | `load_palette_resource` |
| `0x4091` | `play_music_resource` |
| `0x4155` | `release_sound_effect_buffer` |
| `0x417F` | `play_sound_effect_resource` |
| `0x4235` | `stop_sound_effect` |
| `0x43F5` / `0x4413` / `0x4433` | Test/set/clear state flags |
| `0x446F` | `render_study_prompt` |
| `0x451B` | `execute_bin_commands` |
| `0x5AD6` | `find_text_record_by_selector` |
| `0x5B24` / `0x5B76` / `0x5BBF` | Get/set/clear text-record state |
| `0x5CE2` | `copy_text_record_component` |
| `0x5EE7` | `write_wrapped_export_text` |
| `0x5F92` | `export_game_text` |
| `0x629C` | `load_text_bank` |
| `0x6631` | `initialize_scene` |
| `0x6A23` | `update_action_selector_overlay` |
| `0x7997` | `update_scene_threads` |
| `0x7A5C` | `start_scene_thread` |
| `0x7B12` | `handle_faith_depletion` |
| `0x7BED` | `poll_input_event` |
| `0x7D2B` | `initialize_new_session` |
| `0x7D8E` / `0x7E41` | Copy live state to/from save buffers |
| `0x7F01` / `0x7F58` | Write/read the 243-byte save index |
| `0x7FD7` / `0x81AC` | Write/read the 2,752-byte save state |
| `0x834E` | `handle_study_bible_request` |
| `0x8558` | `find_action_target_by_key` |
| `0x875D` | `main_menu_and_game_loop` |
| `0x89AF` | `parse_bible_translation_lock` |
| `0x8A09` | `set_cwd_from_executable_path` |
| `0x8A82` | `game_main` |
| `0x8D79` | `update_mouse_state` |
| `0x8E0A` | `detect_mouse` |
| `0x90D4` | `detect_video_adapter` |
| `0x92D0` | `abt_get_sample_rate` |
| `0x92E0` | `decode_abt` |
| `0x93BE` / `0x94CB` / `0x956E` | Decode packed ABT delta blocks |
| `0x97D0` | `archive_load_member` |
| `0x99AB` | `archive_lookup_member` |
| `0x9BEF` | `archive_read_raw_member` |
| `0x9C5F` | `archive_refill_input` |
| `0x9CA4` | `archive_decode_member` |
| `0x9D98` | `archive_expand_code` |
| `0x9FF7` | `vga_set_dac_entry` |
| `0xA017` | `vga_load_palette_bios` |
| `0xA032` | `vga_write_palette_range` |
| `0xA0C9` | `blit_rect_to_vga` |
| `0xA106` | `blit_rect_transparent_zero` |
| `0xA136` | `blit_rect_opaque` |
| `0xACDA` | `load_file_into_far_memory` |
| `0xB5A8` | `rotate_palette_range` |
| `0xB620` | `update_palette_effect` |
| `0xB818` | `load_art_resource` |
| `0xB948` | `release_render_slot` |
| `0xB99C` | `draw_art_frame_opaque` |
| `0xBCAC` | `render_scene_display_object` |
| `0xCB5C` | `runtime_startup` |

The Rizin script additionally names verified Microsoft C library routines such
as `fopen`, `fread`, `fclose`, `strcat`, `strcpy`, `strcmp`, `tolower`,
`toupper`, `puts`, and `chdir`.
