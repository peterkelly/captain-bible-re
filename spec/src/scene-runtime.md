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

Direct, thread, and animation declarations append objects to one mixed display
list. Their controllers update the frame and transform in the corresponding
stable slot, and all active slots MUST be painted in global list order. Hiding
an object preserves the record and its animation state but omits its pixels.
Showing it makes the current state visible again.

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
mode; stopping releases its visible object. The mode byte is also the live
state observed by the VM. Its complete resource-visible transition table is:

An unlinked animation renders the current step's absolute X, Y, and scale. A
linked animation recursively resolves its parent animation and applies the
child's signed delta from the child's first step:

```text
x     = parent.x     + (current.x     - first.x)
y     = parent.y     + (current.y     - first.y)
scale = parent.scale + (current.scale - first.scale)
```

The arithmetic has 16-bit wrapping behavior. Frame, ART slot, and render flags
still come from the child's current step. A link whose parent is stopped or
otherwise not renderable suppresses the child as well. Implementations MUST
reject or safely suppress invalid and cyclic links rather than recurse without
a bound.

| Start mode | Initial step | Direction | End-of-sequence behavior |
|---:|---|---|---|
| 1 | First | Forward | Set state 0 and release the visible render slot. |
| 2 | Last | Backward | Set state 0 and release the visible render slot. |
| 3 | First | Forward | Wrap to the first step, retaining state 3. |
| 4 | Last | Backward | Wrap to the last step, retaining state 4. |
| 5 | First | None | Remain on the first step in terminal state 5. |
| 6 | Last | None | Remain on the last step in terminal state 6. |
| 7 | First | Forward | Back up to the last valid step and change to state 8. |
| 8 | Last | Backward | Advance to the first valid step and change to state 7. |
| 9 | First | Forward | Remain on the last step and change to terminal state 6. |
| 10 | Last | Backward | Remain on the first step and change to terminal state 5. |

Modes 7 and 8 therefore form a ping-pong pair. “First valid” and “last
valid” above account for the attempted step beyond the sequence boundary;
the boundary command is not displayed as an animation record. Starting a
mode renders its initial step immediately and initializes its countdown from
the negated sequence interval. Each animation update adds the logical tick
increment; when the countdown becomes positive, it performs the table's step
and subtracts the interval again.

State values 0, 5, and 6 are terminal for the VM's wait and finished
predicates, even though states 5 and 6 retain and render their endpoint.
Stopping any mode sets state 0 and releases its visible render slot. The
precise subdivision of the remaining private timing storage is not exposed
and need not be reproduced as a host data layout.

## Scene threads and movement

At least ten independent scene command streams MUST be supported because the
shipped content addresses ten scheduler slots. A thread retains its active or
suspended status, next command offset, delay, motion state, navigation node,
direction, position, selector label and coordinates, and any active movement
or overlay.

Each update decreases eligible delays, resumes ready command streams, advances
movement and animations, and resolves completed arrival/departure callbacks.
The reference supplies the elapsed timer delta to these controllers; it does
not add one merely because one host frame was presented. The controller clock
runs at 2,880 units per second. Its normal interrupt contribution is 24 units,
and the elapsed delta supplied to a single update is capped at 400. Movement
steps use an interval of 20 (about 6.94 ms), animation steps commonly use 40
(about 13.89 ms), and delays such as 3,000 last about 1.04 seconds. A host may
subdivide or batch updates, but it MUST accumulate elapsed time at this rate
and preserve command-boundary ordering.
Movement must be smooth enough for the original art and action coordinates,
and waits must not complete before their controller reaches the states named
in the bytecode chapter.

The scheduler delay is a signed countdown. A newly runnable stream has delay
zero. Opcode `0F` subtracts its operand from that value, commonly making it
negative. The outer update adds the logical elapsed-tick increment to negative
delays and does not execute that stream again until its delay is nonnegative.
The delay check occurs between commands, so an `0F` immediately followed in
the program by a jump or another command yields once `0F` makes the delay
negative. This is how palette fades and input-polling loops remain paced
without an explicit wait opcode.

## Scene-thread movement artwork

Opcode `02` records are navigation-node geometry, not independent visible
actors. The primary movement controller uses the source node's display slot
and renders one global `RUN.ART` sprite while traversing an edge. Opcode `53`
sets both current-node identifiers and immediately initializes X, Y, and
scale from that node. Merely changing the identifiers leaves the actor at the
previous entry-transition coordinates and is incompatible.

For one edge, let `dx`, `dy`, and `ds` be the differences in X, Y, and scale,
and let `average_scale = (start_scale + end_scale) / 2`. The reference derives
the number of 20-unit interpolation steps as:

```text
planar = (max(abs(dx), abs(dy)) + min(abs(dx), abs(dy)) / 2)
         * average_scale / 256
depth  = abs(ds)
steps  = max(1, max(planar, depth) + min(planar, depth) / 2)
```

Coordinates and scale use fixed-point increments across those steps. The
horizontal direction is right when `dx > 0` and left otherwise. It switches
to the away/toward orientation when `2 * abs(ds)` exceeds
`abs(dx) * average_scale / 256`; nonnegative `ds` selects away and negative
`ds` selects toward.

The walking phase advances by 28 modulo `0x0600` per interpolation step. Its
high byte selects one of six positions. Direction offsets are 0 for left and
right, 24 for away, and 12 for toward. An idle actor adds six to that index.
The resulting index selects a one-based `RUN.ART` frame from this exact table:

```text
01 02 03 04 05 06  13 13 13 13 13 13
07 08 09 0A 0B 0C  14 14 14 14 14 14
0D 0E 0F 10 11 12  15 15 15 15 15 15
```

Left-facing horizontal frames set horizontal reflection; the other three
orientations do not. A moving actor remains at the display-list position of
the opcode-`02` record that created its controller slot. Later display records
can therefore occlude it.

Navigation edges are undirected. A movement request finds a route from the
thread's current node to the requested node, processes departure callbacks,
animates each edge, updates the current node, and processes arrival callbacks.
The forward and reverse callback families distinguish traversal relative to
the edge's stored node order. The byte operand of opcodes `17` through `1A` is
the zero-based index of the opcode-`0B` edge record, not a node number. For
each edge, the engine dispatches the matching directional edge callback before
the source-node departure callback, then dispatches the directional edge
arrival callback before the destination-node arrival callback. If no route
exists, the request MUST leave the object at its current node.

After the initial offset-zero invocation has built the entry, edge, and
callback tables and returns, scene entry dispatch matches the requested
secondary entry string case-insensitively. The matching opcode-`0C` record's
two node bytes define the initial traversal. That traversal uses the ordinary
departure and arrival callback machinery; it is not a direct jump to a
hard-coded scene-specific target. For example, the startup `seg` entry in
`LOGO.BIN` traverses its declared `3`--`4` edge and dispatches the arrival
handler attached to node 4.

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
Loading a palette resets a 256-entry source-index map to identity and clears a
signed adjustment word for every output index. Palette output index `i` is
computed component-wise as:

```text
clamp(base_palette[mapping[i]] + adjustment[i], 0, 63)
```

Opcode `16` fills an inclusive adjustment range. Opcode `6C` advances and
wraps its phase inside the inclusive range, then maps successive output
indexes to successive source indexes beginning at that phase and wrapping at
the range end. Rotation changes this mapping; it does not destructively rotate
the already adjusted RGB output.

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
