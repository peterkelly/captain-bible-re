# Captain Bible Reverse Engineering

This repository contains a reproducible environment and research notes for
reverse-engineering *Captain Bible in the Dome of Darkness*, a DOS game from
the 1990s. The original game files are expected in `CB/` and are intentionally
ignored by Git.

The FreeDOS/QEMU environment is complete and executable analysis is in
progress. See `PLAN.md` for the live task list and
`docs/src/progress-log.md` for the complete activity log.

## Requirements

- QEMU with `qemu-system-i386` and `qemu-img`
- mtools (`mformat`, `mcopy`, `mmd`, `mdir`, and `mtype`)
- `unzip`
- Python 3
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

The generated executable and memory dumps remain under ignored `build/`.
Research results, address conventions, function names, command-line behavior,
and the recovered save layout are in the mdBook source.

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

## QEMU DOS-call tracing

Run the game with the QEMU TCG tracer and monitor socket enabled:

```sh
./run.sh --trace-dos
```

The Cocoa window stays visible and host audio remains muted. Trace mode uses
one guest instruction per TCG translation block so register values can be
sampled at DOS interrupt boundaries; it is consequently slower than a normal
run. The generated plugin, trace, monitor socket, screenshots, and memory
dumps are kept under the ignored `build/qemu-trace/` directory.

The trace activates at the reconstructed entry point `0627:CB5C` and records
only `int 21h` calls from code segment `0627`. These addresses are stable for
the current deterministic FreeDOS image. If the DOS environment or boot
configuration changes, re-establish the load segment before relying on the
filter.

## Documentation

Build the research book with:

```sh
mdbook build docs
```

The rendered book is written to `build/docs-book/`.
