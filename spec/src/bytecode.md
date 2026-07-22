# Scene-program virtual machine

## Purpose and execution model

`BIN` resources are programs for a small scene virtual machine. A compatible
engine MUST execute these programs; it MUST NOT treat the shipped scenes as a
fixed list of hard-coded screens.

There are 62 `BIN` members and no generic `BIN` header. Most members are code
from beginning to end. `CP2.BIN` has code through offset `1D54` followed by a
256-byte data trailer. `ROOM3.BIN` has code ranges `0000..0335`,
`0C96..1753`, and `1768` through the end, separated by reserved zero-filled
regions. Code and data offsets remain relative to the beginning of the member.

A program is addressed from byte offset zero. The instruction pointer and all
branch, call, callback, and action targets are absolute byte offsets within the
expanded resource. Integer operands are little-endian. Normal execution reads
an opcode, reads exactly the operands declared below, performs its effect, and
continues at the following byte. Opcode values outside `0x01` through `0x91`
are invalid.

The VM owns 100 signed 16-bit variables. An encoded variable operand is the
even byte offset `2 * index`, not the index itself. Valid variable operands are
therefore even values from 0 through 198. Arithmetic results use 16-bit word
semantics. Comparisons and division are signed where stated. An implementation
MUST diagnose an odd or out-of-range variable operand.

The following operand notation is used:

| Code | Encoding |
|---|---|
| `B` | Unsigned byte. |
| `H` | Unsigned little-endian word; its interpretation may be signed. |
| `z` | Inline NUL-terminated CP437 string. |
| `p` | Inline NUL-terminated CP437 string, or `FF` followed by a word giving the resource-relative offset of a NUL-terminated string. |
| `9` | One nine-byte animation-step record. |
| `s` | One additional word if the immediately preceding word is negative when interpreted as signed. |

Only `p` recognizes the `FF` reference form. The `z` strings in opcodes
`01`, `0D`, `4D`, and `6D` are always inline. In `BHs`, a nonnegative word is
the callback target and uses default thread -1; a negative word stores its
negation as the thread slot and the following word is the callback target. A
command that suspends before consuming its operands MUST leave its instruction
pointer at that command so it can be retried.

## Complete instruction set

Names in this table are specification mnemonics, not names that an
implementation must expose. “Unused” means no shipped scene program invokes
the command; its byte layout and direct effect are nevertheless part of the
full-interpreter compatibility profile.

| Op | Schema | Mnemonic and required effect |
|---:|:---:|---|
| `01` | `z` | `load_art`: load the named `ART` member into the next art slot. |
| `02` | `BHHH` | `create_scene_thread`: create a scene thread from slot, X, Y, and scale and add its display object. |
| `03` | `BBHHB` | `add_native_scale_display_object`: add frame, art slot, X, Y, and flags at scale `0x0100`. Unused. |
| `04` | `BBHHHB` | `add_scaled_display_object`: add frame, art slot, X, Y, scale, and flags. |
| `05` | none | `return_minus_one`: stop the current interpreter invocation with result -1. |
| `06` | `H` | `begin_animation_sequence`: declare an animation with the supplied step interval; following `07` records belong to it. |
| `07` | `9` | `animation_step`: append one animation step in the format defined in [Scene runtime](scene-runtime.md). |
| `08` | `BB` | `start_animation`: start an animation with the supplied animation slot and mode. |
| `09` | `B` | `stop_animation`: stop an animation and release its render slot. |
| `0A` | none | `wait_for_scene_thread_movement`: suspend until primary movement state is 0 or 2. |
| `0B` | `BB` | `add_navigation_edge`: add an undirected edge between two navigation nodes. |
| `0C` | `BBp` | `add_scene_entry`: associate an entry name with its two initial node bytes. |
| `0D` | `zz` | `change_scene`: request the named scene and secondary entry/segment, ending current scene execution. |
| `0E` | none | `nop`: continue. Unused. |
| `0F` | `H` | `adjust_thread_delay`: subtract the word from the current scheduler thread's signed countdown; a resulting negative delay yields at the next command boundary until logical time makes it nonnegative. |
| `10` | `BHHp` | `configure_scene_thread_action`: set thread selector, X, Y, and action label; the selector starts enabled when its scene thread is created. |
| `11` | `BHs` | `add_navigation_arrival_handler`: map destination node to target and optional explicit thread slot using the `BHs` rule. |
| `12` | `BHs` | `add_navigation_departure_handler`: map source node to target and optional explicit thread slot using the `BHs` rule. |
| `13` | `H` | `remove_dialogue_choice`: remove the first choice whose target matches. Unused. |
| `14` | `p` | `show_adversary_dialogue`: show text using adversary presentation and wait for dismissal. |
| `15` | `B` | `select_study_record`: select a text descriptor and clear both study-result continuations. |
| `16` | `HHH` | `set_palette_adjustment_range_from_variable`: fill an inclusive signed brightness-adjustment range with the value of a variable and refresh the palette. |
| `17` | `BHs` | `add_reverse_edge_departure_handler`: add a reverse-traversal departure callback; `B` is the zero-based navigation-edge index. |
| `18` | `BHs` | `add_forward_edge_departure_handler`: add a forward-traversal departure callback; `B` is the zero-based navigation-edge index. Unused. |
| `19` | `BHs` | `add_forward_edge_arrival_handler`: add a forward-traversal arrival callback; `B` is the zero-based navigation-edge index. |
| `1A` | `BHs` | `add_reverse_edge_arrival_handler`: add a reverse-traversal arrival callback; `B` is the zero-based navigation-edge index. |
| `1B` | `H` | `prime_primary_scene_thread_timer`: store the negated value as the primary movement timer and set the transition latch. Unused. |
| `1C` | `B` | `enable_scene_thread_action`: enable one scene thread as a selector. |
| `1D` | `B` | `disable_scene_thread_action`: disable one scene thread as a selector. |
| `1E` | `HH` | `copy_variable`: copy source variable to destination variable. |
| `1F` | `HH` | `set_variable`: store immediate, then destination variable. |
| `20` | `HH` | `jump_if_zero`: variable, target. |
| `21` | `HH` | `jump_if_nonzero`: variable, target. |
| `22` | `HHH` | `jump_if_variables_equal`: left variable, right variable, target. |
| `23` | `HHH` | `jump_if_variable_equals`: variable, immediate, target. |
| `24` | `HHH` | `jump_if_variables_not_equal`: left variable, right variable, target. |
| `25` | `HHH` | `jump_if_variable_not_equal`: variable, immediate, target. |
| `26` | `HHH` | `jump_if_variable_greater_than_variable`: signed left variable, right variable, target. |
| `27` | `HHH` | `jump_if_variable_greater_than`: signed variable, immediate, target. |
| `28` | `HHH` | `jump_if_variable_less_than_variable`: signed left variable, right variable, target. |
| `29` | `HHH` | `jump_if_variable_less_than`: signed variable, immediate, target. |
| `2A` | `HH` | `add_variable`: add source variable to destination. |
| `2B` | `HH` | `add_to_variable`: add immediate to destination. |
| `2C` | `HH` | `subtract_variable`: subtract source variable from destination. |
| `2D` | `HH` | `subtract_from_variable`: subtract immediate from destination. |
| `2E` | `HH` | `multiply_variables`: signed-multiply destination by source variable. Unused. |
| `2F` | `HH` | `multiply_variable`: signed-multiply destination by immediate. |
| `30` | `HH` | `divide_variables`: signed-divide destination by source variable. Unused. |
| `31` | `HH` | `divide_variable`: signed-divide destination by immediate. |
| `32` | `H` | `increment_variable`: increment variable. |
| `33` | `H` | `decrement_variable`: decrement variable. |
| `34` | `H` | `call`: save the following offset and jump to target. |
| `35` | none | `return`: resume the saved call return offset. |
| `36` | `B` | `set_text_record_state`: set and select a text record. |
| `37` | `B` | `clear_text_record_state`: clear a text record. Unused. |
| `38` | `BH` | `jump_if_text_record_set`: selector, target. |
| `39` | `BH` | `jump_if_text_record_clear`: selector, target. Unused. |
| `3A` | `HHHp` | `add_action_target`: target, X, Y, and label. |
| `3B` | `B` | `enable_action_target`: set an action's active byte. |
| `3C` | `B` | `disable_action_target`: clear an action's active byte. |
| `3D` | `H` | `jump`: set the instruction pointer to target. |
| `3E` | `BH` | `start_scene_thread_at`: thread slot, target. |
| `3F` | `B` | `wait_for_animation`: continue for state 0, 5, or 6; otherwise suspend and retry. |
| `40` | `B` | `set_scene_thread_motion_state`: set current thread motion state; state 2 immediately performs a movement update. |
| `41` | none | `enable_action_selection`: enable screen actions for the current scene. |
| `42` | none | `disable_action_selection`: disable screen actions for the current scene. |
| `43` | `BBHHHB` | `add_scaled_display_object`: same contract as `04`. |
| `44` | `Hp` | `add_dialogue_choice`: append target and text to the current choice list. |
| `45` | none | `clear_dialogue_choices`: clear all choices and dialogue state. |
| `46` | none | `present_dialogue_choices`: suspend until a choice supplies a new target. |
| `47` | `B` | `set_modal_menu_selection`: seed the selection consumed by the modal text-menu path. Unused. |
| `48` | `p` | `show_character_dialogue`: show text using character presentation and wait for dismissal. |
| `49` | none | `request_study_bible`: enter the modal study interface and suspend the thread. |
| `4A` | none | `nop`: continue. Unused. |
| `4B` | none | `nop`: continue. Unused. |
| `4C` | `B` | `fill_screen`: fill all 320×200 pixels with the palette index. |
| `4D` | `z` | `load_palette`: load named `PAL` member. |
| `4E` | `p` | `show_captain_bible_dialogue`: show text using Captain Bible presentation and wait for dismissal. |
| `4F` | `BB` | `configure_study_navigation_success`: set record selector and node entered on study success. Unused. |
| `50` | none | `clear_study_record_selection`: clear both active study selectors. Unused. |
| `51` | `BHB` | `configure_study_thread_success`: set record selector, target, and thread slot started on success. |
| `52` | `B` | `play_music`: load and start numbered music. |
| `53` | `B` | `set_scene_thread_origin`: initialize the primary object's nodes and its X/Y/scale from the selected opcode-`02` geometry. |
| `54` | `B` | `move_scene_thread_to`: route the primary object to a navigation node and start movement. |
| `55` | none | `snapshot_state`: copy live state to the retained checkpoint state. |
| `56` | none | `nop`: continue. Unused. |
| `57` | `BH` | `play_sound_effect`: numbered effect and playback rate. |
| `58` | none | `stop_sound_effect`: stop playback and release the decoded sample. |
| `59` | none | `wait_for_sound_effect`: with a usable digital backend, yield and retry while playback remains active; without one, subtract 100 from the calling thread's delay and resume after this command. |
| `5A` | `H` | `jump_if_digital_audio_fallback`: jump when the digital driver is absent, effects are disabled, backend state bit 0 is clear, or the fallback word is nonzero. Fall through only when the first three checks indicate usable playback and the fallback word is zero. |
| `5B` | `B` | `set_scene_thread_direction`: select one of four orientations and its render offset. |
| `5C` | `BBB` | `configure_captain_bible_dialogue`: set Captain Bible text X, text Y, and wrap width. |
| `5D` | `BBB` | `configure_character_dialogue`: set character text X, text Y, and wrap width. |
| `5E` | `H` | `set_deferred_scene_thread_target`: schedule a target later started in thread slot 2. Unused. |
| `5F` | `BBB` | `start_linked_animation`: animation, linked animation, mode. |
| `60` | none | `nop`: continue. |
| `61` | `B` | `stop_scene_thread`: deactivate a scheduler slot. |
| `62` | `H` | `store_mouse_x`: store logical mouse X in variable. |
| `63` | `H` | `store_mouse_y`: store logical mouse Y in variable. |
| `64` | `H` | `jump_if_confirm_pressed`: consume the Enter-or-click latch and jump if it was set. |
| `65` | `BB` | `clear_display_object_frames`: first and count; set each selected frame to zero. Unused. |
| `66` | `BBBB` | `advance_display_object_frames`: first, count, minimum, maximum; increment and wrap selected frame bytes. Unused. |
| `67` | none | `request_restore_saved_game`: leave the scene loop and restore selected retained state. |
| `68` | `H` | `adjust_variable_1280_once`: subtract 1280 if above 640, then add 1280 if below -639; do each test once. |
| `69` | `HH` | `load_bin_word`: immediate resource offset, destination variable. |
| `6A` | `HH` | `patch_bin_word_from_variable`: immediate resource offset, source variable. |
| `6B` | `B` | `load_text_bank`: replace active bank and clear all 66 descriptors. |
| `6C` | `HHHH` | `rotate_palette_range`: inclusive minimum, maximum, signed step, phase variable; update, wrap, and map the range. |
| `6D` | `z` | `load_palette`: same contract as `4D`. |
| `6E` | `B` | `start_primary_scene_thread_overlay`: start a resource-driven overlay on thread zero. Unused. |
| `6F` | none | `wait_for_primary_scene_thread_overlay`: suspend while that overlay is active. Unused. |
| `70` | none | `unload_last_art`: release the most recently loaded art slot. |
| `71` | `HH` | `load_bin_word_indirect`: offset variable, destination variable. |
| `72` | none | `suspend_scene_thread`: suspend until resumed by input or UI processing. |
| `73` | `BH` | `jump_if_state_flag_clear`: flag, target. |
| `74` | `BH` | `jump_if_state_flag_set`: flag, target. |
| `75` | `B` | `clear_state_flag`: clear a bit in the 128-bit flag bank. |
| `76` | `B` | `set_state_flag`: set a bit in the 128-bit flag bank. |
| `77` | none | `process_current_map_cell`: derive scene context and adjacent interactions from the current map coordinate. |
| `78` | `B` | `load_map`: load level letter plus current difficulty code. |
| `79` | none | `clear_navigation_handlers`: clear entry, edge, arrival, and departure callback lists. |
| `7A` | `HH` | `patch_bin_byte_from_variable`: immediate resource offset, source variable; write its low byte. |
| `7B` | `H` | `set_current_map_cell_kind`: preserve the old high nibble and OR in the source variable's low byte. |
| `7C` | `H` | `set_current_map_cell_parameter_a`: write current cell byte 1 from variable. |
| `7D` | `BH` | `configure_study_prompt`: companion-text component and variable whose value is the record selector. |
| `7E` | none | `blackout_palette`: schedule an immediate black-palette transition. |
| `7F` | `H` | `set_current_map_cell_parameter_b`: write current cell byte 2 from variable. |
| `80` | `BH` | `jump_if_animation_active`: animation, target; jump when state is nonzero. |
| `81` | `H` | `reduce_faith`: apply difficulty-scaled loss unless no-combat mode suppresses it. |
| `82` | `HH` | `set_variable_random_modulo`: modulus, destination variable. |
| `83` | `HBH` | `copy_text_record_component_to_bin`: record-selector variable, component, destination resource offset; set flag `22` on success and clear it when the component is absent. |
| `84` | `HH` | `load_bin_byte`: immediate resource offset, destination variable; sign-extend the byte. |
| `85` | `B` | `hide_display_object`: set the selected display object's hidden bit. |
| `86` | `B` | `show_display_object`: clear the selected display object's hidden bit. |
| `87` | none | `normalize_map_cells`: apply the progression-dependent map normalization rules. |
| `88` | none | `clear_text_record_states`: clear state byte 4 in all 66 descriptors. |
| `89` | none | `mark_current_map_cell_explored`: set bit X in exploration row Y. |
| `8A` | `BH` | `jump_if_animation_finished`: animation, target; jump for state 0, 5, or 6. |
| `8B` | none | `consume_random_text_record`: in difficulty state 2, randomly clear one set descriptor and start a 3000-tick timer. Unused. |
| `8C` | `H` | `jump_if_no_combat`: jump to target when installation no-combat mode is set. |
| `8D` | `H` | `jump_if_file_missing`: test active player-prefix plus save suffix and jump on open failure. |
| `8E` | none | `sync_current_cell_flags_23_to_27`: copy five current-cell bits into state flags `23` through `27`. |
| `8F` | `HH` | `and_variables`: destination AND source variable. Unused. |
| `90` | `HH` | `and_variable`: destination AND immediate. Unused. |
| `91` | `HH` | `set_variable_current_cell_byte_modulo`: divisor, destination variable; store the signed remainder of the zero-extended current-cell auxiliary byte. |

## Mutable program data

Opcodes `69`, `6A`, `71`, `7A`, `83`, and `84` deliberately read or modify
bytes in the expanded current `BIN` resource. Each scene instance therefore
needs a writable resource buffer. Changes last for that loaded scene instance
only. Bounds MUST be checked before every access. The shipped programs use
this feature to construct resource names and copy text components, so an
engine that keeps program bytes immutable is not compatible.

## Calls, threads, and suspension

Calls and scheduler threads are distinct. `34`/`35` provide subroutine
control flow inside one command stream. Scene-thread commands create or resume
additional instruction pointers. Waiting commands yield without busy-waiting;
the engine retries them in later update cycles after animations, audio, input,
or modal UI state has changed.

An implementation MAY use coroutines, state machines, or ordinary records.
It MUST preserve externally visible ordering: program mutations completed
before a suspension are visible to all later threads and rendering in that
update cycle.
