# Text, Verses, and the Study Bible

## Text architecture

Gameplay text is divided between translation-specific verse indexes inside
`DD1.DAT` and translation-independent external companion files. The engine
joins them into logical text records when a bank is loaded.

Four translations are identified by one letter:

| Letter | Index | Translation |
|---|---:|---|
| `K` | 0 | King James Version |
| `N` | 1 | New International Version |
| `R` | 2 | Revised Standard Version |
| `T` | 3 | The Living Bible |

`L` MAY be accepted as an alias for translation index 3 in command-line
configuration. Text is CP437 and NUL-terminated unless a byte span supplies an
explicit boundary.

## Banks

Bank letters are `A` through `G` and `R`. An extensionless archive name joins
translation and bank, for example `NA`. The companion is external file
`DDL<bank>`, for example `DDLA`.

There are 319 logical verse records per translation:

| Bank | Records | Companion length |
|---|---:|---:|
| A | 47 | 10,065 |
| B | 40 | 8,253 |
| C | 46 | 4,020 |
| D | 46 | 14,973 |
| E | 42 | 10,489 |
| F | 46 | 10,257 |
| G | 44 | 9,993 |
| R | 8 | 696 |

## Verse-index format

Each ordinary record is:

| Relative offset | Size | Meaning |
|---:|---:|---|
| `+0` | 1 | Nonzero selector used by scene logic |
| `+1` | 2 | Offset into the companion file |
| `+3` | variable | NUL-terminated `citation|verse` text |

The final record is only a zero selector plus a terminal companion offset. The
terminal offset MUST equal companion-file length. Companion offsets are
nondecreasing; equal offsets represent records with no companion components.

The text before `|` is the citation and the text after it is the verse. The
selector is a lookup key, not a component type. Selectors `0xE0` and above are
mature-topic records and are hidden when the no-mature policy is active.

## Companion format

The companion is a sequence of tagged NUL-terminated strings without a header:

| Tag | Meaning |
|---|---|
| `L` | Cyber lie |
| `P` | Paraphrase or lock prompt |
| `W` | Wrong guess response |
| `C` | Correct guess response |
| `E` | Explanation of the correct guess |
| `*` | Conversation with a victim |
| `M` | Numeric or internal metadata |

For one verse record, its companion span begins at its stored offset and ends
at the next record's offset. Parse tagged strings only inside that span. A span
may contain repeated tags. Bank F has a 26-byte `E` preamble before its first
indexed span; it is not associated with a verse.

## Runtime records

Loading a bank creates up to 66 runtime descriptors. A clean logical
descriptor contains:

- the citation and verse string;
- selector byte;
- companion offset and span;
- parsed tagged components; and
- one persistent state byte.

The state byte persists while that bank is active and through checkpoint
save/restore. Requesting the already active bank leaves its descriptors alone.
Loading a different bank rebuilds the descriptor set and clears all 66 state
bytes; restoring a checkpoint rebuilds its saved bank and reapplies the saved
state bytes. Scene commands find a descriptor by selector, set or clear its
state, branch on it, or copy a selected component into mutable scene memory.

The mutable-memory copy command accepts more component selectors than the
interactive prompt mapping. `V` copies `citation - verse`; a byte from 0
through 9 copies that zero-based `W` occurrence; and ordinary tag bytes such
as `C` or `E` copy the first matching component. These textual forms include a
terminating NUL. Selector `X` instead writes a shuffled byte array containing
`0..W-count-1` plus literal `C`, stores its length in variable 27, and does not
append a NUL. The original performs 20 random swaps; the clean-room random
algorithm may differ as allowed by the compatibility boundaries. Successful
copying sets state flag `22`; a missing record or component clears it and
leaves the destination bytes unchanged.

## Computer Bible

The F1 interface displays descriptors whose state marks the verse as obtained.
References are ordered in Bible order. Selecting a reference shows its verse.
Page controls appear when the list exceeds one screen.

Apply is available only when a scene has configured an expected selector and
component. Applying the expected descriptor sets state flag `0x14`. Leaving
without that match sets flag `0x15`. Both flags are cleared before each
interactive study request.

The expected record can also carry one success continuation. Opcode `4F`
associates it with a navigation node, while opcode `51` associates it with a
BIN target and scheduler thread. Applying the matching record starts that
movement or command stream after the modal browser closes. Opcode `15`
selects a record while clearing both continuations, and opcode `50` clears the
active selection. A host must not merely set the result flag and discard these
configured continuations.

## Prompt component selection

Scene opcode `0x7D` stores a prompt byte and reads the expected selector from
the variable encoded by its word operand. The prompt byte chooses:

| Value | Component shown |
|---:|---|
| `0x2A` (`*`) | Victim-conversation text |
| `0x64` | `P` paraphrase text |
| other nonzero | `L` Cyber-lie text |

The study screen compares by descriptor selector. It does not compare rendered
text strings.

## Display substitutions

Dialogue and study strings may contain placeholders expanded from the selected
text descriptor. The scene chooses the active descriptor before display. A
compatible implementation MUST preserve the distinction between verse text,
citations, and companion components and must apply substitutions before line
wrapping.
