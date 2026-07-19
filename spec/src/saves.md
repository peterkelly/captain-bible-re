# Save and restore

## File family

The active player prefix defaults to `DDGAMES` and may be replaced by a
non-option command-line argument. It is combined with these suffixes:

| File | Purpose |
|---|---|
| `.SV0` | Nine-slot label index. |
| `.SV1`–`.SV9` | Normal save states. |
| `.SVQ` | Quick-save state used by F10 and F9. |

The prefix is not stored inside a save. Files contain no header, checksum,
version, or compression. Compatibility is determined by suffix and exact
size.

For an original filename-compatible launch, an extensionless prefix SHOULD be
at most eight characters. A complete path prefix is also valid. Native ports
MAY allow longer host paths as long as the resulting save family remains
unambiguous.

## Label index

`SV0` is exactly 243 bytes: nine 27-byte CP437 NUL-terminated label buffers.
Slot `n` begins at `(n - 1) * 27`. Bytes after the first NUL are semantically
irrelevant and MAY be zeroed by a new implementation. A missing index behaves
as nine `(EMPTY)` labels. User-entered labels are limited to 26 encoded bytes
plus NUL. Selecting an empty slot without replacing its label MAY initialize
`Game 1` through `Game 9` according to the slot. Normal saving updates the
relevant label and rewrites the complete index. Quick save does not require an
index entry.

## State layout

Every normal or quick state is exactly 2752 bytes:

| Offset | Size | Meaning |
|---:|---:|---|
| `000` | 200 | Checkpoint copy of 100 signed variables. |
| `0C8` | 200 | Live copy of 100 signed variables. |
| `190` | 66 | Checkpoint text-descriptor state bytes. |
| `1D2` | 660 | 66 live ten-byte text descriptors. |
| `466` | 20 | Checkpoint scene-resource C-string buffer. |
| `47A` | 20 | Live scene-resource C-string buffer. |
| `48E` | 20 | Checkpoint scene extension/entry C-string buffer. |
| `4A2` | 20 | Live scene extension/entry C-string buffer. |
| `4B6` | 2 | Translation index. |
| `4B8` | 2 | Music-enabled word. |
| `4BA` | 2 | Effects-enabled word. |
| `4BC` | 2 | Checkpoint text-bank character. |
| `4BE` | 2 | Live text-bank character. |
| `4C0` | 768 | Live world map. |
| `7C0` | 768 | Checkpoint world map. |

Words are little-endian. The four 20-byte fields are NUL-terminated CP437
buffers; bytes following NUL are not semantic.

Each live descriptor is:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 2 | Legacy pointer word; nonportable. |
| 2 | 2 | Legacy pointer word; nonportable. |
| 4 | 1 | Persistent record state. |
| 5 | 1 | Record selector. |
| 6 | 2 | Offset in the companion text stream. |
| 8 | 2 | Span in that stream. |

A portable engine MUST reconstruct the first four bytes from its own loaded
text representation and MUST NOT interpret serialized pointer words as host
addresses. When writing an original-format save it SHOULD emit zero for those
words. Selectors, offsets, spans, and state bytes MUST be preserved.

## Checkpoints

The checkpoint is distinct from the act of writing a file. New-session setup
and bytecode opcode `55` copy live variables, each descriptor's state byte,
the scene strings, bank character, and live map to their checkpoint fields.
Saving serializes both copies without first refreshing the checkpoint.

Restoring a selected save loads both serialized copies, copies the checkpoint
fields into live state, reconstructs text descriptors, applies the persisted
translation/music/effects settings, and resumes the checkpoint scene. The
serialized live fields remain part of the compatible file even though this
restore step replaces them. Opcode `67` requests the retained restore path.

## Robustness requirements

Original-format readers MUST reject files whose size is not exactly 243 or
2752 bytes, short reads, unterminated semantic buffers, invalid translation or
bank values, or out-of-range structural descriptor spans. Loading MUST be
atomic: a rejected file cannot partially replace a running session.

Original-format writers SHOULD write a temporary sibling, flush it, and
atomically replace the destination where the host platform supports that.
These safety guarantees intentionally improve on historical partial-read and
partial-write behavior without changing valid-save compatibility.
