# Reproducing the Results

This chapter provides one end-to-end path through the repository. Individual
format chapters explain the evidence and field meanings; this page answers the
practical question “which commands recreate and verify the results?”

The original game files remain under `CB/` and are intentionally not tracked.
Generated disk images, extracted resources, memory dumps, rendered media, and
the HTML book remain under ignored `build/` directories. The Python tools,
tests, Rizin names, checked symbol catalog, and Markdown sources are tracked.

## 1. Check the input copy

The supplied executable and main container used for this research are:

| File | Bytes | SHA-256 |
|---|---:|---|
| `CB/CB.EXE` | 64,299 | `2b7726ae9cf56e0067533e4bd1c5c76685f1d9855a7d90835850388db7b07ee0` |
| `CB/DD1.DAT` | 1,866,068 | `a395fcf9f19d655a6440b5b8ab213983eb7d34a99810b763a9c95360f98f9562` |

Verify them on macOS with:

```sh
shasum -a 256 CB/CB.EXE CB/DD1.DAT
```

The file-inventory chapter records every supplied file, size, timestamp, hash,
and current identification.

## 2. Build and run the DOS environment

Construct or verify the FreeDOS base and persistent play image without opening
QEMU:

```sh
tools/setup_freedos_image.py
./run.sh --setup-only
```

Play with the required visible, zoom-to-fit Cocoa display and silent host audio:

```sh
./run.sh
```

Use `./run.sh --rebuild` only when deliberately replacing the persistent play
image and its saves. The environment chapter documents the image layout,
mtools offset, boot scripts, and guest path.

## 3. Reconstruct and inspect the executable

Recover the EXEPACK-compressed load module:

```sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE
```

When the recorded title dump is present, independently compare relocation and
the live process image:

```sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/dumps/title-physical-1m.bin \
  --load-segment 0x627
```

Load recovered names and verify the checked symbol catalog:

```sh
rizin -b 16 -i analysis/cb.rz build/analysis/CB_UNPACKED.EXE
tools/inspect_symbol_map.py
```

The executable and symbol-map chapters define load offsets, file offsets,
segment translation, confidence levels, and optional handler-address auditing.

## 4. Extract the resource archive

List and expand all 369 directory entries:

```sh
tools/extract_dd1.py --list CB/DD1.DAT
tools/extract_dd1.py --extract-all build/dd1/all CB/DD1.DAT
```

Repeated archive names receive numeric prefixes in all-member output, so no
member overwrites another. The extractor validates declared sizes, payload
magic, compression boundaries, and exact input consumption.

## 5. Reproduce graphics results

Inspect frame descriptors, render a canvas, and regenerate the annotated
full-screen gallery:

```sh
tools/render_art.py build/dd1/all/003_LOGO.ART --list
tools/render_art.py \
  build/dd1/all/003_LOGO.ART \
  --palette build/dd1/all/002_LOGO.PAL \
  --canvas --scale 2 \
  --output build/graphics/logo.png
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT \
  --output build/graphics/full-screen-gallery.png
```

These paths cover all 143 ART members and infer scene-selected palettes from
decoded BIN commands. The graphics chapter records descriptor validation and
the independent QEMU framebuffer comparison.

## 6. Inspect scripts and gameplay systems

The general BIN decoder supports display objects, choices, animations, and
actions:

```sh
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN
tools/inspect_bin.py build/dd1/all/001_LOGO.BIN --objects
tools/inspect_bin.py build/dd1/all/327_BOSS.BIN --choices
tools/inspect_bin.py \
  build/dd1/all/337_COMBAT7.BIN --animations --actions
```

Inspect the world grid and late-game road graph with their specialized tools:

```sh
tools/inspect_map.py CB/DD1.DAT --map CE --rooms
tools/inspect_map.py CB/DD1.DAT --map CE --hall-features
tools/inspect_unibot.py build/dd1/all/315_CP2.BIN
```

The scene, object, conversation, combat, state, maps, and endgame chapters
connect those views to executable runtime tables and progression behavior.

## 7. Reproduce audio and text results

Decode a sound effect, validate an XMIDI container, and join a verse index to
its companion text stream:

```sh
tools/convert_abt.py \
  build/dd1/all/306_D003.ABT \
  --output build/audio/d003.wav
tools/inspect_xmi.py build/dd1/all/267_MUS001.XMI
tools/inspect_midpak_ad.py CB/SOUND.4
tools/inspect_text_resources.py \
  CB/DD1.DAT --data-dir CB \
  --translation N --bank A --record 0
```

The audio decoder covers all 41 ABT members; the XMI parser covers all 32 music
members; and the timbre inspector validates all 181 installed OPL patches. The
text inspector covers every translation and bank pairing. Their chapters
record the live PCM and QEMU-export comparisons.

## 8. Inspect saves and mutable state

Decode the fixed label index, one state, its descriptors, and named variables:

```sh
tools/inspect_save.py CB/DDGAMES.SV0
tools/inspect_save.py CB/DDGAMES.SV3 --descriptors
tools/inspect_save.py CB/DDGAMES.SV9 --variables
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

These commands connect the 2,752-byte save layout to script state, text
descriptors, and the mutable 768-byte map.

## 9. Repeat dynamic tracing when needed

Launch the visible QEMU session with the game-filtered DOS-call plugin:

```sh
./run.sh --trace-dos
```

The dynamic-analysis and sound-driver chapters document generated paths,
deterministic segment assumptions, preserved startup hashes, live AX capture,
and the `int 21h`/`int 66h` record formats. This is an interactive capture, not
part of the fast test suite.

## 10. Run the complete noninteractive verification

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
tools/check_documentation.py
tools/inspect_symbol_map.py
bash -n run.sh tools/build_qemu_dos_trace.sh
mdbook build docs
test -f build/docs-book/index.html
```

The tests read original inputs directly from `CB/` and do not depend on a
previous extraction directory. The documentation checker requires every book
chapter to appear exactly once in `SUMMARY.md`, validates local links and
anchors, and confirms that repository commands in shell examples exist and are
executable. The final HTML is written to `build/docs-book/`.

## Result boundaries

The noninteractive suite proves deterministic parsing, structural invariants,
known byte-level regressions, documentation integrity, and book generation. It
does not claim to automate subjective gameplay checks. Interactive input,
complete major-screen coverage, and focused traces of save writes remain
separate dynamic tasks in PLAN.
