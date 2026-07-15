# Captain Bible Reverse-Engineering Plan

Last updated: 2026-07-15

This plan is a living checklist. Findings and commands are recorded in
`docs/src/progress-log.md`.

## Phase 1: Reproducible game environment

- [x] Inventory the supplied `CB` directory and available host tools.
- [x] Confirm the game's documented DOS launch command and memory needs.
- [x] Adopt the repository's noninteractive LiteUSB/mtools procedure.
- [x] Stop and discard the superseded installer-driven VM attempt.
- [x] Implement `tools/setup_freedos_image.py` and focused unit tests.
- [x] Download and verify the official FreeDOS 1.4 LiteUSB archive.
- [x] Construct the 1 GiB raw FreeDOS image under `build/freedos/`.
- [x] Verify the filesystem, boot scripts, MBR, and QEMU boot marker.
- [x] Add `run.sh` with VGA, mouse, Sound Blaster 16, and AdLib support.
- [x] Create a persistent play image containing the supplied `CB` directory.
- [x] Copy the game into both current images at `C:\CBDOME`.
- [x] Verify that FreeDOS boots and the game reaches its title screen.
- [ ] Have the user confirm interactive input, audio, and normal game exit.

## Phase 2: Static inventory and executable analysis

- [x] Record checksums, timestamps, formats, and sizes for every game file.
- [x] Identify the executable format, compiler/runtime, and memory model.
- [x] Recover and independently verify the EXEPACK-compressed load module.
- [x] Map the initial segments, entry points, strings, and DOS/BIOS services.
- [x] Analyze the command-line parser and documented export options.
- [x] Recover a first-pass function map for startup, input, saves, and export.
- [ ] Determine the purpose and format of each `DD*`, `SOUND.*`, and save file.

## Phase 3: Dynamic analysis

- [x] Establish a repeatable QEMU memory-capture and debugging workflow.
- [x] Capture and correlate a title-screen physical-memory snapshot.
- [x] Build a QEMU TCG plugin for game-originated DOS interrupt tracing.
- [x] Capture and interpret a startup-to-story-introduction DOS API trace.
- [ ] Trace startup, file access, graphics, input, sound, and save operations.
- [ ] Correlate runtime behavior with static functions and data structures.
- [ ] Exercise major screens and gameplay systems while recording evidence.

## Phase 4: File formats and game systems

- [x] Recover the `DD1.DAT` directory and named-resource layout.
- [x] Implement and verify a reproducible `DD1.DAT` extractor.
- [x] Recover the `PAL`, `ART`, and related sprite metadata formats.
- [x] Implement and verify reproducible artwork rendering tools.
- [x] Generate an annotated gallery of every full-screen ART frame.
- [x] Recover the `BIN` scene-command stream and startup sequencing.
- [x] Recover the `ABT` sound-effect and `XMI` music formats.
- [x] Implement and verify reproducible audio inspection/conversion tools.
- [x] Recover the extensionless verse indexes and companion `DDL*` text streams.
- [x] Implement and verify a reproducible text-resource inspector.
- [x] Document data containers, compression, graphics, audio, and text formats.
- [x] Recover and document save-game structures and player-name behavior.
- [x] Implement and verify a reproducible save-game inspector.
- [x] Recover world-map resources, runtime grid, and exploration state.
- [x] Implement and verify a reproducible world-map inspector.
- [x] Recover script variables, progression flags, faith, and text state.
- [x] Recover scene display objects, render fields, and visibility/frame controls.
- [x] Reconstruct conversation choices, dialogue channels, and study-Bible integration.
- [x] Recover combat action targets, animation slots, and BIN-thread control.
- [x] Trace combat outcomes, faith depletion, and encounter map transitions.
- [x] Decode room classes, entrance orientations, and Trap-room state.
- [x] Decode hallway Cybers, stations, exits, locks, and ambush states.
- [ ] Reconstruct endgame and Unibot progression.
- [x] Build small extraction or inspection tools where they improve confidence.

## Phase 5: Consolidation

- [ ] Produce a symbol/function map with evidence and confidence levels.
- [ ] Document reproducible procedures and all discovered formats and systems.
- [ ] Review the mdBook for gaps, contradictions, and unsupported claims.
- [ ] Build and verify the final book.
