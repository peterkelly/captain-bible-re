# Conversation Flow

## Overview

Conversations are ordinary BIN control flow layered over two reusable user
interfaces: a modal dialogue box and a text-choice menu. Scene scripts supply
speaker text inline, build choices as target/text pairs, and branch to the
target selected by the player. The same study-Bible screen used elsewhere in
the game can be opened from a conversation and returns success or failure
through state flags.

This system is distinct from the scene display list. Portraits and other
characters can be display objects, but conversation branches are absolute BIN
offsets and their transient menu records live in a separate table.

## Dialogue commands

Three commands share the handler at load offset `0x52A3`. The handler chooses
presentation parameters from the opcode and stores a far pointer to text in
the current BIN resource. The input layer then displays the modal box and
waits for Enter, Escape, or a click.

| Opcode | Operands | Current name | Corpus evidence |
|---:|---|---|---|
| `0x14` | `p` | `show_adversary_dialogue` | Ten uses, all in `FACE.BIN`, spoken by the Tower of Deception. |
| `0x48` | `p` | `show_character_dialogue` | 306 uses in 12 resources for the boss, victims, and allies. |
| `0x4E` | `p` | `show_captain_bible_dialogue` | 281 uses in 25 resources, normally Captain Bible's side of a conversation. |

Here `p` is either inline NUL-terminated CP437 text or byte `0xFF` followed by
an explicit 16-bit offset in the same BIN resource. `ROOM3.BIN` uses the
offset form twice, at commands `0x181C` and `0x18CE`, to reuse text beginning
at `0x0336`. Those are the only explicit string offsets in shipped code.

The handler has a deliberate retry path that reads no operand. If a modal
dialogue is already active, it suspends the command thread at the original
command offset. Once the modal state clears, re-execution consumes `p` and
continues. This no-read path is synchronization behavior, not an optional
text operand.

Opcode `0x4E` is a presentation channel rather than a hard type system. A few
scripts reuse it for system or caption text such as `Verse loaded: &` and the
credit screen. The speaker names describe the dominant, independently
labelled use rather than a restriction enforced by the interpreter.

The modal dialogue state word is at `DS:8934`. State 1 denotes a choice menu;
higher positive states select dialogue-box artwork and behavior. Function
`show_dialogue_message` at `0x2933` renders the frame, wraps the far text, and
runs the input loop while continuing to update scene animation.

## Choice table

Opcode `0x45` clears the current choices and resets dialogue state. Each
opcode `0x44` then appends one six-byte entry, and opcode `0x46` presents the
result. The runtime structure is:

| Location / offset | Size | Meaning |
|---|---:|---|
| `DS:B428` | 2 | Number of active choices. |
| `DS:B116 + 6*n + 0` | 2 | Absolute target offset in the current BIN resource. |
| `DS:B116 + 6*n + 2` | 2 | Text pointer offset. |
| `DS:B116 + 6*n + 4` | 2 | Text pointer segment. |

The choice text normally points directly into the loaded BIN member. Opcode
`0x13` removes the first entry whose target word matches its operand and
shifts the later six-byte records down. No recovered BIN resource uses
`0x13`, but its implementation is unambiguous.

The full command lifecycle is:

1. `clear_dialogue_choices` (`0x45`, handler `0x51B7`) sets the count and
   dialogue state to zero.
2. `add_dialogue_choice` (`0x44`, handler `0x51C6`) stores the absolute target
   and far string pointer, then increments the count.
3. `present_dialogue_choices` (`0x46`, handler `0x5257`) enters state 1 and
   suspends the current scene thread.
4. `select_from_text_menu` at `0x2556` draws the entries and returns the target
   word belonging to the chosen row.
5. `poll_input_event` writes that target to `DS:7CBA`. The resumed handler
   replaces the interpreter cursor with the target, so execution continues at
   the selected branch.

The corpus contains 40 choice definitions in six resources, 11 clear
commands in six resources, and 14 present commands in seven resources. Those
different totals reflect conditional paths and reuse of a previously built
menu; a linear listing must not assume that every definition belongs to one
runtime menu.

## BOSS.BIN example

The introductory conversation constructs one five-choice menu:

| Choice | Source | Target | Text |
|---:|---:|---:|---|
| 0 | `0x045C` | `0x0644` | `So what do I do when I get inside?` |
| 1 | `0x0482` | `0x07E8` | `Can I expect any resistance?` |
| 2 | `0x04A2` | `0x0751` | `What about the people inside?` |
| 3 | `0x04C3` | `0x0519` | `Should I expect any problems with my computer bible?` |
| 4 | `0x04FB` | `0x095C` | `OK!  I'd better go do it!` |

Each answer eventually jumps back to the menu-building region, except the
final choice, which advances the introductory sequence. This is ordinary BIN
branching; the menu itself does not retain a conversation graph.

## Study-Bible integration

Victim conversations repeatedly ask the player to select an appropriate
verse. Opcode `0x7D` reads a byte plus a script-variable operand and stores a
prompt component at `DS:0066` and the variable's current selector value at
`DS:0068`. The study screen's prompt builder at `0x446F` interprets the first
value as follows:

| Prompt value | Companion component shown |
|---:|---|
| `0x2A` (`*`) | Victim-conversation text. |
| `0x64` | `P` paraphrase text. |
| other nonzero | `L` cyber-lie text. |

Opcode `0x49` sets the study request at `DS:79F0` and suspends the current
thread. The main game loop clears the request and calls
`handle_study_bible_request` at `0x834E`, which invokes the full study browser
at `0x1C88`. The browser clears state flags `0x14` and `0x15` before input.
Selecting the expected descriptor sets flag `0x14`; leaving without that
match sets flag `0x15`. Scripts branch on those flags after opcode `0x72`
suspends the resumed thread once more.

For example, `NAGE.BIN` sets variable 28 to a text-record selector, executes
`configure_study_prompt 0x2A, var[28]`, requests the study screen, and then
branches to success, rejection, or departure paths according to flags
`0x14` and `0x15`. This ties the conversation graph directly to the text
descriptors and companion `*` records documented in the text-format chapter.

## QEMU validation

A visible, silent `./run.sh --trace-dos` session was advanced from the title
screen to the BOSS conversation. At the five-choice menu, the stable game data
segment was `14E1`. The one-megabyte physical-memory capture therefore placed
the count at physical `0x20238` and the table at physical `0x1FF26`.

The live count was five. All five records contained the exact static target
words above and far pointers into `BOSS.BIN` at `4C13:045F`, `4C13:0485`,
`4C13:04A5`, `4C13:04C6`, and `4C13:04FE`. Dereferencing those pointers
produced the five visible menu strings byte for byte.

Before selection, `DS:8934` was 1 and `DS:7CBA` was zero. Selecting the final
row changed `DS:7CBA` to `0x095C`; the next visible dialogue was `Before you
go, I think that we should pray.`, exactly the opcode-`0x48` string at target
`0x095C`. The resulting dialogue state was 2. QEMU was then stopped through
its monitor.

The ignored evidence files are under `build/qemu-trace/`, including
`conversation-menu2.png`, `conversation-menu2-physical-1m.bin`,
`conversation-selected.png`, and
`conversation-selected-physical-1m.bin`.

## Inspection

The ordinary BIN listing now uses semantic names for the recovered dialogue,
choice, study-request, and thread-suspension commands. Add `--choices` for a
compact linear inventory of every opcode-`0x44` definition:

```sh
tools/inspect_bin.py build/dd1/all/327_BOSS.BIN --choices
```

The summary prints source offset, target offset, and text. It explicitly warns
that branches can change the menu seen at runtime.

## Remaining boundaries

- The exact formatting roles of every dialogue state and frame are not yet
  named.
- Conversation choices and verse answers alter progression flags, but they do
  not expose a separate enemy-health, hit-test, or combat-entity structure.

## Relevant executable routines

| Load offset | Current name |
|---:|---|
| `0x1C88` | `show_study_bible` |
| `0x2556` | `select_from_text_menu` |
| `0x2933` | `show_dialogue_message` |
| `0x446F` | `render_study_prompt` |
| `0x4672` | Configure-study-prompt handler. |
| `0x51B7` | Clear dialogue-choice handler. |
| `0x51C6` | Add dialogue-choice handler. |
| `0x51FF` | Remove dialogue-choice handler. |
| `0x5257` | Present dialogue-choice handler. |
| `0x52A3` | Shared dialogue-message handler. |
| `0x5351` | Study-Bible request handler. |
| `0x5357` | Suspend-scene-thread handler. |
| `0x7BED` | `poll_input_event` |
| `0x834E` | `handle_study_bible_request` |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
