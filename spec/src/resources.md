# Resource Names and `DD1.DAT`

## External files

A compatible installation uses these game-owned inputs:

| Name | Purpose |
|---|---|
| `DD1.DAT` | Named archive containing scenes, art, palettes, maps, audio, and verse indexes |
| `DDLA` through `DDLG`, `DDLR` | Companion gameplay and study text |
| `SOUND.5` | Installation policy locks |
| `<player>.SV0`, `.SV1` through `.SV9`, `.SVQ` | Save labels and game states |

The historical `SOUND.1` through `SOUND.4` files contain platform-specific
audio drivers and timbres. A modern engine MAY ignore them and use native
audio services. `SOUND.5` remains relevant because it carries content policy.

## Archive directory

`DD1.DAT` begins with a 16-bit member count followed by that many 24-byte
records:

| Record offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 8 | Zero-padded ASCII base name |
| `0x08` | 1 | Storage marker: 0 raw, 1 compressed |
| `0x09` | 3 | Zero-padded ASCII extension without a dot |
| `0x0C` | 4 | Absolute payload offset |
| `0x10` | 4 | Expanded size |
| `0x14` | 4 | Stored size including payload magic |

All numeric fields are unsigned. Padding after the first NUL in either name
field MUST be zero. Payloads MUST be contiguous in directory order, the first
payload begins immediately after the directory, and the final payload ends at
the end of the archive.

Every payload begins with ASCII `GC`. The two magic bytes count toward stored
size but not expanded size.

The supplied archive declares 369 entries:

| Extension | Count | Meaning |
|---|---:|---|
| `ART` | 143 | Indexed artwork and frames |
| `BIN` | 62 | Scene bytecode and embedded data |
| `ABT` | 41 | Compressed digital effects |
| `PAL` | 37 | Complete indexed palettes |
| none | 33 | Translation-specific verse indexes |
| `XMI` | 32 | Music sequences |
| `MAP` | 21 | Building maps by level and difficulty |

Names are looked up case-insensitively after splitting base and extension.
The archive contains duplicate names whose contents are identical. An engine
MUST retain directory order and SHOULD return the first matching entry unless
an inspection API explicitly addresses entries by index.

## Raw payloads

For storage marker 0, the bytes after `GC` are the complete expanded resource.
The stored size MUST equal expanded size plus two.

## Compressed payloads

Storage marker 1 uses an LZW-family dictionary with codes up to 12 bits. Codes
0 through 255 are literals. Dictionary entries contain a prefix code and one
suffix byte.

Each dictionary pass proceeds as follows:

1. initialize literal entries 0 through 255;
2. read and emit one literal code;
3. use it as the prefix of entry `0x100` and set the next counter to `0x101`;
4. read a code, recursively expand and emit its phrase, save that code as the
   prefix for the following entry, and save the phrase's first byte as the
   suffix of entry `counter - 1`;
5. increment the counter and repeat; and
6. when the counter reaches `0x1001`, restart a dictionary pass by reading a
   new literal. There is no clear code.

The one-entry offset in step 4 provides the ordinary LZW case where a code can
refer to the entry currently being completed.

Codes are stored in groups of at most eight. They are not one continuous bit
stream. For a group, read all high-bit plane bytes first and then one low byte
per code. Bit 0 of each plane byte belongs to the first code, bit 1 to the
second, and so on. The first plane supplies code bit 8, the next bit 9, then
bits 10 and 11. The number of planes grows when the dictionary counter passes
`0x100`, `0x200`, `0x400`, and `0x800`.

The decoder MUST stop after exactly the declared expanded size and MUST also
consume exactly the stored compressed body. Undefined codes, cycles, truncated
planes or low bytes, output overflow, and unused trailing bytes are errors.

## Resource naming conventions

Scene services construct several names:

- a scene base becomes `<base>.BIN`;
- art and palette commands append `.ART` and `.PAL`;
- map level `A` through `G` combines with `E`, `N`, or `D`, then `.MAP`;
- effect number `n` becomes `D%03d.ABT`;
- music number `n` becomes `MUS%03d.XMI` or `IBM%03d.XMI` according to the
  selected music backend; and
- a text translation letter plus bank letter addresses an extensionless
  archive member and external companion `DDL<bank>`.

Names embedded in mutable `BIN` data may be patched before use. Resource
lookup MUST read the current scene-buffer bytes, not a precomputed immutable
string table.

## Validation policy

An engine MUST bounds-check the directory before following payload offsets and
MUST check `GC` before decoding. It SHOULD report the member name and directory
index in format errors. It MUST NOT accept overlapping payloads, expanded-size
mismatches, nonzero directory padding, or archive trailing data in strict
conformance mode.
