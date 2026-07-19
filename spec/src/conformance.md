# Conformance

## Test environment

Conformance tests operate on a legally supplied original data directory. They
do not require an earlier engine. Tests SHOULD use fresh temporary save
prefixes, a deterministic input clock, a controllable random source, and muted
audio with logical completion enabled.

An engine SHOULD report its supported profile from [Compatibility
contract](compatibility.md): data, shipped game, or full interpreter.

## Data-profile tests

The parser test suite MUST establish all of the following:

1. `DD1.DAT` yields 369 ordered entries with the extension population listed
   in [Resources](resources.md).
2. Every member expands to its declared size and consumes its complete stored
   payload. Raw and compressed members are both exercised.
3. All 37 palettes are 768 valid six-bit RGB components.
4. All 143 artwork members have a valid 12-byte descriptor table and
   contiguous pixel blocks.
5. All 41 effects decode to their exact declared sample counts without unused
   bytes.
6. All 32 XMIDI members have valid IFF bounds and a terminating event.
7. The 21 maps cover levels A–G and difficulties E/N/D and are each 768 bytes.
8. All four translations and eight banks join to 319 logical records with the
   bank counts and companion lengths specified in [Text](text.md).
9. Every `BIN` code region decodes without an invalid instruction or operand
   overrun. `CP2.BIN` has code `0000..1D54` and a 256-byte data trailer;
   `ROOM3.BIN` has code ranges `0000..0335`, `0C96..1753`, and `1768` through
   its end.
10. Original saves are accepted only at the exact index and state sizes.

Malformed-input fixtures SHOULD cover overflowed offsets, truncated strings,
invalid LZW phrases, cyclic dictionary references, invalid frame tables,
wrong output counts, IFF chunk overruns, descriptor spans outside companions,
bad branch targets, division by zero, and short saves. Every rejection MUST be
bounded and atomic.

## VM tests

A full-interpreter suite MUST encode and run at least one legal instance of
every opcode `01` through `91`, including both `BH` and `BHH` paths for each
`BHs` opcode and both inline and `FF`-offset forms for every `p` opcode. It
MUST verify:

- little-endian operand reads and exact next-instruction offsets;
- signed comparison, multiply, divide, remainder, threshold, and 16-bit wrap;
- variable byte-offset validation and flag-bank mapping;
- absolute branches, nested calls, callback targets, and cooperative waits;
- mutable `BIN` byte and word reads/writes;
- display, action, dialogue, navigation, map, palette, text, and audio effects;
- all five no-ops and every command marked unused by shipped content; and
- deterministic suspension and resumption around input, animation, and audio.

The shipped-game profile may omit execution tests for unused opcodes but MUST
still decode their operand lengths so tooling can safely traverse a resource.

## Scenario tests

At minimum, an end-to-end implementation SHOULD automate or manually verify:

| Scenario | Required observation |
|---|---|
| Startup | Logo, title, introduction, difficulty selection, and first hall are reachable. |
| Input | Keyboard and pointer choose the same scene actions and modal rows. |
| Study | A wrong selector follows failure; the expected selector follows success in every translation. |
| Map | Moving marks the proper exploration bit; F2 does not change it. |
| Station | Get Verse sets the intended descriptor state and displays its reference. |
| Trap | Correct adjacent-door study clears parameter B; failure follows scene logic. |
| Combat | Attack/Defend/Retreat/Combat dispatch to script targets; retreat preserves the cell. |
| Difficulty | One loss site applies half, normal, and fourfold faith loss. |
| Leech | Victory changes kind 6 to A and transfers B to A. |
| Zapper | Victory ends at faith 10000 and changes the cell to B. |
| Save | Normal and quick saves round-trip state; restore resumes checkpoint rather than arbitrary live dialogue. |
| Crew gate | Six victims cannot depart; seven victims can. |
| Pylon | Correct study completes one variable; wrong study enters `OVER`. |
| Tower | Incomplete pylons fail; correct final answer reaches `WIN`; wrong reaches `OVER`. |

## Rendering and audio comparisons

Exact host RGB framebuffer bytes are not required after scaling, but the
unscaled indexed 320×200 composition SHOULD be suitable for golden-image
comparison at stable scene points. Tests SHOULD separately verify opaque zero,
transparent zero, both flips, clipping, origin offsets, native and non-native
scale, hidden objects, list order, palette rotation, and blackout.

Audio tests compare decoded ABT sample bytes and XMI event sequences before
host resampling or synthesis. Different audio backends MAY produce different
analog output. Muting effects MUST not change the frame or VM update on which
an audio wait completes under the test clock.

## Save interoperability

A state written by a conforming engine in original-format mode MUST be readable
by another conforming engine. Tests ignore bytes after the first NUL in fixed
string buffers and the four pointer bytes of each text descriptor, but compare
every other byte or logical field. Loading a rejected save MUST leave a hash
of the complete running game state unchanged.

## Completion criterion

Shipped-game conformance means the complete objective described in [The game
and its objective](game-overview.md) can be completed from a new session in all
three difficulties without engine-specific data patches. Save/load, both
input methods, every room class, all seven combat programs, all translations,
the Unibot graph, both Tower outcomes, and normal exit must remain usable.
