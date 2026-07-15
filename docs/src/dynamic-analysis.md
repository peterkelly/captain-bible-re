# Dynamic Analysis

## QEMU tracing workflow

`tools/qemu_dos_trace.c` is a QEMU TCG plugin that observes software interrupt
`21h` without changing the game executable or disk image. Build and run it
through the normal launcher:

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
linear address, inferred DOS function, argument registers, data segments, and
an escaped pathname when the API uses one. A paired return record preserves
the carry flag.

QEMU 11.0.2's i386 plugin register accessor reports EAX as zero at these
callbacks even though the other general and segment registers are valid. The
plugin therefore derives the DOS function from the nearest executed
`MOV AH,imm8` or `MOV AX,imm16` before the interrupt and explicitly omits AX
from the log. Trace mode also sets `one-insn-per-tb=on`; without it, plugin
register reads describe the beginning of a longer translation block rather
than the interrupt boundary. These limitations are recorded rather than
silently presenting the zero EAX values as evidence.

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
