# Combat

## Model

Combat is script-driven. The seven programs `COMBAT1` through `COMBAT7`
compose ordinary VM variables, flags, animations, actions, random branches,
sound effects, and faith changes. A compatible engine MUST execute those
programs rather than inventing a separate health/damage simulation.

The encounters correspond to:

| Program | Opponent | Player actions |
|---|---|---|
| `COMBAT1` | Macho Cyber | Attack, Defend, Retreat, Combat |
| `COMBAT2` | Armored Cyber | Attack, Defend, Retreat, Combat |
| `COMBAT3` | Mantis Cyber | Attack, Defend, Retreat, Combat |
| `COMBAT4` | Snake Cyber | Attack, Defend, Retreat, Combat |
| `COMBAT5` | Spider Cyber | Attack, Defend, Retreat, Combat |
| `COMBAT6` | Leech Cyber covering a station | Attack, Retreat, Combat |
| `COMBAT7` | Zapper Cyber | Attack, Defend, Retreat, Combat |

The action selectors are `.11` Attack, `.12` Defend, `.13` Retreat, and
`.14` Combat. They are ordinary scene action targets and their program targets
define the outcome. An action is available only while its target record is
active. Manual mode normally activates Attack, Defend, and Retreat. Automatic
mode normally activates Combat and Retreat. Combat 6 has no Defend target.

## Player understanding

Captain Bible does not have hit points. His 0–100% Faith meter is the loss
condition. Cyber attacks and incorrect choices reduce faith. At negative
faith, the engine clamps it to zero and enters the `OVER` scene.

The player answers a Cyber's lie through study before the physical encounter.
Within combat, Attack and Defend manipulate timing and animations. The Combat
action enters a script-defined randomized exchange. Sword flag `30` and Shield
flag `31` affect those branches and the duration of useful windows. Retreat
exits without defeating the Cyber. The scripts, not the engine, decide which
animation phase makes each action effective.

Automatic Combat is persistent flag `37`. Ordinary combat sets flag `38`
while active; the options menu MUST prevent changes to Automatic Combat during
that interval. Combat 6 intentionally does not use the lock.

## Faith loss

Opcode `81` supplies a base loss in internal faith units. The engine applies:

| Difficulty | Applied loss |
|---|---:|
| Easy | base / 2, integer division |
| Normal | base |
| Difficult | base × 4 |

No-combat installation mode suppresses the subtraction. The shipped static
loss sites are:

| Program | Base values |
|---|---|
| `COMBAT1` | 533, 2011 |
| `COMBAT2` | 107, 102, 502 |
| `COMBAT3` | 1037, 531, 2011, 1703 |
| `COMBAT4` | 596, 1005 |
| `COMBAT5` | 213, 2009 |
| `COMBAT6` | none |
| `COMBAT7` | 233, 207 |

These are possible branch sites, not values that all occur in one fight.

## Outcome contract

Victory in combat 1–5 and 7 changes the current connected map-cell kind to
`B`. Combat 6 changes it to `A`, copies parameter B to parameter A, and clears
B, revealing the covered Scripture station. Retreat skips these mutations,
so returning to the location preserves the encounter.

The Zapper victory alternates faith between 1 and 10000 five times as a visual
meter flash and ends at full faith. This reward occurs before the cell is
marked cleared.

Every encounter eventually selects the appropriate level hall scene and
starts a palette blackout. Two special hall variants may be selected by scene
state. Program self-patching constructs the hall name from the current level
letter. Scene logic also clears parameter A at the common exit where directed
by the resource.

## Animation and synchronization

Combat animation records use the format in [Scene runtime](scene-runtime.md).
Actions commonly disable choices, start one or more linked animations, play a
sound, and suspend until completion. Muted audio MUST use an equivalent logical
completion timer. Random modulo results select branches; deterministic test
runs MAY inject a known random source, but ordinary play SHOULD seed it in a
way that does not repeat every launch.

`POWER` is the in-combat study/power scene. It can patch a numbered
`combat1` name and return to the corresponding encounter. It is not the
game-over scene. Implementations MUST support this entry even though the exact
set of all scene paths that invoke it is not a separate engine invariant.
