# `DD1.DAT` Resource Container

## Container directory

`DD1.DAT` is the game's main named-resource archive. The supplied file is
1,866,068 bytes and has SHA-256
`a395fcf9f19d655a6440b5b8ab213983eb7d34a99810b763a9c95360f98f9562`.
Its first little-endian word is the member count, followed immediately by
fixed 24-byte records:

| Record offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 8 | Zero-padded ASCII base name. |
| `0x08` | 1 | Storage marker: 0 is raw and 1 is compressed. |
| `0x09` | 3 | Zero-padded ASCII extension, without a dot. |
| `0x0C` | 4 | Absolute payload offset, little endian. |
| `0x10` | 4 | Expanded size. |
| `0x14` | 4 | Stored size, including the two-byte payload magic. |

The file declares 369 records. Consequently, the directory occupies
`2 + 369 * 24 = 0x229A` bytes, exactly the offset of the first payload.
Payloads are contiguous in directory order, and the last one ends exactly at
the end of the container. Every payload starts with ASCII `GC`; lookup code at
`0x99AB` seeks to the recorded offset and verifies this word before returning
the member.

The recovered population is:

| Extension | Members |
|---|---:|
| `ART` | 143 |
| `BIN` | 62 |
| `ABT` | 41 |
| `PAL` | 37 |
| no extension | 33 |
| `XMI` | 32 |
| `MAP` | 21 |

There are 38 raw members containing 203,303 expanded bytes and 331 compressed
members containing 5,340,520 expanded bytes. The complete archive expands to
5,543,823 bytes. Three names occur twice: `GANTRY.PAL`, `HOLEA.ART`, and `NG`.
Each repeated pair also has identical extracted content, but its two directory
slots are retained rather than silently deduplicated.

Representative records connect the static directory to the QEMU trace:

| Index | Marker | Payload offset | Stored | Expanded | Name |
|---:|---:|---:|---:|---:|---|
| 0 | 1 | `0x229A` | 576 | 1,041 | `BOSS2.ART` |
| 1 | 1 | `0x24DA` | 431 | 640 | `LOGO.BIN` |
| 82 | 1 | `0x6F69C` | 16,138 | 53,213 | `RUN.ART` |

The startup trace's seek to `0x24DA` and its 431-byte stored and 640-byte
expanded values match `LOGO.BIN` exactly. `RUN.ART`, which appears as a static
name passed to the art loader, is likewise present only as archive member 82;
DOS never opens it as a separate path.

## Payload encodings

For marker 0, the bytes following `GC` are the resource verbatim. The stored
size is therefore always the expanded size plus two.

Marker 1 selects the dictionary decoder at load offset `0x9CA4`. It is an
LZW-family scheme with an unusual byte-plane representation for code bits:

1. Dictionary codes 0 through 255 are literal bytes. Each has a prefix of
   `-1` and a suffix equal to the byte value.
2. At the start of a dictionary pass, the decoder reads and emits one literal,
   stores it as the prefix of entry `0x100`, and sets its code counter to
   `0x101`.
3. It reads the next code, saves that code as the prefix for the following
   dictionary entry, recursively emits the referenced phrase, and saves that
   phrase's first byte as the suffix of entry `counter - 1`. This one-slot
   offset implements the normal LZW special case where the current phrase can
   refer to the entry being completed.
4. When the counter reaches `0x1001`, the dictionary pass restarts with a new
   literal. There is no clear code in the stream.

Codes do not form a conventional contiguous bitstream. Every group of up to
eight codes stores all required high-bit planes first, followed by the eight
low bytes. Bit 0 of each plane byte belongs to the first code in the group,
bit 1 to the second, and so on. One plane supplies code bit 8, the next bit 9,
up to four planes for the 12-bit dictionary range. The number of planes grows
as the counter passes `0x100`, `0x200`, `0x400`, and `0x800`.

The implementation in `tools/extract_dd1.py` follows the assembly's precise
prefix/suffix update order. It also rejects truncated streams, undefined
codes, dictionary cycles, over-expansion, unused compressed bytes, invalid
directory padding, noncontiguous payloads, bad `GC` magic, and trailing
container data. Regression outputs include:

| Member | Bytes | Extracted SHA-256 |
|---|---:|---|
| `LOGO.BIN` | 640 | `8580d3ff93c6e775aa71334c50762ffde2b1f42a320ee362f5608bd8cbc51424` |
| `RUN.ART` | 53,213 | `c4b00d2e31e9dec81cc419dc577086b143a546a4a0b618dbe5600df4e5fd4ac0` |

## Extractor usage

List the directory:

```sh
tools/extract_dd1.py --list CB/DD1.DAT
```

Extract one uniquely named member:

```sh
tools/extract_dd1.py \
  --extract RUN.ART \
  --output build/dd1/RUN.ART \
  CB/DD1.DAT
```

Extract all members with their directory indices preserved:

```sh
tools/extract_dd1.py --extract-all build/dd1/all CB/DD1.DAT
```

The all-members form creates names such as `082_RUN.ART`; the numeric prefix
prevents duplicate archive names from overwriting one another. A duplicate can
also be selected explicitly with `--index` and `--output`.

## Executable routines

| Load offset | Current name | Evidence |
|---:|---|---|
| `0x97D0` | `archive_load_member` | Looks up a record, then dispatches marker 0 to the raw reader or marker 1 to the decoder. |
| `0x99AB` | `archive_lookup_member` | Uppercases and splits a requested name, scans 24-byte records, seeks to the payload, and checks `GC`. |
| `0x9BEF` | `archive_read_raw_member` | Copies the declared expanded length to a caller buffer in far-memory chunks. |
| `0x9C5F` | `archive_refill_input` | Refills the decoder's archive input buffer. |
| `0x9CA4` | `archive_decode_member` | Initializes literals, reads bit planes and codes, and builds the dictionary. |
| `0x9D98` | `archive_expand_code` | Recursively walks prefix links and emits suffix bytes. |

These names refer to offsets within the unpacked load module, using the same
address convention as the rest of this book.
