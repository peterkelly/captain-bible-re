# Captain Bible engine specification

Project repository: [https://github.com/peterkelly/captain-bible-re](https://github.com/peterkelly/captain-bible-re)

This book specifies the observable behavior and data contracts of a compatible
engine for *Captain Bible in the Dome of Darkness*. It is written for a reader
who has never played the game and has never seen an earlier implementation.

The game data is declarative: an archive supplies palettes, artwork, maps,
sound effects, music, text indexes, and scene programs. A compatible engine
loads those resources, executes the scene programs, presents the same choices
and challenges, and preserves the same persistent state. The host platform,
programming language, renderer, audio library, and internal object model are
implementation choices.

This is a clean-room behavioral specification. It intentionally contains no
machine-code addresses, memory segments, compiler conventions, hardware
interrupts, or instructions for reproducing an earlier program's internal
layout. Logical offsets that are part of a resource or save-file format are
included because they are public inputs to a compatible implementation.

## Normative language

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** mark
requirements:

- **MUST** identifies behavior needed for compatibility with valid game data.
- **SHOULD** identifies a safe or useful behavior that does not change normal
  play.
- **MAY** identifies a host-specific implementation choice.

Unless stated otherwise, integers are little-endian, byte offsets begin at
zero, strings use code page 437, and arithmetic stored in a script word wraps
to 16 bits.

## What an engine supplies

A complete engine has the following responsibilities:

1. locate configuration, text companions, save files, and `DD1.DAT`;
2. index and decompress named archive members;
3. render a 320-by-200 indexed-color logical screen and palette effects;
4. decode sound effects and play XMIDI music or a faithful conversion;
5. join translation-specific verse indexes to companion text banks;
6. execute all scene opcodes and coordinate scenes, threads, animation,
   dialogue, actions, maps, combat, and study interactions;
7. maintain script variables, flags, faith, verses, exploration, and
   progression;
8. read and write compatible save files; and
9. expose equivalent keyboard, pointer, options, and export behavior.

The specification describes those responsibilities independently. The
[Conformance](conformance.md) chapter brings them together into testable
profiles.
