# Captain Bible Rust engine

This directory contains a clean-room Rust implementation of the Captain Bible
game engine. It reads the original files from `CB/`; no game data is copied
into the crate.

The engine implements the original-data and shipped scene-runtime surface
described by the repository [`spec`](../spec/src/introduction.md): the
`DD1.DAT` archive, graphics and palettes, decoding for all 145 scene opcodes,
the 122 shipped opcode behaviors, cooperative scene threads, navigation,
dialogue and study records, world maps and progression state, original save
images, sound-effect decoding, XMIDI validation, and the original text-export
mode. The core has no third-party Rust dependencies.

## Build and run

SDL3 and `pkg-config` are hard build requirements, along with a current stable
Rust toolchain. From this directory:

```sh
cargo test --all-targets
cargo run --release -- --data ../CB --validate
cargo run --release -- --data ../CB
```

SDL3 is the default frontend. It draws modal dialogue, response choices, and
the Computer Bible inside the game window. Enter or a primary click dismisses
ordinary dialogue. Choice menus use Up and Down, pointer hover, Enter, and
row-specific clicks. The study browser additionally accepts Page Up, Page
Down, `A`, and Escape. Letters select exploration actions, arrow keys navigate,
F1 through F8 activate the status-row controls, F9 quick-loads, and F10
quick-saves when no modal interface is active. The status controls can also be
clicked directly.

Use the headless terminal frontend with:

```sh
cargo run --release -- --data ../CB --headless
```

In terminal mode, press Enter to dismiss dialogue, type a displayed choice
number or action label, enter `study N` for a requested record selector, and
enter `quit` to stop.

Useful diagnostic modes include:

```sh
# Drive a deterministic smoke run and capture the final 320x200 framebuffer.
cargo run --release -- \
  --data ../CB --headless --ticks 16000 --auto-confirm --screenshot dome.ppm

# Reproduce the original command-line study export.
cargo run --release -- --data ../CB -g63 -sTstudy.txt
```

`--ticks` and `--auto-confirm` are headless-only options. `--ticks` advances
the deterministic runner in reference timer units. The DOS controller runs at
2,880 such units per second. The SDL frontend converts elapsed host
milliseconds to that rate and may process several logical units before
presenting the next frame.

Original launch options `-t`, `-bX`, `-c`, `-iDIR`, `-sXFILE`, `-gXX`, and a
player/save prefix are accepted. Engine-only options are listed by `--help`.

## Architecture

- `archive`, `graphics`, `audio`, `text`, and `world` decode original data.
- `bytecode` bounds-checks every BIN instruction and operand form.
- `engine` contains the scheduler, scene VM, movement, rendering, input, and
  progression integration.
- `state` and `save` preserve the original variable, checkpoint, and disk
  layouts.
- `frontend` is the required-build, minimal SDL3 host adapter.

`tests/shipped_data.rs` validates the supplied archive corpus, decodes every
known BIN code region, renders the startup scene, and compares text export
against the captured DOS reference byte count and hash.

## Frontend scope

The reusable engine core is the primary implementation. The included host
frontends emit music and decoded-effect events but do not yet synthesize XMIDI
or submit PCM to an audio device. This remaining audio limitation does not
alter resource parsing, scene execution, save compatibility, modal input, or
the logical timing used by scripts.
