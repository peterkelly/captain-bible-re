# Compatibility boundaries

## What this specification does not require

A compatible engine does not need to emulate a particular CPU, operating
system, memory model, graphics adapter, sound card, driver interface, file
handle convention, allocator, or compiler runtime. It does not need to keep
logical tables at fixed host addresses or serialize host pointers.

The following presentation choices are deliberately portable:

- host window size, fullscreen mode, and aspect correction;
- update frequency and interpolation, provided script-visible ordering holds;
- keyboard layout mapping and controller support in addition to original keys;
- the exact random algorithm and seed, within the requested modulo range;
- native XMIDI synthesis, conversion, and host resampling;
- crash reporting, logging, save-write atomicity, and malformed-data messages;
- internal object types, collection capacities above shipped requirements, and
  coroutine or scheduler implementation; and
- optional accessibility features that do not alter game state or answers.

## Opaque but preserved values

Some valid data participates in compatibility without a justified universal
name. Implementations MUST preserve and expose it to scene logic:

- connected map kinds `C`, `D`, and `F` and context-specific cell parameters;
- the separate 16×16 current-cell auxiliary table observed by opcodes `8E`
  and `91`;
- the `ABT` auxiliary header word;
- the three dialogue presentation bytes;
- per-node Unibot transition values;
- unrecognized companion `M` metadata strings; and
- the two legacy pointer words in a loaded original save, which are ignored or
  zeroed rather than dereferenced.

Opaque does not mean disposable. A value may influence a scene through normal
resource reads even when no cross-scene semantic name is assigned.

## Underdetermined timing and animation details

The resource-visible animation definition, its nine-byte steps, linking,
start/stop operations, terminal states, display output, and wait predicates are
normative. Two private runtime timing bytes and the exact internal transition
table for animation modes 1 through 10 are not specified as a host data
structure. A shipped-game implementation must nevertheless make the supplied
sequences loop, link, stop, and reach their wait states with equivalent visible
ordering. An implementation claiming cycle-exact animation compatibility must
document its additional timing model separately.

Likewise, the host duration of a “tick” is not fixed here. Scene delay values,
the silent 100-tick effect wait, and the unused 3000-tick text timer are logical
relative durations. They MUST remain ordered and playable; exact wall-clock
matching is an optional higher-precision profile.

## Font and text layout

Strings, CP437 decoding, text order, component selection, substitutions,
70-column export wrapping, modal regions, and scene hit coordinates are
normative. The exact bitmap glyph source is not exposed as an independent
documented resource. A replacement font is allowed if the resulting line
breaks and action regions remain compatible. Pixel-identical typography is
therefore outside the base shipped-game profile.

## Content-defined behavior

The engine must not promote a coincidence in current content into an engine
rule. Examples include the exact caller set for `POWER`, scene-local meanings
of unnamed temporary variables, visual identities for opaque hall kinds, and
which random branch corresponds to a named animation phase. The `BIN`
program, resources, and persistent selectors remain authoritative.

Conversely, absence from shipped content does not erase a VM command. The 23
unused opcodes are required by the full-interpreter profile and are specified
by their direct logical effects in [Scene-program virtual machine](bytecode.md).

## Extension policy

A port MAY add a versioned native save format, high-resolution UI, remastered
audio, translations, or new content. Original-format resources and saves must
still be available through a clearly identified compatibility mode. Extensions
SHOULD use new names or explicit version markers instead of overloading opaque
bytes in original files.
