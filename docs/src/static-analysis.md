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

The default prefix is `DDGAMES`; a player argument replaces the prefix.
`0x7F58` appends `.SV0`, opens the file as `rb`, and reads `0xF3` (243) bytes.
The buffer is nine consecutive 27-byte slot-label records. When the index does
not exist, it initializes all nine labels from `(EMPTY)`. `0x7F01` writes the
same 243-byte index.

Normal game states use suffixes `.SV1` through `.SV9`. The quick-save path
temporarily changes the suffix digit to `Q`, so its state file is `.SVQ`.
Function `0x7FD7` writes a state and `0x81AC` reads the same fixed layout:

| File offset | Size | In-memory DS offset | Current interpretation |
|---:|---:|---:|---|
| `0x000` | 200 | `7BF2` | Primary state block A |
| `0x0C8` | 200 | `727A` | Primary state block B |
| `0x190` | 66 | `3A66` | Compact per-item/entity values |
| `0x1D2` | 660 | `B194` | 66 records of 10 bytes |
| `0x466` | 20 | `6EA6` | String/state block |
| `0x47A` | 20 | `B83E` | String/state block |
| `0x48E` | 20 | `8938` | String/state block |
| `0x4A2` | 20 | `AEFE` | String/state block |
| `0x4B6` | 2 | `007C` | Scalar |
| `0x4B8` | 2 | `0048` | Scalar |
| `0x4BA` | 2 | `004A` | Scalar |
| `0x4BC` | 2 | `9FB0` | Scalar |
| `0x4BE` | 2 | `0080` | Scalar |
| `0x4C0` | 768 | `5B16` | 16×16×3-byte table |
| `0x7C0` | 768 | `76EC` | Second 16×16×3-byte table |
| **Total** | **2,752** | | |

All supplied `DDGAMES.SV1` through `DDGAMES.SV9` files are exactly 2,752
bytes, and the supplied `DDGAMES.SV0` is exactly 243 bytes. The table names
remain conservative until their gameplay meaning is correlated with data and
runtime changes.

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
| `0x3363` | `initialize_hardware_and_data` |
| `0x3A1E` / `0x3A30` | Read byte/word BIN operands |
| `0x3A64` | `bin_read_cstring_offset` |
| `0x4001` | `load_palette_resource` |
| `0x4091` | `play_music_resource` |
| `0x4155` | `release_sound_effect_buffer` |
| `0x417F` | `play_sound_effect_resource` |
| `0x4235` | `stop_sound_effect` |
| `0x451B` | `execute_bin_commands` |
| `0x5AD6` | `find_text_record_by_selector` |
| `0x5CE2` | `copy_text_record_component` |
| `0x5EE7` | `write_wrapped_export_text` |
| `0x5F92` | `export_game_text` |
| `0x629C` | `load_text_bank` |
| `0x6631` | `initialize_scene` |
| `0x7997` | `update_scene_threads` |
| `0x7BED` | `poll_input_event` |
| `0x7D2B` | `initialize_new_session` |
| `0x7D8E` / `0x7E41` | Copy live state to/from save buffers |
| `0x7F01` / `0x7F58` | Write/read the 243-byte save index |
| `0x7FD7` / `0x81AC` | Write/read the 2,752-byte save state |
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
| `0xB620` | `update_palette_effect` |
| `0xB818` | `load_art_resource` |
| `0xB99C` | `draw_art_frame_opaque` |
| `0xCB5C` | `runtime_startup` |

The Rizin script additionally names verified Microsoft C library routines such
as `fopen`, `fread`, `fclose`, `strcat`, `strcpy`, `strcmp`, `tolower`,
`toupper`, `puts`, and `chdir`.
