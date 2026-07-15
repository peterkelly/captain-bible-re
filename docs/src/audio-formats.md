# Audio Formats

## Audio resource families

`DD1.DAT` contains two independent audio families:

| Extension | Members | Expanded bytes | Purpose |
|---|---:|---:|---|
| `ABT` | 41 | 205,513 | Compressed unsigned eight-bit mono sound effects. |
| `XMI` | 32 | 34,618 | IFF/XMIDI music sequences. |

The scene interpreter selects an effect with opcode `0x57`, whose operands
are an effect number and playback rate. Every nonzero invocation in the
recovered command regions uses rate 9,000 and constructs `D001.ABT` through
`D041.ABT`. A `0, 0` invocation stops the active effect. Music opcode `0x52`
selects a numeric track and `play_music_resource` constructs either a
`MUS###.XMI` or `IBM###.XMI` name according to a runtime mode flag.

## `ABT` header

The game contains its complete ABT decoder at unpacked load offset `0x92E0`.
Each member starts with this nine-byte header:

| Offset | Size | Interpretation |
|---:|---:|---|
| `0x00` | 2 | Decoded sample count, little endian. |
| `0x02` | 2 | Playback rate in hertz, little endian. |
| `0x04` | 1 | Samples emitted by each delta block. |
| `0x05` | 1 | Codec identifier. |
| `0x06` | 2 | Auxiliary field not used by the decoder. |
| `0x08` | 1 | Initial unsigned PCM sample. |

All 41 resources use a 9,000 Hz rate, delta blocks of 32 samples, and codec
identifier 2. The auxiliary word is 128 in 35 files, 32 in four, 64 in one,
and 320 in one. Its purpose remains unknown; the decoder explicitly consumes
and discards it.

The decoded population contains 412,282 samples, or approximately 45.809
seconds at 9,000 Hz. Samples are unsigned eight-bit mono PCM. The smallest
effect is 185 samples and the largest is 32,933 samples.

## `ABT` command stream

The initial sample is followed by variable-length commands until the declared
sample count has been produced:

| Control byte | Encoding |
|---|---|
| Bit 7 set | Absolute sample. The output byte is the control byte shifted left once. |
| Bit 7 clear, bit 6 set | Repeat the previous sample by the low six-bit count. |
| Bits 7 and 6 clear | Adaptive delta block selected by the high nibble with step size `(low nibble + 1)`. |

Delta mode 1 uses one-bit codes and the signed table `[-step, +step]`. Mode 2
uses two-bit codes and starts at `-2 * step`. Modes 0 and 3 use four-bit codes
and start at `-8 * step`. Each table advances by `step`, skips zero, and keeps
the executable's signed-byte wraparound. Packed codes are read most
significant bits first. Each delta is added to the preceding output and
clamped to the inclusive range 0 through 255.

Across the archive, exact decoding encounters:

| Command type | Count |
|---|---:|
| Absolute sample | 71,094 |
| One-bit delta block | 2,125 |
| Two-bit delta block | 1,185 |
| Four-bit delta block | 6,533 |
| Run-length command | 1,699 |

Every member produces its declared sample count and consumes its compressed
input exactly, with no unused trailer.

## QEMU validation of `D003.ABT`

The startup sequence plays `D003.ABT` during the logo. QEMU was launched with
the visible Cocoa display, silent audio backend, and GDB remote debugging.
A breakpoint at physical address `0xA499` stopped the process at
`0627:4229`, immediately before the decoded effect is submitted to interrupt
`66h`.

The live state structure at `DS:A0DE` contained buffer pointer `5A45:0000`,
sample count `0x2368` (9,064), callback `14E1:79EC`, and rate `0x2328`
(9,000). Dumped 9,064 bytes from physical address `0x5A450`. The live buffer
and independently decoded host output are byte-for-byte identical:

```text
ca97ad22acf3cc39d078b619168fa026deb1606082999bfb8b9a1aac4957422b
```

This validates the header, every command family exercised by `D003.ABT`, code
bit order, signed delta table, clamping behavior, and final sample count
against the running DOS program.

## Converting `ABT` to WAV

Inspect an effect or write standard unsigned eight-bit mono PCM:

```sh
tools/convert_abt.py build/dd1/all/306_D003.ABT
tools/convert_abt.py \
  build/dd1/all/306_D003.ABT \
  --output build/audio/d003.wav
```

The decoder rejects truncated commands, output overruns, invalid block
geometry, sample-count mismatches, and unused input bytes. The WAV rate comes
from the ABT header rather than being hard-coded.

## `XMI`: IFF/XMIDI music

The archive has matching numeric families `MUS001.XMI` through `MUS016.XMI`
and `IBM001.XMI` through `IBM016.XMI`. Every file has two top-level IFF
containers. IFF sizes are big endian, while the two-byte sequence count in
`INFO` is little endian:

```text
FORM XDIR
  INFO  01 00
CAT  XMID
  FORM XMID
    TIMB
    EVNT
```

All files declare exactly one sequence and contain one `FORM XMID`. `TIMB`
is an even-length list of two-byte patch/bank pairs. `EVNT` uses XMIDI's
MIDI-like event representation:

- bytes below `0x80` before an event are additive delay values;
- channel statuses carry fixed-size parameters;
- note-on events add a variable-length duration after note and velocity;
- system-exclusive and meta events use variable-length payload sizes; and
- meta event `FF 2F 00` ends the track.

Eleven EVNT chunks include one zero padding byte after end-of-track. One track
also contains controller parameter `0xFF`, so the validator preserves the
game data instead of imposing a generic seven-bit MIDI parameter check.

The 32 sequences contain 7,087 events, including 6,608 duration-bearing note
events and 173 TIMB entries. `MUS001.XMI`, loaded during startup, contains 12
timbres, 446 events, 432 notes, eight meta events, and total additive delay
3,016.

Inspect and validate a sequence with:

```sh
tools/inspect_xmi.py build/dd1/all/267_MUS001.XMI
```

The tool validates container sizes and padding, directory counts, form and
chunk order, event boundaries, variable-length quantities, and end-of-track.

## Executable routines

| Load offset | Current name | Evidence |
|---:|---|---|
| `0x4091` | `play_music_resource` | Builds `MUS###.XMI` or `IBM###.XMI`, loads it, and starts the music driver. |
| `0x4155` | `release_sound_effect_buffer` | Releases the retained decoded PCM allocation. |
| `0x417F` | `play_sound_effect_resource` | Builds `D###.ABT`, loads and decodes it, then submits its PCM state. |
| `0x4235` | `stop_sound_effect` | Stops active digital playback and releases its buffer. |
| `0x92D0` | `abt_get_sample_rate` | Returns the little-endian word at ABT offset 2. |
| `0x92E0` | `decode_abt` | Reads the header and dispatches absolute, run, and delta commands. |
| `0x93BE` | `abt_decode_1bit_delta_block` | Expands eight one-bit delta codes per byte. |
| `0x94CB` | `abt_decode_2bit_delta_block` | Expands four two-bit delta codes per byte. |
| `0x956E` | `abt_decode_4bit_delta_block` | Expands two four-bit delta codes per byte. |

Offsets use the unpacked load-module convention documented elsewhere in this
book.
