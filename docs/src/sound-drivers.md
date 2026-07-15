# Sound Drivers and MIDPAK Timbres

## Installed driver set

`SETSOUND.BAT` preserves the original installer names used to create the
otherwise anonymous `SOUND.*` files:

| Installed file | Bytes | Installer source | Role |
|---|---:|---|---|
| `SOUND.1` | 4,824 | `soundrv.com` | DIGPAK Sound Blaster 16 resident driver, version 3.40. |
| `SOUND.2` | 16,263 | `midpak.adv` | Miles/Creative Sound Blaster Pro FM MIDPAK hardware driver. |
| `SOUND.3` | 13,312 | `tmidpak.com` | MIDPAK loader and resident service, version 3.0 family. |
| `SOUND.4` | 3,622 | `midpak.ad` | Audio Interface Library global OPL timbre library. |
| `SOUND.5` | 4 | installer output | Game configuration and Bible-translation lock words. |

The identities do not depend only on the batch file. `SOUND.1` contains the
signatures `DIGPAK`, `Sound Blaster 16`, John W. Ratcliff's credit, and a
version 3.40 identification string. `SOUND.3` contains `MIDPAK`, `MIDI Sound
Package`, and the Audio Solution credits. `SOUND.2` begins with a Miles Design
copyright string and identifies Creative Labs Sound Blaster Pro FM internally.

## Interrupt interface

Both resident packages hook software interrupt `66h`. Captain Bible contains
34 literal `CD 66` instructions: 31 in small API wrappers, one in the driver
detection routine, and two in bootstrap paths. The request number is the
complete `AX` value. The recovered
names agree with the contemporary [Ralf Brown Interrupt List's INT 66
catalog](https://fd.lod.bz/rbil/interrup/sound/index.html).

### DIGPAK wrappers

| Load offset | AX | Recovered wrapper | Contract |
|---:|---:|---|---|
| `0x8F08` | `0688` | `digpak_play_8bit_sound` | Play the `DS:SI` sound structure. |
| `0x8F28` | `0689` | `digpak_report_status` | Return 0 idle or 1 playing in AX. |
| `0x8F2E` | `068A` | `digpak_preformat_sound` | Convert the `DS:SI` structure for the output device. |
| `0x8F41` | `068B` | `digpak_play_preformatted_sound` | Play the preformatted `DS:SI` structure. |
| `0x8F54` | `0694` | `digpak_play_preformatted_data` | Newer preformatted-data entry point. |
| `0x8F67` | `068C` | `digpak_report_capabilities` | Return capability mask, fixed rate, and ID pointer. |
| `0x8F6D` | `068C` | `digpak_get_driver_id` | Copy the NUL-terminated ID returned in `BX:CX`. |
| `0x8F95` | `068D` | `digpak_report_current_sample_address` | Report approximate playback position. |
| `0x8F9B` | `068E` | `digpak_set_callback_address` | Set callback `BX:DX` and callback DS. |
| `0x8FAD` | `068F` | `digpak_stop_current_sound` | Terminate current digital playback. |
| `0x8FB3` | `0690` | `digpak_set_audio_hardware` | Set IRQ, base address, and device value. |
| `0x8FC8` | `0691` | `digpak_report_callback_address` | Return callback and original caller DS. |
| `0x8FCE` | `0689` | `digpak_wait_until_idle` | Poll status until AX becomes zero. |
| `0x8FD8` | `0695` | `digpak_post_audio_pending` | Start or queue a sound structure. |
| `0x8FEB` | `0696` | `digpak_get_audio_pending_status` | Report playing/pending combination. |
| `0x8FF1` | `0697` | `digpak_set_stereo_panning` | Set DX from 0 right through 127 left. |

The [documented DIGPAK sound structure](https://fd.lod.bz/rbil/interrup/sound/660688.html)
is 12 bytes: a far audio-data pointer, 16-bit byte count, far playback-status
pointer, and 16-bit frequency. This exactly explains the live structure at
`DS:A0DE` used by `play_sound_effect_resource`. The game first invokes `068A`
to preformat the independently decoded ABT PCM and then `068B` to play it.

### MIDPAK wrappers

| Load offset | AX | Recovered wrapper | Contract |
|---:|---:|---|---|
| `0x8CFC` | `0701` | `midpak_get_digitized_capabilities` | Probe the companion digital driver. |
| `0x8C7A` | `0702` | `midpak_play_sequence` | Play sequence BX. |
| `0x8C89` | `0703` | `midpak_segue_sequence` | Segue to BX using activation CX. |
| `0x8C9B` | `0704` | `midpak_register_xmidi` | Register data at `CX:BX`, length `DI:SI`. |
| `0x8CB7` | `0705` | `midpak_stop_midi` | Stop MIDI playback. |
| `0x8CBD` | `0706` | `midpak_remap_channel` | Obsolete sequence/channel remap. |
| `0x8D02` | `0707` | `midpak_report_trigger_count` | Return trigger count and ID. |
| `0x8D08` | `0708` | `midpak_reset_trigger_count` | Reset the trigger counter. |
| `0x8D0E` | `0709` | `midpak_sleep` | Obsolete MIDI sleep. |
| `0x8D14` | `070A` | `midpak_awake` | Obsolete MIDI wake. |
| `0x8D1A` | `070B` | `midpak_resume` | Resume playback. |
| `0x8D20` | `070C` | `midpak_get_sequence_status` | Return stopped, playing, or done. |
| `0x8D3E` | `070D` | `midpak_register_xmidi_file` | Register the filename at `CX:BX`. |
| `0x8D26` | `070E` | `midpak_get_relative_volume` | Return relative volume. |
| `0x8D2C` | `070F` | `midpak_set_relative_volume` | Set BX volume over CX time. |

The bootstrap call at `0xABBB` uses service `0710`: BX is the segment of the
loaded `SOUND.2` `.ADV`, CX is zero, and `DX:SI` points to `SOUND.4`. This
matches the [MIDPAK load-driver contract](https://fd.lod.bz/rbil/interrup/sound/660710.html)
exactly. `play_music_resource` then stops playback, sets volume, brackets
registration with sleep/wake, registers the XMI byte buffer with `0704`, and
plays sequence zero with `0702`.

## QEMU call and return evidence

The QEMU plugin now recognizes both `int 21h` and `int 66h` and reads the live
EAX register at entry and return. QEMU represents the first x86 register with
opaque handle value zero; treating that value as a valid handle was necessary
to recover result AX rather than falling back to instruction inference. Return
records also include the other general and segment registers.

A visible, host-muted startup capture produced this capability exchange:

```text
CALL ... pc=0627:ABED int=66 AX=068C ...
RET  ... from=0627:ABED int=66 AX=0FC1 BX=2E88 CX=010C ...
         result="Sound Blaster 16"
```

The same query through wrapper `0x8F67` returns the same mask and ID pointer.
Service `0710` returns AX zero after loading the FM driver and timbres.
Observed DIGPAK status calls return both 0 and 1, matching idle and playing;
MIDPAK `070C` returns 1 while the title sequence is active. All captured
driver returns have carry clear.

The current bounded trace contains 159 DOS calls and 7,844 driver calls. Most
driver traffic is deliberate polling: 7,831 calls to DIGPAK status while the
slowed one-instruction translation mode runs. Its ignored artifact is
`build/qemu-trace/dos-calls.log`, SHA-256
`ae9d9b5952171f35d9dff8a75548e399a15fb01ee27d4058b2800891766404a6`.

## `SOUND.4` global timbre library

The file consists of a six-byte directory entry repeated until `FF FF`, then
the timbres at their absolute offsets:

| Directory offset | Size | Meaning |
|---:|---:|---|
| `+0` | 1 | MIDI patch number. |
| `+1` | 1 | Bank; `0x7F` denotes percussion. |
| `+2` | 4 | Absolute little-endian timbre offset. |

The terminator ends at `0x440`, which is also the first timbre offset. There
are 128 bank-zero melodic entries for patches 0 through 127 and 53 percussion
entries for notes 35 through 87 in bank `0x7F`.

Every timbre is exactly 14 bytes and every directory offset is contiguous:

| Timbre offset | Size | Meaning |
|---:|---:|---|
| `+0` | 2 | Record length including this word: 14. |
| `+2` | 1 | Signed melodic transpose, or percussion note. |
| `+3` | 5 | Modulator OPL registers: AVEKM, KSL/TL, attack/decay, sustain/release, waveform. |
| `+8` | 1 | Feedback/connection register. |
| `+9` | 5 | Carrier registers in the same order. |

This layout agrees byte-for-byte with the AIL structures recovered from Miles
source by [OPL3BankEditor's pinned AIL parser](https://github.com/Wohlstand/OPL3BankEditor/blob/992008e2edbaabcd8809df6be6bc91925597f1a9/src/FileFormats/format_ail2_gtl.cpp).
No padding or unreferenced trailer remains: `181 * 14` bytes extend from
`0x440` to the exact 3,622-byte end of file.

Validate or list the bank with:

```sh
tools/inspect_midpak_ad.py CB/SOUND.4
tools/inspect_midpak_ad.py CB/SOUND.4 --list
```

The parser rejects a missing directory terminator, out-of-range or duplicate
patches, a gap or overlap between records, unsupported record lengths, and a
truncated final record.
