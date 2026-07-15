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
feature rather than merely a string search.

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

## High-confidence function map

| Load offset | Name |
|---:|---|
| `0x3363` | `initialize_hardware_and_data` |
| `0x5F92` | `export_game_text` |
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
| `0xB818` | `load_art_resource` |
| `0xCB5C` | `runtime_startup` |

The Rizin script additionally names verified Microsoft C library routines such
as `fopen`, `fread`, `fclose`, `strcat`, `strcpy`, `strcmp`, `tolower`,
`toupper`, `puts`, and `chdir`.
