# Configuration and launch options

## Installation policy file

`SOUND.5` is exactly four bytes and contains policy, not sound-driver data:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | `u16le` | Translation lock; `0x0070` means unlocked, otherwise 0–3. |
| 2 | `u8` | Mature-topic permission; only `DB` permits, any other value forces filtering. |
| 3 | `u8` | Value ORed into no-combat mode. |

A command-line translation selection is retained instead of being replaced by
the installation translation. Restrictions combine monotonically: command
line options can request filtering or no-combat, but cannot relax an
installation restriction.

A portable engine MAY store equivalent policy in another configuration system
for native installations. When pointed at an original game directory, it MUST
interpret `SOUND.5` as above.

## Command line

Option letters are case-insensitive. The compatible launch interface is:

| Form | Effect |
|---|---|
| `-t` | Filter mature-topic records. |
| `-bX` | Translation: `K`=0, `N`=1, `R`=2, `L` or `T`=3. |
| `-c` | Enable no-combat mode, suppressing faith loss through opcode `81`. |
| `-idirectory` | Use the directory, with a path separator added, for installation configuration and audio assets. |
| `-sXfilename` | Export study material in translation X to the filename. |
| `-gXX` | Set a two-decimal-digit export mask. |
| non-option | Replace the `DDGAMES` player/save prefix. |

An unknown option MUST produce a clear error. A native implementation MAY also
offer modern long options, provided these forms remain supported in its
original-compatibility launch profile.

## Text export

The export mask has these bits:

| Bit | Value | Output |
|---:|---:|---|
| 0 | 1 | Numbered lie/verse heading. |
| 1 | 2 | Cyber lie (`L` component). |
| 2 | 4 | Paraphrase or lock text (`P` / `*`). |
| 3 | 8 | Conversation with victim (`W`). |
| 4 | 16 | Communications material (`W`, `C`, and `E` as applicable). |
| 5 | 32 | Citation and verse text. |

`M` metadata is not printed. The text is CP437-compatible text, wrapped at 70
columns, with the game study-file heading and section labels. Mature selectors
`E0` and above are excluded when filtering is active. Installation translation
locking applies to export as it does to gameplay.

## In-game settings

The options interface controls Bible translation when unlocked, music,
effects, and Automatic Combat. Music and effects are words in save state and
take effect immediately. Disabling effects must preserve logical sound wait
durations. Automatic Combat is flag `37` and is not changeable while ordinary
combat-active flag `38` is set.

Native ports MAY offer volume, scaling, controller, accessibility, or language
presentation options. Such additions cannot change scene variable values,
resource selection, study correctness, or saved original-format fields unless
the player explicitly opts into a non-compatible mode.
