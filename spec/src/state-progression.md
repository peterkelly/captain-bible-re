# State and progression

## Primary variables

The persistent script state is an array of 100 signed 16-bit words. New game
initialization clears all words before assigning starting values. Scene
programs may use unnamed words as temporaries; a compatible engine MUST save
all 100, not only the named fields.

The following indexes have cross-scene meanings:

| Index | Meaning |
|---:|---|
| 0 | Difficulty: 0 Easy, 1 Normal, 2 Difficult. |
| 11 | Current map X. |
| 12 | Current map Y. |
| 13 | Current connected kind or zero-mask room class. |
| 14 | Room entrance code or contextual neighboring kind. |
| 16 | Current map level letter as a character value. |
| 17 | Current cell parameter A. |
| 18 | Current cell parameter B. |
| 21 | Faith, from 0 through 10000. |
| 23–25 | Adjacent Trap parameter B at right, left, and above. |
| 37–52 | Sixteen exploration bitmap rows, one word per map Y. |
| 53 | Unibot turn/rotation value. |
| 54 | Current Unibot node. |
| 55 | Heading: 0 north, 1 east, 2 south, 3 west. |
| 56–62 | Completion of pylons 1 through 7. |
| 63 | Next Unibot node. |
| 64 | Active pylon number; 100 means none. |
| 65 | Tower state: 0, 1, 2, or 9. |

Faith is stored in hundredths of a displayed percentage point. New play starts
at 10000. F3 displays it as a percentage, and ordinary rendering clamps values
to the 0–10000 range. A negative value after input processing is clamped to
zero and requests `OVER`.

## Flag bank

Variables 3 through 10 also form a 128-bit boolean bank. Flag `n` resides in:

```text
word = 3 + (n >> 4)
mask = 1 << (n & 15)
```

Flags `00` through `2F` include transient movement and action context and are
rebuilt by current-cell processing. Higher flags carry durable abilities and
progress. Important identifiers are:

| Flag | Meaning |
|---:|---|
| `14` | Study selection matched the expected record. |
| `15` | Study browser was left without that match. |
| `30` | Sword power. |
| `31` | Shield power. |
| `32` | No Trap power. |
| `33` | Candle power. |
| `34` | Flight power. |
| `37` | Automatic Combat enabled. |
| `38` | Ordinary combat active; option is locked. |
| `3A`–`40` | Victims `JELO`, `FEAR`, `CULT`, `LAW`, `RICH`, `DENY`, `NAGE` rescued. |
| `42`–`48` | Corresponding crew members aboard the Unibot. |
| `54` | One-time Annoy Cyber event completed. |

The status bar exposes the five powers as F4 through F8 icons. They are
boolean capabilities, not consumable counters, unless a scene explicitly
clears them.

## Ordinary progression

Each level is an explorable grid containing halls, Cybers, side rooms,
Scripture stations, and an exit. The player acquires verses, studies them to
answer lies and unlock interactions, rescues the level's victim, and reaches
the exit. Scene programs set the seven rescue flags at the successful
conversation points. The engine MUST preserve the live map, variables, flags,
text-record states, and scene name across save/restore.

At the gantry, each rescue flag `3A`–`40` is mirrored to crew flag `42`–`48`.
The craft requires all seven crew flags; with fewer, it reports the missing
count and does not depart. Departure clears Sword, Shield, No Trap, Candle,
and Flight, initializes Unibot node and heading state, and enters the final
road network.

## Unibot graph

The final network is a 16-node graph embedded in `CP2.BIN`. Direction slots
are north, east, south, west; `100` is blocked. All open edges are reciprocal.

| Node | Type | Map coordinate | Transition | N | E | S | W |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | road/start | `(270,170)` | 0 | 1 | 100 | 100 | 100 |
| 1 | road | `(270,165)` | 0 | 14 | 4 | 0 | 2 |
| 2 | road | `(265,165)` | 0 | 9 | 1 | 3 | 100 |
| 3 | pylon 1 | `(265,170)` | 800 | 2 | 100 | 100 | 100 |
| 4 | road | `(275,165)` | 0 | 6 | 5 | 100 | 1 |
| 5 | pylon 2 | `(280,165)` | 480 | 100 | 100 | 100 | 4 |
| 6 | road | `(275,160)` | 0 | 15 | 7 | 4 | 100 |
| 7 | pylon 3 | `(280,160)` | 480 | 100 | 100 | 100 | 6 |
| 8 | pylon 4 | `(275,150)` | 160 | 100 | 100 | 15 | 100 |
| 9 | road | `(265,160)` | 0 | 12 | 100 | 2 | 10 |
| 10 | pylon 5 | `(260,160)` | -160 | 100 | 9 | 100 | 100 |
| 11 | pylon 6 | `(260,155)` | -160 | 100 | 12 | 100 | 100 |
| 12 | road | `(265,155)` | 0 | 100 | 13 | 9 | 11 |
| 13 | pylon 7 | `(270,155)` | 480 | 100 | 100 | 100 | 12 |
| 14 | Tower | `(270,160)` | 160 | 100 | 100 | 1 | 100 |
| 15 | road | `(275,155)` | 0 | 8 | 100 | 6 | 100 |

The player can turn right (`.r`), turn left (`.l`), or move forward (`.u`).
Turns wrap heading modulo four. Forward follows the adjacency entry for the
current heading and is unavailable when it is 100.

On scene entry, endpoint nodes normalize to adjacent roads:
`3→2`, `5→4`, `7→6`, `8→15`, `10→9`, `11→12`, `13→12`, and `14→1`.
The engine MUST honor the script's table reads and this normalization rather
than substituting Euclidean movement.

`CP2.BIN` is `1E55` bytes. Its commands occupy `0000..1D54`; the trailer is
four consecutive signed-word tables:

| Offset | Words | Meaning |
|---:|---:|---|
| `1D55` | 64 | 16 nodes × north, east, south, west destinations. |
| `1DD5` | 16 | Node type: 0 road, 1 pylon, 2 Tower. |
| `1DF5` | 16 | Opaque transition values. |
| `1E15` | 32 | Sixteen lower-right map `(x,y)` coordinate pairs. |

The first eligible road event loads `ANNOY`, clears the player's acquired
verse states, and sets flag `54`. Later road visits skip it.

## Pylons and ending

Pylon endpoints map to variables 56 through 62 and study selectors `11`
through `17`. A completed pylon is skipped. Correct study sets its variable to
one, destroys it, and recovers the associated crew member. A wrong answer
enters `OVER`.

The Tower at node 14 requires all seven variables to be nonzero; arriving
early also enters `OVER`. With the gate satisfied, `FACE` and `CP3` implement:

| State | Behavior | Result |
|---:|---|---|
| 0 | Tower threatens; crew recalls Captain Bible. | set 1 and return to `FACE` |
| 1 | Tower presents hopelessness; study selector `20`. | correct: 2; wrong: 9 |
| 2 | Captain rejects control. | `KABLAM`, then `WIN` |
| 9 | Captain surrenders. | `OVER` |

There is no additional engine-defined victory condition. Scene programs and
these persistent values are the progression authority.
