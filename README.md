# Captain Bible Reverse Engineering

[![docs](https://img.shields.io/badge/docs-online-blue)](https://peterkelly.github.io/captain-bible-re/)

<p align="center">
  <img src="title.png" width="640">
</p>

This repository contains a reproducible environment and research notes for
reverse-engineering
[Captain Bible in the Dome of Darkness](https://archive.org/details/msdos_Captain_Bible_in_the_Dome_of_Darkness_1994),
a DOS game from the 1990s. The original game files are expected in `CB/` and are intentionally
ignored by Git.

The FreeDOS/QEMU environment and the planned static and dynamic analysis are
complete. See `PLAN.md` for the living checklist and
`docs/src/progress-log.md` for the complete activity log.

## Requirements

- QEMU with `qemu-system-i386` and `qemu-img`
- mtools (`mformat`, `mcopy`, `mmd`, `mdir`, and `mtype`)
- `unzip`
- Python 3
- Pillow (for `ART`/`PAL` rendering)
- A C compiler, `pkg-config`, and GLib development headers for DOS tracing
- A POSIX shell
- mdBook (for the research book)
- Rizin (for the supplied symbol script and further disassembly)

The setup is being developed and tested with QEMU 11.0.2 and mdBook 0.5.3 on
macOS/Apple Silicon.

## Running the game

From the repository root, run:

```sh
./run.sh
```

The script opens QEMU and starts Captain Bible automatically. On its first
run, it creates a persistent play image at
`build/captain-bible/captain-bible.img`. Saved games are written to that image
and remain available on later runs. On macOS, the game uses QEMU's visible
Cocoa display with `zoom-to-fit=on`. Before QEMU opens, the script prints both
the host image filename and the guest path `C:\CBDOME\CB.EXE`.

The game supports both mouse and keyboard input. If QEMU captures the pointer,
use Control-Option-G to release it on macOS. Exit through the game's Escape
menu before closing QEMU so pending save writes complete cleanly.

QEMU still presents Sound Blaster 16 and AdLib hardware to the game, but uses
the silent `none` audio backend. The Cocoa window remains visible while game
audio is suppressed on the host.

To prepare or check the images without opening QEMU:

```sh
./run.sh --setup-only
```

To recreate the play image from the current `CB/` directory:

```sh
./run.sh --rebuild
```

`--rebuild` replaces the persistent play image and therefore resets any saved
games held only inside it.

## Rebuilding FreeDOS

The base operating-system image is constructed noninteractively from the
official FreeDOS 1.4 LiteUSB distribution:

```sh
tools/setup_freedos_image.py
```

The result is `build/freedos/freedos.img`. The builder verifies the published
SHA-256, preserves the source boot code, constructs a new FAT16 partition, and
copies the FreeDOS filesystem with mtools. It does not run or automate the
FreeDOS installer.

The current workspace image also contains the complete game at `C:\CBDOME`, added
after the base image was built. If you boot that image directly, run:

```bat
CD \CBDOME
CB
```

Rebuilding the base image removes that manual game copy. Running `./run.sh`
will still create or use the separate game-bearing play image automatically.

Run its focused unit tests with:

```sh
python3 -m unittest discover -s tests -v
```

## Executable analysis

`CB.EXE` is a 16-bit MZ executable compressed with Microsoft EXEPACK. Generate
the independently verified unpacked executable and, when the recorded QEMU
dump is present, compare it with the relocated process image:

```sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/dumps/title-physical-1m.bin \
  --load-segment 0x627
```

Load the current high-confidence names into Rizin with:

```sh
rizin -b 16 -i analysis/cb.rz build/analysis/CB_UNPACKED.EXE
```

Audit all 140 named functions, 71 BIN handlers, and 9 data symbols against the
Rizin script, with per-entry confidence and evidence, using:

```sh
tools/inspect_symbol_map.py
```

The generated executable and memory dumps remain under ignored `build/`.
Research results, address conventions, function names, command-line behavior,
and the recovered save layout are in the mdBook source.

Inspect the installed Miles AIL/MIDPAK OPL timbre library with:

```sh
tools/inspect_midpak_ad.py CB/SOUND.4
tools/inspect_midpak_ad.py CB/SOUND.4 --list
```

The sound-driver chapter maps all 34 game-side `int 66h` sites and the DIGPAK
and MIDPAK service contracts. `./run.sh --trace-dos` records both DOS `int 21h`
and driver `int 66h` calls and returns while keeping the Cocoa window visible
and host audio silent.

## Extracting `DD1.DAT`

The main resource archive has a recovered 24-byte directory format and custom
LZW-family compression. List or extract its 369 members with:

```sh
tools/extract_dd1.py --list CB/DD1.DAT
tools/extract_dd1.py \
  --extract RUN.ART \
  --output build/dd1/RUN.ART \
  CB/DD1.DAT
tools/extract_dd1.py --extract-all build/dd1/all CB/DD1.DAT
```

All-member output is prefixed with each directory index so repeated archive
names remain distinct. The extractor validates the directory, payload magic,
compressed stream, expanded size, and exact input consumption. Format details
and the corresponding executable routines are in the mdBook's `DD1.DAT`
chapter.

## Rendering artwork

Extracted `ART` resources contain 12-byte frame descriptors followed by
row-major eight-bit pixels. Their colors come from separate 768-byte VGA
`PAL` resources. Inspect or render them with:

```sh
tools/render_art.py build/dd1/all/003_LOGO.ART --list
tools/render_art.py \
  build/dd1/all/003_LOGO.ART \
  --palette build/dd1/all/002_LOGO.PAL \
  --canvas --scale 2 \
  --output build/graphics/logo.png
```

The renderer can also write one frame with `--frame` or every frame with
`--all-frames`. Palette index 0 is transparent by default for sprite previews;
use `--opaque-zero` when reproducing an opaque draw. The mdBook graphics
chapter documents the format and its byte-for-byte correlation with QEMU VGA
memory.

Generate an annotated contact sheet of every full-screen ART frame, with PAL
associations inferred from the scene programs:

```sh
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT \
  --output build/graphics/full-screen-gallery.png
```

Use `--scale 2` for a nearest-neighbor enlarged sheet.

## Inspecting scene bytecode

The 62 extracted `BIN` resources contain scene programs. The recovered
decoder knows the operand layout and dispatch effect of all 145 opcodes. It
assigns semantic names to every value, including conservative low-level names
for the 23 values absent from the shipped scripts:

```sh
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN
tools/inspect_bin.py build/dd1/all/001_LOGO.BIN --objects
tools/inspect_bin.py build/dd1/all/327_BOSS.BIN --choices
tools/inspect_bin.py \
  build/dd1/all/337_COMBAT7.BIN --animations --actions
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x0c96 --limit 0x1754
```

Most resources are code from beginning to end. `CP2.BIN` has a data trailer,
and `ROOM3.BIN` has three command regions separated by zero-filled reserved
blocks, so those regions require explicit `--start` and `--limit` values. The
mdBook scene-bytecode chapter describes the interpreter, command schema,
startup sequence, QEMU memory correlation, and complete opcode catalog. It
also records the corrected two-word layout of opcode `0x69`, which removes 11
phantom commands from the linear corpus.
The `--objects` view summarizes the display records defined in linear command
order, including thread/animation types and direct objects' coordinates,
scale, flags, frame, and ART slot. See the scene-display-object chapter for
the live ten-byte layout and control-flow caveat. The `--choices` view lists
dialogue-choice source offsets, absolute branch targets, and inline text. See
the conversation-flow chapter for its six-byte runtime table, study-Bible
integration, and live QEMU correlation. The `--animations` view groups each
animation header with its contiguous nine-byte steps; `--actions` lists
screen coordinates, absolute targets, selectors, and recovered combat and
hall-action labels.
The combat-runtime chapter documents their runtime tables, BIN scheduler,
action outcome branches, faith effects, shared victory/retreat epilogue, and
map transitions.

Patch both scene-name fields in a disposable 2,752-byte state for controlled
scene-entry experiments, then compare a physical-memory capture with its BIN
definitions using:

```sh
tools/patch_save_scene.py input.SVQ COMBAT1 output.SVQ
tools/inspect_runtime_tables.py memory.bin \
  --data-segment 0x14e1 \
  --bin build/dd1/all/343_COMBAT1.BIN
```

The patcher changes only the two saved 20-byte scene-name fields; use it only
on research copies. The runtime inspector decodes the counted action and
animation tables plus ten BIN-thread records. With `--bin`, it compares action
targets and animation definition fields against the static command stream.

`CP2.BIN` ends with the complete 16-node Unibot navigation graph. Inspect its
four-heading exits, seven pylon nodes, Tower, lower-right-map coordinates, and
per-node transition values with:

```sh
tools/inspect_unibot.py build/dd1/all/315_CP2.BIN
```

The Unibot and endgame chapter follows the seven-rescue boarding gate through
all pylon encounters, the one-time Annoy Cyber event, the Tower gate, and the
successful and failed ending chains.

## Inspecting audio resources

The 41 `ABT` members are compressed 9,000 Hz unsigned eight-bit mono sound
effects. Inspect one or convert it to a standard WAV file with:

```sh
tools/convert_abt.py build/dd1/all/306_D003.ABT
tools/convert_abt.py \
  build/dd1/all/306_D003.ABT \
  --output build/audio/d003.wav
```

The 32 `XMI` members are one-sequence IFF/XMIDI music resources. Validate and
summarize their containers, timbres, and event streams with:

```sh
tools/inspect_xmi.py build/dd1/all/267_MUS001.XMI
```

## Inspecting game text

The extensionless resources in `DD1.DAT` contain translation-specific verse
indexes. They pair with the `DDLA` through `DDLR` files containing lies,
paraphrases, questions, explanations, and conversations. Inspect a combined
record with:

```sh
tools/inspect_text_resources.py \
  CB/DD1.DAT --data-dir CB \
  --translation N --bank A --record 0
```

Translations are `K`, `N`, `R`, and `T`; banks are `A` through `G` and `R`.
The mdBook text-format chapter documents both binary layouts and their
validation against the game's built-in study-file exporter.

Both tools reject structural inconsistencies and consume their inputs exactly.
The mdBook audio chapter documents the formats, executable decoder, and a
byte-for-byte comparison between host-decoded `D003.ABT` and its live QEMU
PCM buffer.

## Inspecting saved games

Each player prefix has a 243-byte `.SV0` label index, nine normal state files,
and a separate `.SVQ` quick save. Inspect either fixed format with:

```sh
tools/inspect_save.py CB/DDGAMES.SV0
tools/inspect_save.py CB/DDGAMES.SV3 --descriptors
tools/inspect_save.py CB/DDGAMES.SV9 --variables
```

The inspector validates exact sizes, decodes the nine fixed C-string label
buffers, separates live and checkpoint state blocks, and exposes the saved
settings and text descriptors. The mdBook save-format chapter documents the
2,752-byte state layout, player-prefix behavior, quick-save suffix changes,
snapshot copying, error behavior, and evidence from all supplied saves.
The `--variables` view decodes the 100 signed script words, named map and
faith fields, the embedded 128-bit flag bank, powerups, and victim-rescue
flags.

## Inspecting world maps

The archive contains 21 world maps: levels A through G at Easy, Normal, and
Difficult settings. Each is a row-major 16×16 grid of three-byte mutable
cells. Display the location-kind grid and optionally list its nonzero cells:

```sh
tools/inspect_map.py CB/DD1.DAT --map CE
tools/inspect_map.py CB/DD1.DAT --map CE --cells
tools/inspect_map.py CB/DD1.DAT --map CE --rooms
tools/inspect_map.py CB/DD1.DAT --map CE --hall-features
```

The cell view names the four connection directions. The room view decodes
the five room classes—Victim, Trap, Prayer, Communications, and Jump
Tunnel—together with each room's entrance side and mutable parameters.
The hall-feature view identifies the seven Cyber types, hidden Spider
triggers, Scripture stations, cleared encounters, and level exits while
leaving unresolved environmental states unnamed.

Compare an original map with the live grid serialized in a save:

```sh
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

The mdBook world-map chapter documents resource naming, cell addressing,
packed fields, room dispatch and orientation encoding, scene commands,
hallway entities and transitions, exploration bits, map-screen behavior, and
the byte-level identification of supplied save grids.

## QEMU DOS-call tracing

Run the game with the QEMU TCG tracer and monitor socket enabled:

```sh
./run.sh --trace-dos
```

The Cocoa window stays visible and host audio remains muted. Trace mode uses
one guest instruction per TCG translation block so register values can be
sampled at DOS and driver interrupt boundaries; it is consequently slower than
a normal run. The generated plugin, trace, monitor socket, screenshots, and
memory dumps are kept under the ignored `build/qemu-trace/` directory.

The trace activates at the reconstructed entry point `0627:CB5C` and records
BIOS keyboard `int 16h`, DOS `int 21h`, mouse `int 33h`, and sound-driver
`int 66h` calls and returns from code segment `0627`, including live AX and
the other argument/result registers. These addresses are stable for the
current deterministic FreeDOS image. If the DOS environment or boot
configuration changes, re-establish the load segment before relying on the
filter.

## Documentation

Run the documentation integrity check and build the research book with:

```sh
tools/check_documentation.py
mdbook build docs
```

The checker validates SUMMARY coverage, local chapter links and anchors, and
repository commands used in shell examples. The Reproducing the Results
chapter gives a single end-to-end command sequence for every recovered format
and system. Known Gaps and Evidence Boundaries separates confirmed results
from deliberately unnamed fields and the limits of controlled scene-entry
captures.
The rendered book is written to `docs/book/`.

Pushes to `main` that change the book or its publishing workflow build and
publish the same output with GitHub Actions. The workflow can also be started
manually from the Actions tab. It installs the tested mdBook 0.5.3 Linux
binary, verifies its published SHA-256, uploads `docs/book/` as a Pages
artifact, and deploys it to:

<https://peterkelly.github.io/captain-bible-re/>

The repository's Pages source is configured for GitHub Actions, and the first
deployment has completed successfully. Subsequent relevant pushes publish
automatically; no generated book files are committed.
