# Scene Bytecode

## Overview

The 62 expanded `BIN` members are the game's scene programs. Most are pure
bytecode streams with no header. They select art and palettes, start music,
change scenes, update variables, branch, call subroutines, and coordinate
animation. The executable's interpreter dispatches opcodes `0x01` through
`0x91` through a 145-entry near-pointer table at load offset `0x59AB`.

The operand layout and an evidence-based handler name have now been recovered
for every dispatched opcode. Linear decoding identifies 25,829 commands in 64
code regions and uses 122 of the 145 possible opcodes. Names for commands that
do not occur in the shipped scripts describe their direct engine effects rather
than claiming an unobserved gameplay role.

## Runtime model

`initialize_scene` at `0x6631` appends `.BIN` to a scene base name, loads that
archive member into far memory, installs its base and initial cursor, resets
scene-thread state, and calls `execute_bin_commands` at `0x451B` with file
offset zero. Later, `update_scene_threads` at `0x7997` resumes active command
streams by passing their saved file offsets back to the same interpreter.

Four words in the data segment hold the current input state:

| DS offset | Runtime example | Interpretation |
|---:|---:|---|
| `0x00F6` | `0x004B` | Current file-relative bytecode offset. |
| `0x00F8` | `0x4C13` | Segment containing the current bytecode cursor. |
| `0x00FA` | `0x0000` | Offset of the loaded resource's far-memory base. |
| `0x00FC` | `0x4C13` | Segment containing the resource base. |

The interpreter sets its cursor to `base + requested_offset`, fetches one
byte, converts opcode 1 to dispatch index 0, range-checks through `0x91`, and
calls the corresponding handler. Branch and call targets are absolute offsets
within the expanded `BIN` member, rather than relative displacements.

Three shared operand readers make the encoding unambiguous:

| Load offset | Current name | Operation |
|---:|---|---|
| `0x3A1E` | `bin_read_u8` | Read one byte and advance the far cursor. |
| `0x3A30` | `bin_read_u16` | Read one little-endian word. |
| `0x3A64` | `bin_read_cstring_offset` | Read a NUL-terminated string and return its base-relative offset; byte `0xFF` escapes to an explicit 16-bit offset. |

## Operand schema

The decoder records each opcode with a compact schema:

| Marker | Encoding |
|---|---|
| `B` | Unsigned byte. |
| `H` | Unsigned little-endian 16-bit word. |
| `z` | NUL-terminated CP437 string, or `FF` plus an explicit 16-bit resource-string offset. |
| `9` | Opaque nine-byte animation record skipped by opcode `0x07`. |
| `s` | An additional word only when the preceding `H`, interpreted as signed, is negative. |

The conditional `BHs` form is used by opcodes `0x11`, `0x12`, and `0x17`
through `0x1A`. For example, bytes `11 01 F8 FF E6 01` contain byte 1, signed
word -8, and therefore the extra word `0x01E6`.

The complete machine-readable table is `OPCODE_SCHEMAS` in
`tools/inspect_bin.py`. It contains one entry for every value from `0x01`
through `0x91`; tests extract the resources directly from `CB/DD1.DAT` and
exercise every known code region against that table.

## Identified commands

These handler meanings have direct static support from their callees or clear
control-flow behavior:

| Opcode | Operands | Current name | Evidence |
|---:|---|---|---|
| `0x01` | `z` | `load_art` | Passes the name to `load_art_resource`, which appends `.ART`. |
| `0x05` | none | `return_minus_one` | Terminates interpretation with return value -1. |
| `0x02` | `BHHH` | `create_scene_thread` | Initializes a thread slot and appends a type-`0x02` display record. |
| `0x03` | `BBHHB` | `add_native_scale_display_object` | Appends a directly rendered object with implicit scale `0x0100`. |
| `0x04` / `0x43` | `BBHHHB` | `add_scaled_display_object` | Appends a directly rendered object with frame, ART slot, X, Y, scale, and flags. |
| `0x06` | `H` | `begin_animation_sequence` | Creates animation state and appends a type-`0x06` display record. |
| `0x07` | `9` | `animation_step` | Advances over a fixed nine-byte step retained for later animation updates. |
| `0x08` / `0x5F` | `BB` / `BBB` | start animation | Starts an animation without / with an explicit linked slot. |
| `0x09` | `B` | `stop_animation` | Stops an animation and releases its render slot. |
| `0x0D` | `zz` | `change_scene` | Selects a new scene and secondary segment name. |
| `0x0F` | `H` | `adjust_thread_delay` | Updates the current command thread's wait value. |
| `0x13` | `H` | `remove_dialogue_choice` | Removes the first six-byte choice record with the matching target. |
| `0x14` | `z` | `show_adversary_dialogue` | Uses the adversary presentation channel; all ten uses are in `FACE.BIN`. |
| `0x1E` | `HH` | `copy_variable` | Copies one signed script-variable word to another. |
| `0x1F` | `HH` | `set_variable` | Stores an immediate in a script variable. |
| `0x20` | `HH` | `jump_if_zero` | Selects an absolute target when a variable is zero. |
| `0x21` | `HH` | `jump_if_nonzero` | Selects an absolute target when a variable is nonzero. |
| `0x22`–`0x29` | `HHH` | variable comparisons | Compare variable/variable or variable/immediate pairs and conditionally jump. |
| `0x2A`–`0x31` | `HH` | variable arithmetic | Add, subtract, multiply, or divide a destination by a variable or immediate. |
| `0x32` | `H` | `increment_variable` | Increments a numbered variable. |
| `0x33` | `H` | `decrement_variable` | Decrements a numbered variable. |
| `0x34` | `H` | `call` | Saves a return offset and jumps to an absolute target. |
| `0x35` | none | `return` | Resumes the saved bytecode return offset. |
| `0x36` / `0x37` | `B` | set/clear text-record state | Mutates persistent descriptor byte `+4` selected by record identifier. |
| `0x38` / `0x39` | `BH` | branch on text-record state | Selects a target when a record state is set / clear. |
| `0x3A` | `HHHz` | `add_action_target` | Appends a selectable screen coordinate, BIN target, and label selector. |
| `0x3B` / `0x3C` | `B` | enable/disable action target | Changes one action record's active byte. |
| `0x3D` | `H` | `jump` | Replaces the cursor with an absolute file offset. |
| `0x3E` | `BH` | `start_scene_thread_at` | Activates a BIN scheduler slot at an absolute target. |
| `0x3F` | `B` | `wait_for_animation` | Suspends the current thread while an animation is active. |
| `0x41` / `0x42` | none | enable/disable action selection | Controls screen-action input globally. |
| `0x44` | `Hz` | `add_dialogue_choice` | Appends an absolute target and far text pointer to the choice table. |
| `0x45` | none | `clear_dialogue_choices` | Clears the choice count and dialogue state. |
| `0x46` | none | `present_dialogue_choices` | Suspends the thread until the selected choice supplies a new BIN target. |
| `0x48` | `z` | `show_character_dialogue` | Presents the character/boss/victim dialogue channel. |
| `0x49` | none | `request_study_bible` | Requests the modal study interface and suspends the current thread. |
| `0x4D` | `z` | `load_palette` | Calls `load_palette_resource`, which appends `.PAL`. |
| `0x4E` | `z` | `show_captain_bible_dialogue` | Presents Captain Bible's dialogue channel, also reused for some captions. |
| `0x52` | `B` | `play_music` | Builds `MUS###` or `IBM###` and loads an XMI member. |
| `0x55` | none | `snapshot_state` | Copies the live state into a retained buffer. |
| `0x57` | `BH` | `play_sound_effect` | Builds `D###.ABT`, decodes it, and starts playback at the supplied rate. |
| `0x58` | none | `stop_sound_effect` | Stops active digital playback and releases its PCM buffer. |
| `0x59` | none | `wait_for_sound_effect` | Suspends until digital playback or its simulated timer completes. |
| `0x60` | none | `nop` | Continues directly to the next command. |
| `0x61` | `B` | `stop_scene_thread` | Clears one BIN scheduler slot's active byte. |
| `0x65` | `BB` | `clear_display_object_frames` | Sets the frame byte to zero across a consecutive display-record range. |
| `0x66` | `BBBB` | `advance_display_object_frames` | Increments and range-wraps frame bytes across consecutive records. |
| `0x6C` | `HHHH` | `rotate_palette_range` | Advances a script-variable phase by a signed step, wraps it within an inclusive palette-index range, and rotates that range's mapping. |
| `0x6D` | `z` | `load_palette` | Uses the same palette-loading path as `0x4D`. |
| `0x70` | none | `unload_last_art` | Releases the most recently loaded art slot. |
| `0x72` | none | `suspend_scene_thread` | Marks the current command thread suspended until the input/UI path resumes it. |
| `0x73` / `0x74` | `BH` | branch on state flag | Selects a target when a boolean state flag is clear / set. |
| `0x75` / `0x76` | `B` | clear/set state flag | Mutates one identifier in the 128-bit state bank. |
| `0x77` | none | `process_current_map_cell` | Calls the current-cell handler, which consults the cell and its neighbors. |
| `0x78` | `B` | `load_map` | Combines a level letter with the current `E`/`N`/`D` difficulty code and loads a `.MAP` member. |
| `0x7A` | `HH` | `patch_bin_byte_from_variable` | Writes the low byte of a script variable to an absolute offset in the current BIN resource. |
| `0x7B` | `H` | `set_current_map_cell_kind` | Replaces the low nibble of the current cell from a script variable. |
| `0x7C` | `H` | `set_current_map_cell_parameter_a` | Writes the current cell's second byte from a script variable. |
| `0x7D` | `BH` | `configure_study_prompt` | Selects a companion-text component and record selector for the next study screen. |
| `0x7E` | none | `blackout_palette` | Starts an immediate black palette effect before a scene transition. |
| `0x7F` | `H` | `set_current_map_cell_parameter_b` | Writes the current cell's third byte from a script variable. |
| `0x80` | `BH` | `jump_if_animation_active` | Selects a target when an animation state byte is nonzero. |
| `0x81` | `H` | `reduce_faith` | Subtracts a difficulty-scaled immediate from faith unless no-combat mode is active. |
| `0x82` | `HH` | `set_variable_random_modulo` | Stores a pseudorandom remainder in a script variable. |
| `0x85` / `0x86` | `B` | hide/show display object | Sets / clears the high hidden bit in a display record's ART-slot byte. |
| `0x87` | none | `normalize_map_cells` | Applies recovered location-kind and parameter transitions across the grid. |
| `0x88` | none | `clear_text_record_states` | Clears persistent byte `+4` in all 66 text descriptors. |
| `0x89` | none | `mark_current_map_cell_explored` | Sets the current X bit in the current Y exploration row. |
| `0x8E` | none | `sync_current_cell_flags_23_to_27` | Copies five bits from a 16-by-16 current-cell table into state flags `0x23` through `0x27`. |
| `0x8F` / `0x90` | `HH` | variable bitwise AND | ANDs a destination with a variable / immediate. |

### Formerly structural commands

The final unnamed-handler pass connected the remaining 51 opcode values to
their consumers. Thirteen of these values never occur in the shipped command
regions; their rows are marked **unused** and rely on static handler behavior.

| Opcode | Operands | Recovered name | Operation |
|---:|---|---|---|
| `0x0A` | none | `wait_for_scene_thread_movement` | Yields the current BIN thread until primary movement state is 0 or 2. |
| `0x0B` | `BB` | `add_navigation_edge` | Appends an undirected two-node edge used by the recursive route finder. |
| `0x0C` | `BBz` | `add_scene_entry` | Associates an entry/segment string with the two initial navigation-node bytes used after `change_scene`. |
| `0x0E`, `0x4A`, `0x4B`, `0x56` | none | `nop` | **Unused.** All four jump-table entries point at the interpreter's continue loop. |
| `0x10` | `BHHz` | `configure_scene_thread_action` | Gives a scene thread selector X/Y coordinates and an inline action label. |
| `0x11` | `BHs` | `add_navigation_arrival_handler` | Maps a destination node to a BIN target and optional explicit thread slot. |
| `0x12` | `BHs` | `add_navigation_departure_handler` | Maps a source node to a BIN target and optional explicit thread slot. |
| `0x15` | `B` | `select_study_record` | Selects the text descriptor expanded by study placeholders and clears both success continuations. |
| `0x16` | `HHH` | `set_palette_mapping_range_from_variable` | Fills an inclusive palette-index mapping range with one script-variable value and schedules an update. |
| `0x17` | `BHs` | `add_reverse_edge_departure_handler` | Adds a callback for starting traversal opposite an edge's stored order. |
| `0x18` | `BHs` | `add_forward_edge_departure_handler` | **Unused.** Adds the corresponding forward-departure callback. |
| `0x19` | `BHs` | `add_forward_edge_arrival_handler` | Adds a callback for completing traversal in stored edge order. |
| `0x1A` | `BHs` | `add_reverse_edge_arrival_handler` | Adds a callback for completing reverse traversal. |
| `0x1B` | `H` | `prime_primary_scene_thread_timer` | **Unused.** Stores the negated operand in the primary motion timer and raises its completion signal. |
| `0x1C`, `0x1D` | `B` | enable/disable scene-thread action | Enables or disables one scene thread as an input selector. |
| `0x40` | `B` | `set_scene_thread_motion_state` | Writes the current thread's motion state; state 2 immediately runs the scene-motion update. |
| `0x47` | `B` | `set_modal_menu_selection` | **Unused.** Seeds the selection consumed and reset by the modal text-menu path. |
| `0x4C` | `B` | `fill_screen` | Fills the complete 320-by-200 framebuffer with one palette index. |
| `0x4F` | `BB` | `configure_study_navigation_success` | **Unused.** Selects a study record and the navigation node entered after success. |
| `0x50` | none | `clear_study_record_selection` | **Unused.** Clears both active study-record selector words. |
| `0x51` | `BHB` | `configure_study_thread_success` | Selects a study record plus the BIN target and thread slot started after success. |
| `0x53` | `B` | `set_scene_thread_origin` | Initializes the primary navigation object's current and previous node. |
| `0x54` | `B` | `move_scene_thread_to` | Requests movement to a navigation node, including path search and animation setup. |
| `0x5A` | `H` | `jump_if_digital_audio_fallback` | Tests the fallback-audio flag and conditionally jumps; contradictory hardware guards make the shipped path unable to take the branch. |
| `0x5B` | `B` | `set_scene_thread_direction` | Selects one of four movement orientations and its sprite/render offset. |
| `0x5C`, `0x5D` | `BBB` | configure dialogue presentation | Writes the three presentation fields used by Captain Bible / character dialogue channels. |
| `0x5E` | `H` | `set_deferred_scene_thread_target` | **Unused.** Sets a target that the main loop later starts in scheduler slot 2. |
| `0x62`, `0x63` | `H` | store mouse X/Y | Stores the current mouse coordinate in the selected script variable. |
| `0x64` | `H` | `jump_if_confirm_pressed` | Consumes the Enter-or-click latch and jumps to an absolute target when set. |
| `0x67` | none | `request_restore_saved_game` | Leaves the scene loop through mode 2, which restores retained save buffers. |
| `0x68` | `H` | `wrap_variable_1280` | Wraps a script variable by 1,280 into the engine's signed coordinate interval. |
| `0x69` | `HH` | `load_bin_word` | Loads a little-endian word at an immediate current-BIN offset into a variable. |
| `0x6A` | `HH` | `patch_bin_word_from_variable` | Writes a variable word to an immediate current-BIN offset. |
| `0x6B` | `B` | `load_text_bank` | Replaces the active companion-text bank and clears all 66 descriptors. |
| `0x6E` | `B` | `start_primary_scene_thread_overlay` | **Unused.** Loads and starts a resource-driven transient overlay for scene thread zero. |
| `0x6F` | none | `wait_for_primary_scene_thread_overlay` | **Unused.** Yields while that transient overlay remains active. |
| `0x71` | `HH` | `load_bin_word_indirect` | Uses one variable as the BIN offset, loads a word, and stores it in another variable. |
| `0x79` | none | `clear_navigation_handlers` | Clears scene-entry, edge-transition, arrival, and departure callback counts. |
| `0x83` | `HBH` | `copy_text_record_component_to_bin` | Selects a text record through a variable and copies one component to an immediate BIN offset. |
| `0x84` | `HH` | `load_bin_byte` | Loads a byte at an immediate current-BIN offset into a variable. |
| `0x8A` | `BH` | `jump_if_animation_finished` | Jumps when the selected animation is in state 0, 5, or 6. |
| `0x8B` | none | `consume_random_text_record` | **Unused.** When variable zero is 2, clears one random available text descriptor and starts a 3,000-tick timer. |
| `0x8C` | `H` | `jump_if_no_combat` | Jumps when the installation's `SOUND.5` no-combat flag is set. |
| `0x8D` | `H` | `jump_if_file_missing` | Constructs and opens a runtime filename, jumping when `fopen` fails. |
| `0x91` | `HH` | `set_variable_current_cell_byte_modulo` | Stores the current map cell's first byte modulo the immediate divisor in a variable. |

Opcode `0x69` was previously recorded as a one-word instruction. Its handler
actually reads an immediate BIN offset and a destination-variable offset. In
`CP2.BIN`, the second word's low byte happened to be opcode `0x40`, so all
streams still decoded while eleven destination operands appeared as phantom
commands. Correcting the schema reduces the corpus total from 25,840 to 25,829
without changing the set of 122 opcodes genuinely used by shipped scripts.

Opcode `0x7A` deliberately modifies the loaded BIN buffer. Combat exits use
it to replace the `C` in inline `CHAL` from the current level-letter
variable; `POWER.BIN` replaces the digit in `combat1` from the selected
combat number. It is therefore a resource-name templating mechanism rather
than a persistent-state write.

Opcode `0x6C` calls `rotate_palette_range` at `0xB5A8`. Its operands are
inclusive minimum, inclusive maximum, signed step, and phase variable. The
helper wraps the updated phase, fills the palette-index mapping across the
range, and schedules a palette update. Opcode `0x7E` calls
`start_palette_blackout` at `0x1B6C`; the next palette update writes an all
black palette and counts down the effect state.

The suffix strings are present in the executable data segment and were also
checked in the QEMU process image: `.PAL` at `DS:0434`, `.ART` at `DS:0490`,
and `.BIN` at `DS:0721`. This corrects an early interpretation of bytes such
as `4D 54 49 54 4C 45 00` as the string `MTITLE`: byte `0x4D` is actually the
palette opcode followed by the string `TITLE`.

## Startup programs

The QEMU DOS trace and archive directory give this resource-load sequence:

```text
LOGO.BIN -> LOGO.PAL -> LOGO.ART -> D003.ABT
TITLE.BIN -> TITLE.PAL -> TITLE.ART -> TITLE2.ART -> MUS001.XMI
INTRO.BIN -> INTRO.ART
```

The scripts involved decode completely:

| Resource | Expanded bytes | Commands |
|---|---:|---:|
| `LOGO.BIN` | 640 | 114 |
| `TITLE.BIN` | 436 | 80 |
| `INTRO.BIN` | 184 | 39 |
| `MENU.BIN` | 2,004 | 99 |

`INTRO.BIN` begins by setting two small state values, loading `TITLE.PAL`,
loading `INTRO.ART`, and drawing the opening sequence. Opcode `0x52` selects
music index 1, which produces `MUS001.XMI`. At file offset `0x009A`, opcode
`0x0D` carries strings `dome` and `seg` to enter the first gameplay scene.

The runtime dump contains all 184 `INTRO.BIN` bytes at physical address
`0x4C130`. The base pointer `4C13:0000` appears at physical address `0x14F0A`,
stored as offset word `0000` at `DS:00FA` and segment word `4C13` at
`DS:00FC`. The live cursor is `4C13:004B`; resource offset
`0x004B` begins opcode `0x42` and is exactly the boundary after the preceding
`return_minus_one` command. This ties the static decoder's command boundaries
to live interpreter state.

## Mixed code and data

Sixty members decode linearly from byte zero through end of file. Two members
contain non-code regions:

- `CP2.BIN` has commands at `0x0000..0x1D54`, followed by a 256-byte
  structured data trailer at `0x1D55..0x1E54`. It contains a 16-node
  four-heading adjacency table, node types, transition values, and lower-right
  map coordinates. The Unibot chapter decodes every entry.
- `ROOM3.BIN` has command regions `0x0000..0x0336`,
  `0x0C96..0x1754`, and `0x1768..0x19DB`. A 2,400-byte zero-filled block and
  a 20-byte zero-filled block separate them.

Opcode zero is invalid. The decoder deliberately reports it instead of
guessing that arbitrary padding or embedded tables are executable commands.
The later `ROOM3.BIN` entry points are therefore decoded explicitly rather
than reached by a single linear sweep.

## Inspection tool

After extracting the archive, inspect a complete stream with:

```sh
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN
```

Use explicit bounds for embedded regions:

```sh
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x0c96 --limit 0x1754
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x1768
tools/inspect_unibot.py build/dd1/all/315_CP2.BIN
```

Output includes the file-offset range, opcode, current semantic name, and
typed operands. Variable operands show both their word index and encoded byte
offset, with recovered names such as `var[21:faith]@0x002a`. Other words with
their high bit set are displayed in both unsigned hexadecimal and signed
decimal forms. Every dispatched opcode now has a name; low-level names for
unused commands deliberately describe state changes rather than inferred UI.

Add `--objects` to append a linear summary of commands which define display
records, `--choices` to inventory dialogue target/text pairs, or
`--animations --actions` to inventory animation sequences and selectable
screen targets. Action summaries name the four combat selectors and the hall
selectors for movement, Confront Cyber, Unlock, and Get Verse. The
[scene-display-object chapter](scene-objects.md) documents the ten-byte
runtime record, while the [conversation-flow chapter](conversation-flow.md)
documents the six-byte choice table. The
[combat-runtime chapter](combat-runtime.md) documents animation slots, action
targets, and the BIN scheduler; the [world-map chapter](world-maps.md)
correlates the hall actions with map-cell features. These summaries warn that
branches can change which definitions execute.

## Executable routines

| Load offset | Current name |
|---:|---|
| `0x034F` | `load_map_resource` |
| `0x0457` | `normalize_map_cells` |
| `0x075F` | `show_map_screen` |
| `0x0C6C` | `process_current_map_cell` |
| `0x1B6C` | `start_palette_blackout` |
| `0x1C88` | `show_study_bible` |
| `0x2556` | `select_from_text_menu` |
| `0x2933` | `show_dialogue_message` |
| `0x3AD2` | `reset_scene_display_records` |
| `0x3AFF` | `render_scene_display_records` |
| `0x3B9B` | `resolve_animation_transform` |
| `0x3D08` | `render_animation_slot` |
| `0x3DA8` | `update_animation_slots` |
| `0x3F59` | `start_animation_slot` |
| `0x3FDF` | `stop_animation_slot` |
| `0x3A1E` | `bin_read_u8` |
| `0x3A30` | `bin_read_u16` |
| `0x3A64` | `bin_read_cstring_offset` |
| `0x4001` | `load_palette_resource` |
| `0x4091` | `play_music_resource` |
| `0x446F` | `render_study_prompt` |
| `0x451B` | `execute_bin_commands` |
| `0x6631` | `initialize_scene` |
| `0x6A23` | `update_action_selector_overlay` |
| `0x7997` | `update_scene_threads` |
| `0x7A5C` | `start_scene_thread` |
| `0x834E` | `handle_study_bible_request` |
| `0x8558` | `find_action_target_by_key` |
| `0xB5A8` | `rotate_palette_range` |
| `0xB948` | `release_render_slot` |
| `0xBCAC` | `render_scene_display_object` |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
