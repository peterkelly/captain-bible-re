# Compatibility Contract

## Behavioral, not structural, compatibility

A conforming engine MUST reproduce the behavior visible to scene programs,
resource files, saves, and players. It does not need to reproduce any previous
engine's allocation strategy, pointers, processor mode, hardware API, or
function decomposition.

The following are compatibility interfaces:

- archive directory records and compressed payloads;
- resource and external-file names;
- `PAL`, `ART`, `ABT`, `XMI`, `MAP`, verse-index, and companion-text bytes;
- `BIN` opcode encodings and absolute resource offsets;
- signed 16-bit script state and flag identifiers;
- player-visible input, menus, dialogue, animation, audio, and timing order;
- scene, map, text, progression, and checkpoint transitions; and
- `.SV0`, `.SV1` through `.SV9`, and `.SVQ` files.

## Compatibility profiles

### Data profile

An implementation satisfies the **data profile** when it can parse every
valid shipped resource and save file, reject malformed lengths without unsafe
memory access, and expose decoded values to higher layers.

### Shipped-game profile

An implementation satisfies the **shipped-game profile** when it can execute
all 62 supplied scene programs and complete the game with equivalent visible
state transitions. This profile exercises 122 of the 145 opcode values.

### Full interpreter profile

An implementation satisfies the **full interpreter profile** when it also
implements the 23 opcodes absent from shipped scene code according to this
specification. A complete compatible engine SHOULD satisfy this profile so
tools or restored content can use the full instruction set.

## Resource offsets and host references

A word stored in a scene program is often an offset relative to the beginning
of that expanded `BIN` member. A clean implementation SHOULD represent it as
an integer or a bounds-checked slice, never as a host pointer. The same rule
applies to string offsets, animation-step offsets, branch targets, and embedded
tables.

Save-file text descriptors contain four historical pointer bytes. Those bytes
are not portable identifiers. A clean implementation MUST rebuild text
references from the saved bank and selector information and MAY preserve or
zero the opaque pointer bytes when writing a save.

## Valid-input assumption and defensive behavior

The normative game behavior assumes the supplied, internally consistent data
set. A host implementation MUST still bounds-check all external data. It
SHOULD fail atomically with a useful error on a malformed archive, truncated
resource, invalid target, division by zero, or wrong-size save instead of
partially mutating live state.

Defensive rejection is not a gameplay incompatibility. Silently changing a
valid resource, reordering duplicate archive entries, changing signed
arithmetic, or normalizing an opaque map value is.

## Determinism

Script execution and resource decoding MUST be deterministic for the same
state and input sequence except where a random opcode explicitly requests a
value. The exact random-number generator and seed are not serialized and are
therefore an implementation choice. The result range and every script-visible
branch remain normative.
