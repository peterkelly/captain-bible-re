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

SDL3 is the default frontend. It accepts mouse clicks, Enter, Escape, letters for action
shortcuts, arrow keys for navigation and modal selection, F9 for quick load,
and F10 for quick save. It currently presents modal dialogue, choices, and the
study list in the launching terminal while the original indexed graphics
appear in the window.

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
frontends intentionally remain small: they emit music and decoded-effect
events but do not synthesize XMIDI or submit PCM to an audio device, and the
SDL adapter does not yet draw the game's text menus inside the window. Those
host presentation limitations do not alter resource parsing, scene execution,
save compatibility, or the logical timing used by scripts. Consequently, this
release does not claim the specification's full player-facing UI/audio
conformance profile yet.
