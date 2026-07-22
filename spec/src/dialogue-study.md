# Dialogue and Bible study

## Dialogue presentations

The game has three dialogue channels:

- adversary dialogue (`14`), used for a Cyber's lie;
- character dialogue (`48`), used for victims, bosses, and other characters;
- Captain Bible dialogue (`4E`), also used for some narration or captions.

Each displays translated CP437 text in a modal panel using a three-byte
presentation tuple containing logical text X, text Y, and wrap width. Opcode
`5C` configures the Captain Bible channel. Opcode `5D` configures the character
channel, which the adversary presentation also uses. The panel frame extends
slightly beyond this text rectangle. A compatible engine MUST apply the tuple,
wrap within its width, and preserve the channel's command timing.

The `BOSS` introduction configures `[4, 30, 150]` for Captain Bible and
`[162, 89, 150]` for the other character. These place the two speakers at the
upper left and lower right respectively. `FACE` instead uses `[80, 12, 180]`
for adversary messages and `[80, 170, 180]` for Captain Bible. These shipped
values and the corresponding DOS captures establish all three byte roles.

Dialogue text uses the proportional seven-row atlas in `STUFF.ART` frame 0.
The renderer expands each logical atlas pixel to 2 by 2, advances by the
executable's per-character width plus one, and wraps by measured logical
width. Captain Bible and character messages use text style 2, whose atlas
values `0,1,2` map to palette indexes `1,37,4`. Adversary messages use style 7,
mapping them to `15,86,90`. The `CONTINUE` caption is not generated text: it
is transparent-zero `STUFF.ART` frame 29, positioned by its signed origin over
the horizontal center of the panel.

If a dialogue command is reached while another modal message is active, it
suspends before consuming its `p` operand. After the modal state clears, the
same command is retried, consumes the text, and presents it. Confirmation by
Enter, Escape, or a primary click dismisses ordinary dialogue.

## Choices

A choice consists of an absolute `BIN` target and a text string. Opcode `45`
clears the list, `44` appends choices in display order, `13` can remove the
first target match, and `46` presents the menu. Selecting a choice clears the
modal state and resumes the suspended thread at that choice's target.

Keyboard Up and Down clamp at the first and last rows, visually identify the
current selection, and activate it with Enter. Pointer motion selects the
visible row under the pointer; a primary click activates that row. A click
outside the menu MUST NOT activate the previously selected row. Empty choice
lists MUST be treated as malformed content rather than leaving the player in
an inescapable modal screen.

Unselected rows use text style 1 (`1,7,3`), while the selected row uses style
2 (`1,37,4`). The `SELECT` caption is transparent-zero `STUFF.ART` frame 28,
not a host-font label. Its signed origin positions it beside the selected row.

## Study browser

The Study Bible is both a player reference (F1) and a gameplay answer screen.
It displays translated text-bank records and supports navigation among the
available record descriptors. A descriptor has a one-byte selector, component
references, a persistent state byte, and a span. The active bank contains no
more than 66 descriptors.

The standalone F1 view lets the player browse acquired or otherwise available
material and return without changing an encounter continuation. Encounter
study mode is configured by bytecode:

1. `15` directly selects an expected record, or `7D` selects a component and
   reads the expected selector from a script variable.
2. `4F` or `51` defines the success continuation, either a navigation node or
   a command target and thread.
3. `49` opens the browser and suspends the scene thread.
4. Choosing the expected descriptor takes the configured success path and
   sets flag `14` where the surrounding conversation uses result flags.
5. Leaving without the expected match sets flag `15` for those conversations
   and resumes their failure or retry path.

The browser clears both result flags before accepting encounter input. It MUST
compare stable record selectors, not translated display strings. This keeps
gameplay identical in every supported translation.

### DOS presentation

The Computer Bible is a full-screen 320-by-200 indexed modal. Opening it
clears the viewport to palette index zero and suppresses the scene and status
row. It is not a generic white panel drawn over the current scene. The modal
loads `BOOK.ART` (resource ID `0x239`) and draws its transparent-zero frames
with the current scene palette.

`BOOK.ART` contains the following zero-based frames:

| Frame | Descriptor `(x, y, w, h)` | Purpose |
|---:|---|---|
| 0 | `(28, 27, 266, 150)` | Complete open-book chassis and enabled controls |
| 1 | `(85, 162, 29, 12)` | Enabled Apply control |
| 2 | `(36, 26, 26, 12)` | Off control |
| 3 | `(34, 85, 13, 14)` | Enabled page-up control |
| 4 | `(34, 106, 13, 14)` | Enabled page-down control |
| 5 | `(34, 85, 13, 14)` | Disabled page-up control |
| 6 | `(34, 106, 13, 14)` | Disabled page-down control |
| 7 | `(85, 162, 29, 12)` | Disabled Apply control |

Frame 0 and the page and Apply overlays use caller anchor `(0,24)`. Frame 2
uses caller anchor `(9,24)`. The resulting logical bounds are `(28,51)` for
the chassis, `(45,50)` for Off, `(34,109)` and `(34,130)` for the arrows, and
`(85,186)` for Apply. The bottom of the chassis and controls is clipped by the
200-line viewport exactly as in the DOS renderer.

The acquired-reference list begins at `(52,70)`, contains 14 rows, and uses
an eight-pixel line pitch. Each reference is clipped to 100 logical pixels.
The selected row uses text style 5, whose font-atlas values `0,1,2` map to
palette indexes `0,64,70`; unselected rows use style 6, mapping them to
`0,32,37`. The selected citation is drawn at `(172,61)` with a 110-pixel
limit. Its verse begins at `(168,74)`, wraps to 114 logical pixels, and uses
style 5 with the same eight-pixel pitch. With no acquired records the right
page displays the executable's exact message `NO VERSES LOADED`; both page
arrows and Apply use their disabled artwork.

Up and Down move one acquired record and clamp at the ends. Page Up, Page
Down, and the two artwork arrows move by 14 acquired records. Enter or `A`
activates Apply only while an encounter has enabled Bible application; the F1
reference browser always displays disabled Apply artwork and cannot produce a
study answer. Escape, `O`, or a primary press on Off closes the modal. A
primary press on a reference row selects that row but does not apply it; a
separate press on enabled Apply is required. Page and Apply controls ignore
presses while disabled, and presses outside all authored bounds do nothing.

## Text expansion

Before display, the engine resolves the selected record/component, expands
the data-defined placeholders described in [Text resources](text.md), applies
the current translation, and wraps for the destination panel. Resource bytes
remain immutable; descriptor state and scene-local expanded strings are kept
separately except when a scene explicitly invokes the bytecode self-modifying
copy command.

Study choices and verse acquisitions update descriptor state through opcodes
`36`–`39`. The same state mechanism can represent an obtained verse, a
completed conversation step, or another text-related condition; the scene
program determines the meaning. Loading a new text bank or executing opcode
`88` clears all 66 state bytes as specified.

## Player-facing mechanics

Cybers confront Captain Bible with false statements. The player studies the
available Bible passages and selects the passage that answers the lie. Correct
study results advance dialogue, unlock doors, rescue victims, destroy pylons,
or enable combat actions depending on context. An incorrect record or leaving
the browser follows the scene-defined failure, retry, or faith-loss branch.

The engine MUST never infer correctness by wording, verse number, or locale.
Only selectors and continuations embedded in the resources define it.
