# Text Resource Formats

Captain Bible divides its study and gameplay text between translation-specific
verse indexes inside `DD1.DAT` and translation-independent companion files
named `DDLA` through `DDLG` and `DDLR`. The executable joins them at runtime.

## Resource families

The first character of an extensionless archive name selects a Bible
translation:

| Prefix | Translation | Command-line letter | Runtime index |
|---|---|---|---:|
| `K` | King James Version | `K` | 0 |
| `N` | New International Version | `N` | 1 |
| `R` | Revised Standard Version | `R` | 2 |
| `T` | The Living Bible | `T` | 3 |

The second character is a bank letter `A` through `G` or `R`. It selects the
companion file with the same suffix, such as resource `NA` plus file `DDLA`.
There are 319 logical verse records in each translation:

| Bank | Verse records | Companion bytes | Terminal offset |
|---|---:|---:|---:|
| `A` | 47 | 10,065 | `0x2751` |
| `B` | 40 | 8,253 | `0x203D` |
| `C` | 46 | 4,020 | `0x0FB4` |
| `D` | 46 | 14,973 | `0x3A7D` |
| `E` | 42 | 10,489 | `0x28F9` |
| `F` | 46 | 10,257 | `0x2811` |
| `G` | 44 | 9,993 | `0x2709` |
| `R` | 8 | 696 | `0x02B8` |

The archive contains 33 rather than 32 extensionless members because `NG`
appears at directory indexes 199 and 206. Their expanded bytes are identical.

## Extensionless verse index

Each ordinary index record has a three-byte header followed by text:

| Offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 1 | Nonzero selector byte used by scene logic. |
| `0x01` | 2 | Little-endian offset into the companion `DDL` file. |
| `0x03` | variable | NUL-terminated CP437 `citation|verse` text. |

The final record is only `00` plus a little-endian terminal offset. That
offset equals the companion file's exact byte length and lets the game derive
the final ordinary record's span. Offsets are nondecreasing rather than
strictly increasing: repeated offsets represent verses with no associated
companion records.

The selector is an exact lookup key, not a record type. Function
`find_text_record_by_selector` linearly compares it against the loaded table.
Selectors `0xE0` and above mark mature-topic records for filtering.

## `DDL` companion stream

Every companion record is an ASCII tag byte followed immediately by a
NUL-terminated CP437 string. There is no file header or terminal marker; index
offsets and the file size delimit the relevant ranges.

| Tag | Count in all eight files | Game export heading |
|---|---:|---|
| `L` | 277 | `CYBER LIE:` |
| `P` | 123 | `PARAPHRASE:` |
| `W` | 210 | `WRONG GUESS:` |
| `C` | 67 | `CORRECT GUESS:` |
| `E` | 68 | `EXPLANATION OF CORRECT GUESS:` |
| `*` | 58 | `CONVERSATION WITH VICTIM:` |
| `M` | 255 | Numeric or internal metadata; not printed by the exporter. |

All eight files contain 1,058 tagged records. Of these, 1,057 fall in indexed
verse spans. `DDLF` begins with one 26-byte `E` preamble before its first index
offset; the game does not associate it with a verse. Some verse spans contain
several records with the same tag, particularly multiple wrong guesses or
metadata values.

The built-in `-gXX` export mask connects the two formats. Bit 1 prints `L`,
bit 2 prints `P`, bit 3 prints `*`, bit 4 prints `W`, `C`, and `E`, and bit 5
prints the citation and verse from the index. Bit 0 prints the numbered record
heading. `M` is consumed by gameplay helpers but omitted from study output.

## Executable implementation

`load_text_bank` at load offset `0x629C` constructs the two-character archive
name from the selected translation and requested bank. It loads the
extensionless resource and turns every index record into a ten-byte runtime
descriptor containing a far text pointer, selector, companion offset, and
span. It then opens the corresponding `DDL` file for random access.

| Load offset | Current name | Role |
|---:|---|---|
| `0x5AD6` | `find_text_record_by_selector` | Linearly find the runtime descriptor with a requested selector. |
| `0x5CE2` | `copy_text_record_component` | Return the verse or a selected tag occurrence from its companion span. |
| `0x5EE7` | `write_wrapped_export_text` | Wrap study text at 70 columns and write it to the export stream. |
| `0x5F92` | `export_game_text` | Apply the `-gXX` mask and emit the complete study file. |
| `0x629C` | `load_text_bank` | Load and join one verse index and `DDL` bank. |

The loader reads the next record's offset to compute each span, including the
terminal zero record for the last span. `copy_text_record_component` seeks to
that offset in the open companion file, reads exactly the computed span, and
walks its tagged NUL strings.

## QEMU export validation

Ran the original executable's built-in exporter in a visible, silent FreeDOS
QEMU session with `-g63 -sTSTUDY.TXT`. The installed `SOUND.5` configuration
contains translation index 1, so it enforced NIV despite the requested `T`,
as the manual warns an installation lock may do.

The game produced a 132,510-byte file with SHA-256
`c9ebe2cc4fbd00cd709d87761b38f6a8843eae99ceaa75cef842b93364dad0bc`.
After normalizing the exporter's line wrapping, all 302 emitted verses match
the parsed `N` resources exactly. The only 17 verses absent from the export
have selectors `0xE1` through `0xE4`; these are precisely the records rejected
by the executable's active mature-topic filter. The export also reproduces
the parsed `L`, `P`, `W`, `C`, `E`, and `*` companion strings under their
documented headings.

## Inspection tool

`tools/inspect_text_resources.py` validates both formats, joins index spans to
their companion records, and displays the game-facing result. For example:

```sh
tools/inspect_text_resources.py \
  CB/DD1.DAT --data-dir CB \
  --translation N --bank A --record 0
```

Omit `--record` to display the complete bank. Translation choices are `K`,
`N`, `R`, and `T`; bank choices are `A` through `G` and `R`.
