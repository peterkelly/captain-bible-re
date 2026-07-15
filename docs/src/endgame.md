# Unibot and Endgame Progression

The final sequence is controlled by six scene programs: `GANTRY`, `CP1`,
`ROBOT`, `CP2`, `FACE`, and `CP3`. `KABLAM` and `WIN` provide the successful
ending, while `OVER` handles both failure paths. Static decoding is sufficient
to recover the rescue gate, the complete Unibot road graph, all seven energy
pylons, and the Tower confrontation state machine.

## Boarding the Unibot

The seven victim scenes set rescue flags `0x3A..0x40`. On the gantry,
`GANTRY.BIN` mirrors each set flag to the corresponding crew-present flag:

| Victim flag | Crew flag |
|---:|---:|
| `0x3A` | `0x42` |
| `0x3B` | `0x43` |
| `0x3C` | `0x44` |
| `0x3D` | `0x45` |
| `0x3E` | `0x46` |
| `0x3F` | `0x47` |
| `0x40` | `0x48` |

`CP1.BIN` counts the seven crew flags in variable 27. With none present it
says the craft needs eight people in all; with one through six it reports how
many more people are needed. Exactly seven advances to `ROBOT.BIN`. That
scene clears the Sword, Shield, No Trap, Candle, and Flight flags, initializes
Unibot variables 53 through 55 to zero, and enters `CP2.BIN`.

This proves that `0x42..0x48` are not merely generic late-game flags: they are
the seven rescued crew members physically present for the Unibot mission.

## CP2 data trailer

`CP2.BIN` is exactly 7,765 bytes (`0x1E55`). Commands occupy
`0x0000..0x1D54`; four signed-word tables fill the remainder:

| Offset | Words | Recovered purpose |
|---:|---:|---|
| `0x1D55` | 64 | 16 nodes × four next-node indexes |
| `0x1DD5` | 16 | Node type: road `0`, pylon `1`, Tower `2` |
| `0x1DF5` | 16 | Per-node transition/render value |
| `0x1E15` | 32 | 16 lower-right-map `(x, y)` coordinate pairs |

The four exit slots are north, east, south, and west. Turning right increments
the current heading and turning left decrements it, both with wraparound.
Value `100` is the blocked-exit sentinel. Every nonblocked edge is reciprocal,
and each coordinate changes by five units in the expected direction.

The transition values are exposed by the inspector because the script indexes
them, but their exact visual interpretation remains unproven. Calling them a
render or rotation field would currently go beyond the evidence.

## Navigation graph

The road network has 16 nodes. `N`, `E`, `S`, and `W` are destinations; a dash
is blocked.

| Node | Type | Map `(x,y)` | Transition | N | E | S | W |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | road/start | `(270,170)` | 0 | 1 | - | - | - |
| 1 | road | `(270,165)` | 0 | 14 | 4 | 0 | 2 |
| 2 | road | `(265,165)` | 0 | 9 | 1 | 3 | - |
| 3 | pylon 1 | `(265,170)` | 800 | 2 | - | - | - |
| 4 | road | `(275,165)` | 0 | 6 | 5 | - | 1 |
| 5 | pylon 2 | `(280,165)` | 480 | - | - | - | 4 |
| 6 | road | `(275,160)` | 0 | 15 | 7 | 4 | - |
| 7 | pylon 3 | `(280,160)` | 480 | - | - | - | 6 |
| 8 | pylon 4 | `(275,150)` | 160 | - | - | 15 | - |
| 9 | road | `(265,160)` | 0 | 12 | - | 2 | 10 |
| 10 | pylon 5 | `(260,160)` | -160 | - | 9 | - | - |
| 11 | pylon 6 | `(260,155)` | -160 | - | 12 | - | - |
| 12 | road | `(265,155)` | 0 | - | 13 | 9 | 11 |
| 13 | pylon 7 | `(270,155)` | 480 | - | - | - | 12 |
| 14 | Tower | `(270,160)` | 160 | - | - | 1 | - |
| 15 | road | `(275,155)` | 0 | 8 | - | 6 | - |

The three player actions use selectors `.r`, `.l`, and `.u`: turn right,
turn left, and move forward. Forward indexes the four-entry adjacency row by
the current heading and disables the action when the result is `100`.

On scene entry, pylon and Tower node indexes are normalized back to their
adjacent road nodes: `3→2`, `5→4`, `7→6`, `8→15`, `10→9`, `11→12`,
`13→12`, and `14→1`. The behavior is exact; treating it as save/resume
normalization is a likely interpretation rather than a proven design name.

## Script variables and road event

| Variable | Meaning |
|---:|---|
| 53 | Turn/rotation offset used by the Unibot animation |
| 54 | Current Unibot node |
| 55 | Current heading (`0=N`, `1=E`, `2=S`, `3=W`) |
| 56–62 | Pylons 1–7 rescued/destroyed |
| 63 | Next node selected by forward movement |
| 64 | Active pylon number; `100` means no unresolved pylon |
| 65 | Tower confrontation state |

The ordinary-road handler also contains one special event. The first eligible
road visit loads `ANNOY`, removes the player's verses, sets flag `0x54`, and
continues without combat. Later road visits skip it. This matches the manual's
Annoy Cyber description, so `0x54` is the high-confidence one-time Annoy-event
flag.

## Energy pylons

Entering a pylon node maps it to pylon number 1 through 7 and variable 56
through 62. A pylon whose variable is already nonzero is skipped. Otherwise,
`CP2.BIN` loads the matching face artwork and presents one of seven study
prompts, selected by `0x11..0x17`.

The expected response sets that pylon variable to one, plays the destruction
sequence, and shows the corresponding crew member recovering. A wrong
response produces a catastrophic defense failure and enters `OVER`. Thus the
seven variables mean both that the pylon was destroyed and that its captive
crew member was recovered.

## Tower gate and confrontation

Moving into node 14 tests all seven pylon variables. If any is zero, the crew
reports that the defenses cannot hold and the scene enters `OVER`. With all
seven set, the Tower trance begins in `FACE.BIN`.

`FACE` renders dialogue for the current state; `CP3` performs the transition:

| State | `FACE` / `CP3` behavior | Next state or scene |
|---:|---|---|
| 0 | Tower threatens and cajoles; crew calls Captain Bible back. | state 1, `FACE` |
| 1 | Tower presses hopelessness and obedience; study prompt `0x20`. | correct: state 2; wrong: state 9 |
| 2 | Captain rejects control and accepts the risk. | `KABLAM` |
| 9 | Captain surrenders and shuts down the defenses. | `OVER` |

The successful resource chain is `CP3 → KABLAM → WIN`. The failed study
response follows `CP3 → FACE(state 9) → CP3 → OVER`. No additional hidden
endgame condition appears in these programs.

## Reproducible inspection

After extracting `DD1.DAT`, print and validate all four embedded CP2 tables:

```sh
tools/inspect_unibot.py build/dd1/all/315_CP2.BIN
```

The inspector rejects the wrong file size, invalid destinations, unknown node
types, nonreciprocal edges, a changed pylon set, or a Tower outside node 14.
Archive-backed tests independently assert the crew gate, Unibot initialization,
seven pylon variables, graph endpoints, Tower states, and ending scene chain.

All findings in this chapter come from expanded BIN bytecode and its embedded
tables. Interactive confirmation of the complete final sequence remains useful,
but is not required for the recovered control flow.
