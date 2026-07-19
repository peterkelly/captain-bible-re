# The Game and Its Objective

## Premise

The city has been enclosed by a Tower of Deception. Its field suppresses truth,
and roaming deception Cybers capture and mislead the inhabitants. The Bible
Corps opens a small breach and sends Captain Bible into the city.

Captain Bible has no innate superpower. His usable power comes from Scripture
stored in a portable computer Bible. Teleportation begins the mission with the
computer Bible empty, so verses must be collected from Scripture stations and
applied to lies, locks, conversations, and other challenges.

## Overall objective

The player must:

1. enter each of seven principal buildings;
2. explore its halls and rooms;
3. collect useful verses;
4. confront Cybers by matching their lies with appropriate verses;
5. survive or avoid combat and environmental obstacles;
6. rescue one victim in each building;
7. return with all seven victims to crew the Unibot;
8. drive the Unibot through its road network and destroy seven energy pylons;
9. answer the Tower's final study challenge; and
10. destroy the Tower of Deception.

Failure occurs when faith is exhausted or when a scripted endgame challenge
fails. Success proceeds through the final destruction and victory scenes.
After the first building is completed, the remaining principal buildings may
be tackled in any order. Leaving an unfinished building and returning can
repopulate its Cybers according to the building-entry scene logic.

## Normal play loop

Most of the game alternates between exploration and scripted interactions:

- In a hall, the player moves between connected map cells and chooses temporary
  actions such as Move, Get Verse, Unlock, or Confront Cyber.
- Entering a room starts a room-specific scene: Prayer, Trap, Jump Tunnel,
  Communications, or Victim.
- Dialogue advances one message at a time and may offer several responses.
- The study Bible asks the player to select and apply an acquired verse.
- Successful Cyber confrontation leads to manual or automatic combat.
- The map, faith display, computer Bible, powerup explanations, and options are
  available through persistent top-of-screen controls when the active scene
  permits them.

Scene programs define the detailed order. The engine provides reusable
rendering, input, text, map, state, and timing services.

## Hall actions and study

A Scripture station offers **Get Verse**. Taking it marks that verse as
available in the Computer Bible and shows its reference and text.

A Cyber offers **Confront Cyber**. The Cyber states a lie and the Computer
Bible opens so the player can apply a verse. Applying the expected verse
defeats the lie and leads to combat. A related but not exact answer may follow
a scene-defined retry without penalty; a wrong answer can reduce faith.
Choosing Off before applying a verse retreats from the confrontation without
penalty.

A locked side-room door offers **Unlock**. The game displays a true statement
that must be matched to a supporting verse. The statement need not be a close
paraphrase. A correct match clears the lock state so the room can be entered.

## Manual and automatic action modes

Automatic Combat flag `0x37` changes both combat and Jump Tunnels:

- In manual Cyber combat, the usual actions are Attack, Defend, and Retreat.
  The player attacks during a vulnerability window and defends before an
  incoming hit. Several successful attacks may be required.
- In automatic combat, the actions are Combat and Retreat. The Combat result
  is selected by script random branches and can hurt neither party, hurt
  Captain Bible, or defeat the Cyber.
- In a manual Jump Tunnel, the player moves left or right to avoid incoming
  Cybers. In automatic mode, the script controls the run and its outcome.

The option cannot be changed in the middle of either interaction. Automatic
Combat is distinct from installation no-combat mode: the former lets scripts
choose results randomly, while the latter suppresses the engine's normal
faith-loss operation and prevents Jump Tunnel hits.

## Difficulty

At the beginning of a new game the player selects Easy, Normal, or Difficult.
The selection is stored as script variable 0 with values 0, 1, and 2.

Difficulty selects a distinct map resource for each building and changes
faith loss:

| Difficulty | Map suffix | Faith-loss multiplier |
|---|---|---:|
| Easy | `E` | one half, using integer division |
| Normal | `N` | one |
| Difficult | `D` | four |

The maps contain different verse and encounter populations. Scene programs
also make individual challenges more severe at higher difficulty. In
Difficult mode, Trap rooms can remove every powerup except Flight.

## Faith and failure

Faith is stored in hundredths of one percent. Full faith is 10,000 and zero is
empty. The status meter and detailed percentage display clamp out-of-range
values for presentation. A loss operation scales its base amount by difficulty
unless no-combat mode is active.

After input and scene processing, the engine MUST detect faith below zero,
clamp it to zero, and enter the game-over scene. Prayer rooms can restore
faith. Defeating a Zapper Cyber restores full faith.

## Verses and powerups

Obtained verses are represented by persistent state bytes on the current text
bank's descriptors. Scripture stations reveal verses, dialogue and study
screens apply them, and the map can show references without revealing the
verse text.

Five durable capabilities have status icons and state flags:

| Flag | Capability | Player-facing effect |
|---:|---|---|
| `0x30` | Sword | Improves combat attacks. |
| `0x31` | Shield | Improves defense in combat and obstacles. |
| `0x32` | No Trap | Makes Trap-room doors flash a warning. |
| `0x33` | Candle | Lights dark hall regions. |
| `0x34` | Flight | Enables flight where a scene supports it. |

Prayer rooms award these capabilities through study challenges. The exact
challenge flow remains scene-driven rather than hard-coded by the engine.

## Room types

Every building can contain the following room classes:

- **Victim:** hold the person who must be rescued for that building.
- **Trap:** require an appropriate verse to escape safely.
- **Prayer:** restore faith or award a powerup after a study interaction.
- **Communications:** let rescued victims discuss and transfer a verse.
- **Jump Tunnel:** move Captain Bible to another area while presenting an
  avoidance challenge.

The detailed interactions are:

- A Trap presents a lie that must be answered with the correct verse to
  escape safely. A nearly correct choice can allow another attempt. On
  Difficult, Trap consequences can clear every power except Flight.
- A Prayer room can restore faith or grant a requested power. A power request
  succeeds after the correct verse is applied; a wrong verse does not hurt
  Captain Bible.
- A Victim conversation requires several verse applications. The first victim
  provides access needed for the other buildings; later rescues return Captain
  Bible to that building's entrance.
- A Communications room speaks through an already rescued victim, poses a
  fixed interpretation choice for one verse, and transfers that verse after a
  correct response. A wrong response or leaving without choosing can cost
  faith.
- A Jump Tunnel relocates Captain Bible after the manual or automatic
  avoidance sequence described above.

The first building has no Communications room. The world-map format encodes
room class and entrance orientation; the [World Maps and Navigation](world.md)
chapter gives the exact representation.

## Cyber vulnerability guide

The combat art and timing communicate these intended attack windows:

| Cyber | Vulnerability or special behavior |
|---|---|
| Macho | Attack while its eye is open. |
| Armored | Attack while its lid is open. |
| Mantis | Attack while both arms are lowered. |
| Snake | Attack when it pauses in the lower-right corner. |
| Spider | Attack at the top of its jump; a hidden one may drop behind the player. |
| Leech | Attack while its lid is open; victory exposes the covered station. |
| Zapper | It can be walked under but drains faith; victory restores full faith. |
| Annoy | A one-time outdoor event that clears acquired verses and leaves without combat. |
