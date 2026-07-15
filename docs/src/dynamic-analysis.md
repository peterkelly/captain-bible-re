# Dynamic Analysis

## QEMU tracing workflow

`tools/qemu_dos_trace.c` is a QEMU TCG plugin that observes BIOS keyboard
interrupt `16h`, DOS interrupt `21h`, mouse interrupt `33h`, and sound-driver
interrupt `66h` without changing the game executable or disk image. Build and
run it through the normal launcher:

```sh
./run.sh --trace-dos
```

Trace mode keeps the required Cocoa display visible, uses QEMU's silent audio
backend, and creates these ignored artifacts:

```text
build/qemu-trace/qemu_dos_trace.so
build/qemu-trace/dos-calls.log
build/qemu-trace/monitor.sock
```

The plugin filters on the current game code segment `0627` and remains dormant
until the reconstructed entry point `0627:CB5C` executes. That prevents an
earlier FreeDOS program that temporarily occupies the same segment from
polluting the trace. Each call record contains its exact `CS:IP`, physical
linear address, live AX, argument registers, data segments, and an escaped
pathname when the DOS API uses one. A paired return record preserves AX, the
other general and segment registers, and carry.

QEMU 11.0.2 represents the first x86 register's opaque plugin handle with
value zero. The tracer tracks descriptor presence separately instead of
mistaking that valid EAX handle for a missing register. It retains static
`MOV AH/AX` inference only as a fallback for targets that do not expose EAX.
Trace mode also sets `one-insn-per-tb=on`; without it, plugin register reads
describe the beginning of a longer translation block rather than the
interrupt boundary.

## Preserved startup capture

The verified capture ran from process startup into the first story text. The
monitor stopped at:

| Register | Value |
|---|---:|
| `CS:IP` | `0627:C668` |
| `DS=ES=SS` | `14E1` |
| `FS` | `0617` (PSP) |
| `GS` | `04C7` |

This independently repeats the earlier load and data segment values. The
screen contains the opening narration beginning “There once was a city far
from us in place and time,” establishing the visible runtime point. QEMU also
saved the first MiB of physical memory to
`build/qemu-trace/startup-physical-1m.bin`.

| Artifact | SHA-256 |
|---|---|
| `dos-calls.log` | `f8013fb529444c409a6309a5bbc57336d674382f4e20dcde9185a4d67658e3c9` |
| `startup-physical-1m.bin` | `7fee3fdda30db225711d0db84d1f292efb9b087c4a91deb2e035025cd31bf71e` |
| `startup-screen.png` | `85a46bbf6345d5cd88393596706ded3daadbbe0ecb9853cdd0bcecf610077c79` |

Comparing the captured memory with the independently unpacked and relocated
load module again produces the exact `0x905A`-byte static prefix and 5,612
runtime differences across 75,264 bytes, matching the earlier title capture.

The trace contains 195 completed game DOS calls. Its high-level file timeline
is:

| First call | Activity |
|---:|---|
| 13 | Change directory to `C:\CBDOME`. |
| 22 | Open and read the four-byte `SOUND.5` installation-lock file. |
| 29 | Load `SOUND.1`. |
| 43 | Load `SOUND.2`. |
| 68 | Load `SOUND.3`. |
| 90 | Load `SOUND.4`. |
| 105 | Probe `DD1.DAT`, then reopen it as the persistent main-data handle. |
| 121 | Read `DDGAMES.SV0`, the 243-byte save-slot index. |
| 135 / 142 | Load `DDLC` twice during early resource initialization. |
| 181 | Reopen `DDGAMES.SV0` before the story introduction. |

All listed returns have carry clear. The path sequence is runtime evidence,
not a prediction from embedded strings.

## Sound-driver correlation

`SOUND.5` is read in requests of one byte and three bytes. Each driver file is
then opened, queried, measured with three seek calls, allocated in DOS memory,
read in chunks, and closed. The observed allocation request exactly matches
the file size rounded up to a 16-byte paragraph:

| File | Bytes | Allocation (`BX`) | Paragraph bytes |
|---|---:|---:|---:|
| `SOUND.1` | 4,824 | `012E` | 4,832 |
| `SOUND.2` | 16,263 | `03F9` | 16,272 |
| `SOUND.3` | 13,312 | `0340` | 13,312 |
| `SOUND.4` | 3,622 | `00E3` | 3,632 |

This connects the static far-pointer loader at `0xACDA` with the DOS API calls
inside the Microsoft C low-level I/O routines. The trace supports the names
`libc_lowio_close` (`0xDA82`), `libc_lowio_seek` (`0xDAA2`),
`libc_lowio_open` (`0xDB1C`), `libc_lowio_read` (`0xDCC0`), and
`libc_lowio_write` (`0xDD9E`).

### Live decoded effect capture

For an independent codec check, launched QEMU with the same visible Cocoa
display and silent audio devices, plus its GDB remote stub. A breakpoint at
physical `0xA499` stopped Captain Bible at `0627:4229`, after `D003.ABT` had
been decoded and immediately before its state was submitted to interrupt
`66h`.

The state at `DS:A0DE` pointed to `5A45:0000` and declared 9,064 samples at
9,000 Hz. The 9,064-byte physical-memory dump from `0x5A450` exactly matches
the independently implemented ABT decoder. Both have SHA-256
`ca97ad22acf3cc39d078b619168fa026deb1606082999bfb8b9a1aac4957422b`.
The dedicated audio-format chapter records the codec and conversion tool.

## Main container correlation

Startup first opens and closes `DD1.DAT` through normal stream setup, then
opens it again as DOS handle 5. Subsequent resources cause seeks and reads on
that handle; no DOS open is made for the static resource name `RUN.ART`.
This is direct evidence that names such as `RUN.ART` refer to members indexed
inside `DD1.DAT`, not sibling files in the DOS directory.

`DDLC`, by contrast, is opened as a separate DOS pathname twice during the
captured interval. Later static and format analysis identifies it as tagged
companion text bank C; `DDLA` through `DDLG` and `DDLR` use the same recovered
record stream. The direct opens are therefore runtime confirmation that DDL
text lives beside the main container, while the extensionless verse indexes
live inside `DD1.DAT`. The text-format chapter documents their exact join.

## Focused input and save capture

A later visible, silent QEMU run added `int 16h` and `int 33h` to the same
instruction-boundary tracer. The game polls BIOS keyboard service `0101` at
`0627:E9DC`, mouse motion service `000B` at `0627:8D8A`, and mouse
position/buttons service `0003` at `0627:8DCD`. These sites independently
match the statically named input wrappers.

Moving the monitor mouse changed the returned position from X/Y `0140:0064`
to `01D0:0088`, or `(320, 100)` to `(464, 136)`. Holding the left button then
produced repeated service-`0003` returns with `BX=0001` at the new position.
This proves that the guest driver state reaches the game's own polling path,
not merely that QEMU accepted host events.

F10 produced BIOS scan/ASCII word `4400` first through the non-consuming
service and then through service `0000`. The next DOS activity opened the
existing `DDGAMES.SV0`, then created and wrote `DDGAMES.SVQ`. After QEMU
stopped, the quick save was exactly 2,752 bytes with SHA-256
`5e329e21f32d2e6c3e564d3a3ad717ab07ad55aaedde2587725756945597e43f`.
The before/after `.SV0` hashes were identical, confirming that quick save does
not rewrite the normal-slot label index.

The normal in-game Escape/Save Game path ended name entry with BIOS word
`1C0D` and then rewrote the 243-byte `DDGAMES.SV0` followed by the selected
2,752-byte `DDGAMES.SV2`. The low-level writes follow the recovered state
layout: 200-byte snapshot and live blocks, 66 flags, 660 bytes of text
descriptors, four 20-byte strings, five words, and two 768-byte maps. Parsing
the copied slot with `tools/inspect_save.py` recovered the expected settings,
bank C, `INTRO`/`seg` scene strings, and named script-variable state. This
connects BIOS input, the menu path, `write_save_state`, Microsoft C low-level
I/O, and the two on-disk formats in one run.

Adding more interrupt vectors exposed a tracer bookkeeping bug: an interrupt
instruction inside DOS could have the same registered return callback active
while a game call was pending. Return records from the affected capture are
therefore not used for DOS-result claims; its call-entry paths and write
arguments remain valid. The plugin now stores the pending call's exact linear
return address and ignores callbacks at every other `CS:IP`. A fresh bounded
run recorded 119,824 paired calls—39,903 keyboard, 115 DOS, and 79,806
mouse—with no false DOS-internal return.

## Representative interactive coverage

The visible Cocoa session exercised and captured these distinct paths:

| System | Observed evidence |
|---|---|
| Startup | Main title, landscape title transition, and difficulty selector. |
| Story | Opening narration and multi-step commander conversation. |
| Exploration | Captain Bible on the exterior platform and inside a hall. |
| Study | F1 Bible interface reporting no loaded verses. |
| Navigation | F2 map interface with the current node graph. |
| State | F3 faith overlay reporting 100 percent. |
| Menus/saves | Gameplay options, normal-save slot list, and name entry. |
| Combat | COMBAT1 action screen, A-key attack effect, and defeat screen. |

Function keys were sent only after normal gameplay began; an earlier F1 during
the introductory sequence advanced into the difficulty selector instead of
opening the Bible. The distinction is useful evidence that the same input is
routed by scene state rather than handled as an unconditional global hotkey.
The combat chapter records the controlled scene-entry provenance and table
dump in detail.
