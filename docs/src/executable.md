# Executable Reconstruction

## File identity

The supplied `CB/CB.EXE` is a 64,299-byte, 16-bit DOS MZ executable. Its
SHA-256 is:

```text
2b7726ae9cf56e0067533e4bd1c5c76685f1d9855a7d90835850388db7b07ee0
```

The filesystem timestamp is 1996-12-24 23:32 in the host's `+0700` time zone.
The MZ header has no outer relocations and points to `0F79:0010`, only 395
bytes before the end of the file. The load module's entropy is approximately
7.004 bits per byte. These are consequences of executable compression, not
evidence that the game code is encrypted.

## Microsoft EXEPACK

The bytes at file offset `0xF990` are a 16-byte Microsoft EXEPACK header. The
`RB` signature, the decompression loop, and the 22-byte
`Packed file is corrupt` error message identify the format. Microsoft's
[MS-DOS Encyclopedia](https://www.pcjs.org/documents/books/mspl13/msdos/encyclopedia/section4/)
describes EXEPACK as LINK's compression of repeated byte runs and the
relocation table. David Fifield's independently maintained
[EXEPACK implementation](https://www.bamsoftware.com/software/exepack/)
documents and implements the specific header and backward decompression
algorithm used here.

| Field | Value |
|---|---:|
| Packed MZ entry | `0F79:0010` |
| EXEPACK header file offset | `0xF990` |
| Compressed load bytes | 63,376 (`0xF790`) |
| Complete EXEPACK block | 411 bytes (`0x019B`) |
| Decompressor and message | 277 bytes (`0x0115`) |
| Reconstructed load bytes | 75,264 (`0x12600`) |
| Real entry | `0000:CB5C` |
| Initial stack | `1A40:1388` |
| Reconstructed minimum allocation | `0x091A` paragraphs |
| Reconstructed relocation count | 43 |

The packed relocation table is 118 bytes: 32 bytes of counts for 16 groups
plus 43 two-byte offsets. The recovered load-module relocation offsets are:

```text
0034c 0033c 00334 002ac 000af 000aa 034d4 034c8 035fb 0429c
04286 04275 0424f 04246 0422c 041fc 0414e 04143 0412e 04129
04115 040f0 043da 043cf 043ba 0439d 04392 0437d 04363 04335
04320 04316 042ed 05146 07615 0973a 09ae8 09e8c 0ab31 0cb67
0cbf1 12214 122a8
```

`tools/analyze_cb_exe.py` implements the relevant MZ and EXEPACK decoding with
the Python standard library. It emits a 75,776-byte conventional MZ file with
SHA-256:

```text
4875f83d6d2ba9c1cc4f058e351e453010c6a5976e1b15976b676689f9747643
```

That output is byte-identical to the result from Fifield's EXEPACK 1.4.0 at
source revision `f715ed19285565d636e78182fc19df62c0fa64b9`.

## QEMU memory verification

QEMU was run with the required visible Cocoa display and its monitor and GDB
server enabled. Once the title screen appeared, the VM was stopped and the
first MiB of physical memory was saved:

```text
build/dumps/title-physical-1m.bin
```

The captured register state located the process precisely:

| Item | Value |
|---|---:|
| PSP segment | `0617` |
| Load/CS segment | `0627` (physical `0x06270`) |
| Title-screen `CS:IP` | `0627:C614` |
| Title-screen `DS=ES=SS` | `14E1` |
| Relative data-segment base | `0xEBA0` |
| Physical data-segment base | `0x14E10` |

After adding load segment `0x0627` at all 43 MZ relocation sites, the rebuilt
load module and the QEMU process memory have an identical prefix of `0x905A`
bytes. There are 5,612 differing bytes in the full 75,264-byte comparison;
inspection shows runtime-initialized tables, loaded resource metadata, and
BSS state. Known static strings occur at the predicted relocated addresses,
including the Microsoft run-time banner at physical `0x14E18`. This makes the
QEMU snapshot a strong independent check of both decompression and relocation.

## Address convention and memory model

All function addresses in this book and `analysis/cb.rz` are linear offsets
from the DOS load-module base, not file offsets. Add `0x200` for the unpacked
file offset. At the captured load segment, add physical base `0x6270` for a
physical address.

The C startup sets `DS` to load segment plus `0x0EBA`, so a source-level data
reference such as `DS:08DA` corresponds to load offset `0xF47A`. Rizin does not
automatically perform this segment addition and may present such immediates as
references into low code addresses.

The evidence is consistent with the Microsoft C small memory model: ordinary
code and data pointers are 16-bit, all normal C calls are near within one code
segment, and explicit far pointers are used for loaded resources and driver
interfaces. The initialized data contains:

```text
MS Run-Time Library - Copyright (c) 1988, Microsoft Corp
```

This identifies the Microsoft C run time and Microsoft LINK/EXEPACK, but does
not by itself prove an exact compiler release.
