# Known Gaps and Evidence Boundaries

This book deliberately leaves fields unnamed when the available evidence does
not distinguish their semantics. The list below consolidates those boundaries
so an unresolved detail in one chapter is not mistaken for a contradiction in
another.

## Dynamic-capture boundary

Focused keyboard/mouse input, quick and normal saves, representative screens,
and all three COMBAT1 runtime table families now have preserved dynamic
evidence. The combat capture deliberately used a saved-scene patch to enter
COMBAT1, so it validates loaded runtime structures and action execution but not
the natural map-to-encounter transition or an ordinary outcome. The startup
trace, title/intro memory captures, live dialogue-choice table, scene display
records, framebuffer comparison, and decoded `D003` PCM remain independent
dynamic checks.

## Partially named runtime structures

- The auxiliary word at ABT offset `0x06` is consumed but unused by the game
  decoder. Its values are known across all resources; its producer-side meaning
  is not.
- The opcode-`0x02` 16-byte interactive/display records, the last two bytes of
  12-byte animation slots, and some animation mode transitions need finer
  field names.
- The three bytes written by dialogue-presentation opcodes `0x5C` and `0x5D`
  are assigned to their two channels, but their finer layout roles remain
  deliberately unnamed.
- Combat's `POWER` re-entry exists and is decoded, but its complete caller path
  has not been isolated. Randomized branches are not all labeled by rendered
  enemy phase.
- Supplied saves expose 275 varying byte positions. Known state, flags,
  descriptors, and maps are decoded; pairwise variation alone cannot assign a
  gameplay meaning to every remaining byte.

## Conservative world-map names

All room classes, entrances, Cybers, stations, locks, Spider triggers, cleared
encounters, and exits used by recovered gameplay are named. Connected hallway
kinds `0xC`, `0xD`, and `0xF` remain numeric because their exact environmental
presentation has not been proven. Parameters A and B are named only in contexts
where script transitions or map rendering establish their roles.

## Static-analysis coverage

The checked catalog contains every project-assigned Rizin name: 140 functions,
134 distinct BIN handler addresses, and 9 data symbols. It is not a claim that
the executable has only 140 functions. Rizin proposes roughly 340 candidates,
including false merges across data and jump tables; unsupported candidates
remain unnamed.

All 145 opcode operand layouts and dispatch effects now have inspector names.
Twenty-three values do not occur in shipped scripts, including thirteen from
the final unnamed-handler pass, so their names stay close to directly observed
state writes and callees. The finer gameplay role of unused opcode `0x1B`'s
motion-transition latch and unused modal-menu opcode `0x47` remain evidence
boundaries rather than reasons to leave their handlers structurally unnamed.

## Resolved former gaps

Several statements in early progress entries describe questions that later
work answered. Current chapters supersede those chronological notes:

- `DDLA` through `DDLG` and `DDLR` are tagged companion text streams joined to
  extensionless verse indexes inside `DD1.DAT`.
- `POWER.BIN` is the in-combat study interface, not a game-over resource.
- `CP2.BIN` has a 256-byte 16-node Unibot graph trailer beginning at `0x1D55`.
- Flags `0x42..0x48` are rescued crew present for the Unibot mission, and
  variables 56 through 62 are the seven energy-pylon results.
- All 34 game-side interrupt-`66h` sites are assigned DIGPAK/MIDPAK services,
  and `SOUND.4` is a fully validated 181-entry AIL OPL timbre library.
- Hall kinds for all seven Cybers, the hidden Spider, stations, cleared combat,
  and exits are correlated with their scripts and manual identities.
- BIOS keyboard and mouse polling are captured at the named game call sites;
  F10 and normal menu saves are joined to their exact guest writes.
- The live COMBAT1 action table matches all four static targets, and all 33
  captured animation records match their static first-step and interval fields.
- Representative startup, story, exploration, study, map, faith, menu, save,
  combat, and defeat screens were exercised in visible, silent QEMU.
- The complete dispatch audit establishes 145 opcode values, 134 distinct
  handlers, and exact operand-reader paths. Pointer-capable strings are now
  distinguished from inline-only names.
- Opcode `0x8D` constructs the active player's save-index filename. Its only
  shipped use tests `.SV0`, and its branch target equals its fallthrough.

The append-only progress log is intentionally historical and can contain an
earlier hypothesis followed by its correction. Format and system chapters are
the current reference.
