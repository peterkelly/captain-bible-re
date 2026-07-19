# Dialogue and Bible study

## Dialogue presentations

The game has three dialogue channels:

- adversary dialogue (`14`), used for a Cyber's lie;
- character dialogue (`48`), used for victims, bosses, and other characters;
- Captain Bible dialogue (`4E`), also used for some narration or captions.

Each displays translated CP437 text in a modal panel using its configured
three-byte presentation tuple. The tuple affects visual presentation but its
internal subdivision is not a cross-platform API. A compatible engine MUST
keep the three channels visually distinguishable where the shipped resources
configure them and MUST preserve their command timing.

If a dialogue command is reached while another modal message is active, it
suspends before consuming its `p` operand. After the modal state clears, the
same command is retried, consumes the text, and presents it. Confirmation by
Enter or primary click dismisses ordinary dialogue.

## Choices

A choice consists of an absolute `BIN` target and a text string. Opcode `45`
clears the list, `44` appends choices in display order, `13` can remove the
first target match, and `46` presents the menu. Selecting a choice clears the
modal state and resumes the suspended thread at that choice's target.

Keyboard navigation MUST wrap or clamp consistently within the list, visually
identify the current selection, and activate it with Enter. Mouse activation
uses the visible choice rows. Empty choice lists MUST be treated as malformed
content rather than leaving the player in an inescapable modal screen.

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
