# Input and User Interface

## Logical coordinate system

All scene coordinates and action targets use a 320-by-200 logical viewport.
A host window MAY scale this viewport to any size, but pointer coordinates
MUST be transformed back to the logical range and clamped to valid pixels.
Pixel-art scaling SHOULD use nearest-neighbor sampling.

The primary pointer action is a left-button press. Keyboard and pointer paths
must select the same logical actions.

## Exploration controls

During ordinary movement:

- arrow keys request movement in available directions;
- moving the pointer over an active target reveals its action label;
- clicking the active label selects it;
- Space cycles through currently available temporary action labels;
- Enter selects the current temporary action; and
- the first letter of a displayed action may select it when the scene defines
  that key.

Common selector strings are:

| Selector | Action |
|---|---|
| `.u`, `.d`, `.l`, `.r` | Move up, down, left, or right |
| `.c` | Confront Cyber |
| `.x` | Unlock |
| `.v` | Get Verse |
| `.11` | Attack |
| `.12` | Defend |
| `.13` | Retreat |
| `.14` | Combat |

Selector strings are data-driven; the engine MUST route them through the
active action-target table rather than hard-coding actions by screen position.

## Persistent status controls

When permitted by the current scene, the top control row provides:

| Key | Control | Behavior |
|---|---|---|
| F1 | Computer Bible | Browse obtained verses and optionally apply one. |
| F2 | Map | Show explored cells, room markers, and verse references. |
| F3 | Faith | Show the numerical faith percentage. |
| F4 | Sword | Explain the Sword powerup. |
| F5 | Shield | Explain the Shield powerup. |
| F6 | No Trap | Explain the No Trap powerup. |
| F7 | Candle | Explain the Candle powerup. |
| F8 | Flight | Explain the Flight powerup. |
| Escape | Game Options | Open the options menu. |
| F9 | Quick Load | Load `<player>.SVQ`. |
| F10 | Quick Save | Write `<player>.SVQ`. |

These are context-sensitive controls. A scene may consume a function key as a
normal continue action or suppress the status row. The engine MUST route input
through the active UI state before applying global shortcuts.

The ordinary status row uses transparent-zero frames from `STUFF.ART` at
their descriptor origins. Frame 4 is Computer Bible at `(4,1)`, frame 32 is
Map at `(23,1)`, and frames 22 through 26 are the five Faith-meter states at
`(44,3)`. Acquired Sword, Shield, No Trap, Candle, and Flight powers display
frames 17 through 21 respectively. Frame 11 is the upper-right disk indicator
at `(297,1)`. These are logical 320-by-200 coordinates; the standard output
expands them by 2 in both axes. Pointer activation uses the visible frame
bounds and must invoke the same interface as F1 through F8.

F2 is context-sensitive. Inside a building it shows explored and unexplored
halls, room letters, stations, and verse references. Outside, it shows the
city and colors a building gold after its victim has been rescued. One
building uses a special view of broken and closed platforms, rooms, and doors.
During the Unibot sequence, a lower-right map shows the vehicle's node and
heading.

### F2 map modal

The ordinary F2 map is a 320-by-200 indexed modal built from `MAP.ART`; it is
not a host-drawn diagram or a panel layered over the current scene. Opening it
replaces the complete viewport with palette index zero, temporarily suppresses
the scene and status controls, and draws the composed map using the current
scene palette. `MAP.ART` has no companion map palette.

Frame numbers below are zero-based resource indexes. Frame 0 is the
`189`-by-`167` blue enclosure at descriptor origin `(44,26)`, and frame 1 is
the hinged `OFF` control at `(64,27)`. The engine MUST clone frame 0 for each
opening. It then composites symbol frames into that clone with source color
zero transparent. A symbol's destination is:

```text
destination_x = caller_x + symbol.origin_x
destination_y = caller_y + symbol.origin_y
```

The mutated frame 0 and the unchanged frame 1 are then drawn at their own
descriptor origins. Implementations MUST preserve indexed pixels through this
composition; substituting generic lines, text, or geometric markers does not
reproduce the resource artwork.

When exterior-map flag `39` is set, the normal grid is skipped. Frame 51 is
composited at caller offset `(66,31)`. For each set rescue flag `3A` through
`40`, the corresponding frame 52 through 58 is composited at the same offset.
This produces the seven-building city overview and turns rescued buildings
gold using the authored overlays.

When flag `39` is clear, the engine uses the packed world grid and exploration
rows as described in the world chapter. Sixteen-column maps first composite
frame 62 at `(0,0)` for the legend. Each cell uses caller position
`(64 + 7*x, 34 + 5*y)`. Frames 3 through 18 are the 16 explored connection
shapes, and frames 24 through 39 are the corresponding unexplored shapes.
Frames 19 through 21 and 40 through 42 are the explored and unexplored room
approaches. Explored rooms add their class letter from frames 46 through 50
(`V`, `T`, `P`, `C`, or `J`). Frames 59 through 61 supply station and special
level-E markers. The exact frame selection is specified with the packed-map
model in the world chapter.

Escape, `O`, `o`, or a primary-button press on frame 1 closes the modal. A
press elsewhere does nothing. Enter does not close it. Arrow keys retain the
DOS map behavior of snapping the pointer along its five-pixel vertical and
seven-pixel horizontal grid:

```text
Up:    y = ((y - 57) / 5) * 5 + 52
Down:  y = ((y - 57) / 5) * 5 + 62
Left:  x = ((x - 104) / 7) * 7 + 97
Right: x = ((x - 104) / 7) * 7 + 111
```

The divisions truncate toward zero, matching signed 16-bit DOS division.
The mouse driver or host coordinate layer clamps the result to the logical
viewport.
When state flag `52` is set, the ordinary F2 map request is suppressed; the
late-game vehicle map remains owned by its scene program.

## Dialogue and menus

A modal message advances on Enter, Escape, or an equivalent click. A choice
menu uses Up and Down to move the highlighted row, clamps at both ends, and
uses Enter to select it. Pointer motion highlights the wrapped row under the
cursor and a left click selects that row; clicking outside its panel does
nothing.

Escape cancels a study or returns from interfaces where an Off action is
available. In the computer Bible, Page Up and Page Down change pages, arrow
keys choose a verse, and Apply uses `A` or Enter when enabled.

## Options menu

The options menu contains Exit, Save Game, Load Game, New Game, Translation,
Music, Sound Effects, Automatic Combat, and Continue. Up and Down move through
the rows; Enter or a click activates the selected row.

Automatic Combat cannot be toggled while the combat-active flag is set. Exit
and New Game require confirmation. Exit does not save. Save and load use the
nine labeled slots. A normal save lets the player edit a slot label of at most
26 CP437 bytes plus NUL. The most recently saved listed slot is marked with
`<<` in the load interface. Continue closes the menu without changing the
game.

## Pause behavior

Opening the options interface pauses ordinary scene interaction. Modal
dialogue and study interfaces suspend their owning scene thread but MAY keep
visual animation and audio service active. A host application losing focus
MAY additionally pause, provided it does not advance script timers while
paused.
