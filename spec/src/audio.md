# Sound Effects and Music

## Audio model

Digital effects and music are independent channels with separate enable
settings. Scene commands can start, stop, and wait for an effect and can replace
the current music sequence. A host implementation MAY decode into any native
sample or synthesizer representation.

Disabling effects MUST make effect-play commands silent while preserving the
timing expected by wait commands. Disabling music stops or suppresses music
without disabling effects.

## Effect naming and playback

Effect identifier `n` selects `D%03d.ABT`. The play command also supplies a
rate; all nonzero calls in shipped scenes use 9,000 Hz. Identifier and rate
both zero request a stop rather than `D000.ABT`.

Only one retained digital effect is required. Starting a replacement releases
the preceding decoded buffer. The stop operation halts playback and releases
that buffer. The wait operation yields until playback finishes; without a
digital backend it uses a simulated 100-tick duration so script timing remains
similar.

## `ABT` header

An `ABT` effect begins with nine bytes:

| Offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 2 | Decoded sample count |
| `0x02` | 2 | Playback rate in hertz |
| `0x04` | 1 | Samples emitted by each delta block |
| `0x05` | 1 | Codec identifier |
| `0x06` | 2 | Auxiliary value; consumed but not used |
| `0x08` | 1 | Initial unsigned PCM sample |

The supplied effects use codec 2, 32 samples per delta block, and 9,000 Hz.
The decoder MUST use the header fields rather than assuming those population
values.

## `ABT` command stream

The initial sample is output first. Commands then produce samples until the
declared count is reached:

| Control form | Meaning |
|---|---|
| bit 7 set | Output `(control << 1) & 0xFF` as an absolute sample. |
| bit 7 clear, bit 6 set | Repeat the preceding sample `control & 0x3F` times. |
| bits 7 and 6 clear | Decode an adaptive delta block. |

For a delta block, bits 4 and 5 select mode and the low nibble plus one is the
step. Mode 1 uses one-bit codes and deltas `[-step, +step]`. Mode 2 uses
two-bit codes beginning at `-2 * step`. Modes 0 and 3 use four-bit codes
beginning at `-8 * step`. Build each table by adding `step`, skipping zero,
and retaining signed-byte wraparound.

Packed codes are read most-significant bits first. Add each signed delta to the
preceding output sample and clamp the result to 0 through 255. Stop only when
the declared output count has been produced. Truncation, output overrun,
impossible block geometry, count mismatch, or unused input is a format error.

The result is unsigned eight-bit mono PCM at the header rate.

## XMIDI resources

Music identifier `n` selects either `MUS%03d.XMI` or `IBM%03d.XMI` according
to the configured music family. Every supplied sequence contains:

```text
FORM XDIR
  INFO
CAT  XMID
  FORM XMID
    TIMB
    EVNT
```

IFF chunk sizes are big-endian and padded to even boundaries. The two-byte
sequence count inside `INFO` is little-endian. Supplied files declare one
sequence and contain one `FORM XMID`.

`TIMB` is an even-length array of patch/bank byte pairs. `EVNT` uses XMIDI's
MIDI-like representation:

- bytes below `0x80` before an event are additive delays;
- channel statuses have their standard fixed parameter counts;
- note-on adds a variable-length duration after note and velocity;
- system-exclusive and meta events use variable-length payload sizes; and
- `FF 2F 00` ends the track.

An optional zero pad may follow end-of-track. Parameter byte `0xFF` occurs in
valid supplied data and MUST NOT be rejected by an over-strict generic MIDI
validator.

A modern engine MAY convert XMIDI events to another sequencer format or play
them directly. Event order, delays, durations, program/bank choices, looping or
replacement behavior, and the distinction between the MUS and IBM families
must remain compatible.
