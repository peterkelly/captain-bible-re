# Scene runtime

## Scene state

Entering a scene creates a fresh scene-local runtime while preserving global
game state. The engine MUST load the requested `BIN`, reset its display list,
action list, dialogue choices, navigation graph and callbacks, animations,
and scene threads, then execute the program from offset zero. Art and palette
loads performed by the program populate that scene's rendering state.

Scene changes are deferred requests. Once requested, the current update MUST
stop accepting scene actions, finish safe cleanup, and enter the named scene
with the named secondary entry string. Resource names are case-insensitive.

## Display objects

The scene maintains an ordered display list. A logical display object has:

- a type identifying direct, thread-driven, or animation-driven rendering;
- X and Y coordinates in the 320×200 logical space;
- a 16-bit scale where `0x0100` is native scale;
- render flags, including horizontal and vertical reflection;
- an ART slot and frame number; and
- a hidden state.

Objects MUST be painted in list order. Direct-object opcodes append objects.
Thread and animation declarations also append objects whose frame and position
come from their controller. Hiding an object preserves the record and its
animation state but omits its pixels. Showing it makes the current state
visible again.

The on-disk animation-step record is exactly nine bytes:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | `u8` | One-based ART frame; zero suppresses drawing. |
| 1 | `u8` | ART slot. |
| 2 | `i16le` | X. |
| 4 | `i16le` | Y. |
| 6 | `u16le` | Scale. |
| 8 | `u8` | Render flags. |

An animation definition consists of the interval word from opcode `06`
followed by its contiguous `07` records. Runtime animation state MUST retain
the first and current step, interval, optional linked animation, mode/state,
and display object. Starting resets the selected sequence as required by its
mode; stopping releases its visible object. State values 0, 5, and 6 are
terminal for the VM's wait and finished predicates. The precise subdivision
of two private bookkeeping bytes is not externally specified.

## Scene threads and movement

At least ten independent scene command streams MUST be supported because the
shipped content addresses ten scheduler slots. A thread retains its active or
suspended status, next command offset, delay, motion state, navigation node,
direction, position, selector label and coordinates, and any active movement
or overlay.

Each update decreases eligible delays, resumes ready command streams, advances
movement and animations, and resolves completed arrival/departure callbacks.
The exact host tick duration is not normative; ordering and playability are.
Movement must be smooth enough for the original art and action coordinates,
and waits must not complete before their controller reaches the states named
in the bytecode chapter.

Navigation edges are undirected. A movement request finds a route from the
thread's current node to the requested node, processes departure callbacks,
animates each edge, updates the current node, and processes arrival callbacks.
The forward and reverse callback families distinguish traversal relative to
the edge's stored node order. If no route exists, the request MUST leave the
object at its current node.

## Actions

An action target is logically:

| Field | Type |
|---|---|
| Program target | `u16` absolute `BIN` offset |
| X, Y | `u16`, `u16` logical coordinates |
| Label | string reference |
| Active | boolean |

The engine displays or otherwise exposes active actions when global action
selection is enabled. Selecting an action resumes execution at its target.
Thread selectors use the same player-facing interaction model but are attached
to a moving scene object. The engine MUST preserve list order for keyboard
cycling and deterministic hit testing.

## Palette, audio, and modal waits

Palette mapping and blackout effects are advanced as part of the scene update.
Audio waits complete on actual playback completion when audio is enabled and
on an equivalent logical timer when it is muted or unavailable. This prevents
muting sound from changing scene progression.

Dialogue, choice menus, study screens, pause screens, save/restore screens,
and help/status screens are modal. While one is active, ordinary scene actions
do not advance. Animations and audio MAY continue where that does not alter
program outcomes. Dismissing a modal interface resumes the suspended command
at the specified continuation.

## Capacity and validation

A clean implementation SHOULD use dynamically sized collections. It MUST
support every table size used by the shipped resources, including 66 text
descriptors and ten scene-thread slots. It MUST reject invalid resource
offsets, unterminated strings, impossible frame references, and table growth
that would exhaust its configured safety limits with a descriptive error,
rather than corrupting adjacent state.
