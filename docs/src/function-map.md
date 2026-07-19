# Symbol and Function Map

The checked symbol catalog is `analysis/symbol-map.tsv`. It records every
project-assigned name in `analysis/cb.rz`, rather than only a selected list of
interesting routines. The current map contains 175 entries:

| Kind | Count | Meaning |
|---|---:|---|
| Function | 140 | Application, driver API, decoder, rendering, and Microsoft C routines |
| BIN handler | 26 | Named cases in the 145-entry scene-opcode dispatcher |
| Data | 9 | Strings and one recovered room-orientation table |

All offsets are 16-bit linear offsets from the DOS load-module base. Add
`0x200` to obtain an offset in `CB_UNPACKED.EXE`. For the recorded QEMU load at
segment `0627`, add physical base `0x6270`. Initialized data references also
require the documented `DS` base translation; the executable chapter gives
the complete address convention.

## Confidence scale

Each catalog row has its own evidence statement and one of these confidence
levels:

| Level | Requirement | Current entries |
|---|---|---:|
| Verified | Static semantics plus independent agreement with QEMU state, traced I/O, supplied saves, or exhaustive resource decoding | 82 |
| High | Instruction behavior, callers, data layout, and cross-resource use uniquely support the name | 93 |
| Medium | Best current interpretation, but a material semantic ambiguity remains | 0 |

“Verified” does not mean source-level names were recovered: the executable has
no debug symbols. It means the descriptive name has an independent check
beyond recognizing the disassembly. “High” is still strong enough to load into
Rizin. Unresolved candidate routines remain unnamed rather than being promoted
to the catalog with speculative labels.

## Coverage

The catalog groups evidence by subsystem. Counts include functions, handlers,
and data symbols:

| Subsystem | Entries | Principal evidence |
|---|---:|---|
| Bytecode | 33 | Complete opcode layouts, switch targets, and decoded BIN corpus |
| Runtime | 16 | Microsoft C startup banner, standard implementations, and call sites |
| Graphics | 14 | ART/PAL validation and QEMU framebuffer comparison |
| Saves | 10 | Exact supplied SV0/SV1–SV9/SVQ structures and copy directions |
| Text | 10 | All translation banks and byte-identical QEMU export |
| Audio | 41 | ABT/XMI validation, live PCM, INT 66h traces, and published driver ABI |
| State | 9 | Script corpus, saved words, flag masks, and faith behavior |
| Archive | 7 | Exact extraction of all 369 DD1 members |
| Input | 7 | Action tables, keyboard/mouse callers, and BIOS interfaces |
| Startup | 6 | Entry flow, DOS trace, configuration, and resource loads |
| Animation | 5 | Recovered runtime records and combat sequence corpus |
| Dialogue | 5 | Live choice table and study-Bible suspension sequence |
| Maps | 5 | All 21 maps, saved mutations, and room dispatch |
| Hardware | 3 | VGA/mouse BIOS checks and traced configuration open |
| Scene display | 3 | Live ten-byte record table and framebuffer path |
| Files | 1 | Traced DOS open/seek/read/close sequence |

The TSV preserves one concise piece of evidence per individual entry. For
example, `decode_abt` cites both exhaustive decoding and the live `D003` PCM
match, while `normalize_map_cells` remains High because its loop is clear but
has not received an independent runtime capture.

## Reproducible audit

Validate the catalog against every `afn`, `fr`, and named data flag in the
Rizin script:

```sh
tools/inspect_symbol_map.py
```

The command rejects missing or extra names, changed function/data offsets,
duplicate names, duplicate kind/offset pairs, unknown confidence labels, and
empty evidence. It can also filter the readable listing:

```sh
tools/inspect_symbol_map.py --kind function
tools/inspect_symbol_map.py --confidence verified
```

BIN handler addresses originate in Rizin's switch analysis, because `cb.rz`
renames generated case flags rather than declaring those addresses directly.
Regenerate and verify that final layer with:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c fl build/analysis/CB_UNPACKED.EXE \
  > build/analysis/cb-flags.txt
tools/inspect_symbol_map.py \
  --rizin-flags build/analysis/cb-flags.txt
```

The current Rizin run resolves all 71 handlers at the cataloged offsets and
emits no script errors. Archive-backed unit tests enforce the 140/71/9 counts
and exact catalog-to-script coverage without requiring Rizin during the normal
test suite.

## Boundaries

Rizin's recursive analysis currently proposes roughly 340 functions, but
several candidates cross jump tables or data. The catalog therefore does not
claim that 140 functions are the whole executable. They are the complete set
of names supported by the reverse-engineering evidence so far.

The 71 handler names cover every distinct implementation needed to describe
all 145 opcodes; shared implementations account for dialogue variants, four
no-op values, four edge-transition callbacks, and other paired commands.
Unused handlers keep low-level names when shipped scripts cannot establish a
more specific gameplay role.
