# Known Gaps and Evidence Boundaries

This book deliberately leaves fields unnamed when the available evidence does
not distinguish their semantics. The list below consolidates those boundaries
so an unresolved detail in one chapter is not mistaken for a contradiction in
another.

## Dynamic captures still wanted

- Capture focused keyboard/mouse input and normal save/quick-save writes with
  the DOS tracer or monitor, then connect them to the already named input and
  save functions.
- Capture the animation, action-target, and BIN-thread tables during a live
  combat encounter. Their static layouts are recovered, but the first attempted
  automated encounter capture stopped during a black transition in a loaded
  sound-driver segment.
- Exercise a representative screen from each major gameplay system while
  recording scene names, script state, and expected inspector output.
The existing startup trace, title/intro memory captures, live dialogue-choice
table, scene display records, framebuffer comparison, and decoded `D003` PCM
remain valid independent dynamic checks.

## Partially named runtime structures

- The auxiliary word at ABT offset `0x06` is consumed but unused by the game
  decoder. Its values are known across all resources; its producer-side meaning
  is not.
- The opcode-`0x02` 16-byte interactive/display records, the last two bytes of
  12-byte animation slots, and some animation mode transitions need finer
  field names.
- Conversation opcode `0x15` and several dialogue presentation states have
  visible formatting roles but no precise user-facing names.
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
26 BIN handlers, and 9 data symbols. It is not a claim that the executable has
only 140 functions. Rizin proposes roughly 340 candidates, including false
merges across data and jump tables; unsupported candidates remain unnamed.

Similarly, all 145 opcode operand layouts are known, but only handlers with
strong gameplay semantics receive descriptive executable symbols. The BIN
inspector uses structural `opcode_XX` names for the rest.

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

The append-only progress log is intentionally historical and can contain an
earlier hypothesis followed by its correction. Format and system chapters are
the current reference.
