# Engine Lifecycle

## Startup

The engine startup sequence SHOULD be organized as follows:

1. determine the game-data directory and player save prefix;
2. read installation policy and user overrides;
3. open and validate `DD1.DAT`;
4. initialize graphics, input, audio, text, and save services;
5. read the nine-slot save-label index or synthesize empty labels;
6. load `RUN.ART` as the globally available cursor/movement artwork;
7. initialize a new session; and
8. enter `LOGO.BIN`, which begins the logo, title, and introduction chain.

A modern engine does not need the historical sound-driver files. It MUST honor
the resulting music, effects, translation, mature-topic, and no-combat policy.

The initial resource sequence is content-driven:

```text
LOGO.BIN  -> LOGO.PAL, LOGO.ART, D003.ABT
TITLE.BIN -> TITLE.PAL, TITLE.ART, TITLE2.ART, MUS001.XMI
INTRO.BIN -> INTRO.ART
```

The engine only selects the initial `LOGO` scene; those programs request the
remaining loads and transitions.

## New session

A new session clears all 100 signed script words, flags, text state, map state,
scene-local tables, and transient UI state. It initializes the scene-name
buffers, presents the introductory sequence and difficulty selector, and then
enters gameplay with full faith.

The scene programs perform much of the initialization. The engine MUST avoid
pre-populating script values that those programs expect to set themselves.

## Main update cycle

One logical update cycle performs these responsibilities in a stable order:

1. poll pointer and keyboard input and translate it into logical events;
2. update active palette effects and animation slots;
3. update or simulate sound-effect completion;
4. run eligible scene-command threads;
5. render display records and active overlays;
6. service modal dialogue, choice, study, map, status, and options requests;
7. apply a selected action or resumed bytecode target;
8. detect faith exhaustion and other top-level state transitions; and
9. present the completed 320-by-200 frame.

An implementation MAY split or combine these stages, but waits, modal screens,
and animation must continue to observe the same ordering. In particular, a
modal message may keep scene animation updating while its command thread is
suspended.

## Scene transition

A scene is identified by a base name and a secondary segment string. To enter
a scene, the engine MUST:

1. stop or release scene-owned render and audio state as required;
2. clear the display list, action targets, navigation callbacks, animation
   definitions, and scene threads;
3. load `<base>.BIN` from the archive;
4. retain the expanded bytes as mutable scene memory;
5. start bytecode execution at offset zero; and
6. let the scene program load its palettes, art, text bank, map, and audio.

Some commands deliberately patch bytes inside the loaded `BIN` image before a
later scene-change or resource-load command reads them. The expanded scene
buffer MUST therefore be writable for the lifetime of the scene.

## Suspension and resumption

Scene execution is cooperative. A handler either continues to the next
command, selects an absolute target, ends the current invocation, or yields.
A yielding command records enough state to resume at either the same command
or a target supplied by the UI.

Wait commands retry their condition. Dialogue commands retry without consuming
their text operand if another modal dialogue is already active. Choice
presentation resumes at the selected choice target. Study requests suspend the
scene while the study Bible runs, then expose success and cancellation flags
to later script commands.

## Checkpoints, saves, and restore

The engine maintains both live state and a checkpoint copy. Scene opcode
`0x55` copies selected live state into the checkpoint. Normal and quick saves
serialize both copies; saving does not implicitly refresh the checkpoint.

Restoring a state file loads both copies and then copies checkpoint fields to
live state to reconstruct the resumable scene, text bank, descriptors, and
map. This is
why saving during a conversation may resume from the beginning of that scene
rather than from the exact dialogue line.

## Shutdown

The options menu offers an explicit exit with confirmation. A clean engine
SHOULD flush any host audio and release resources. It MUST NOT silently save
the game during ordinary exit.
