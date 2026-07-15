#!/usr/bin/env python3
"""Inspect Captain Bible verse indexes and their DDL companion text."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from extract_dd1 import DD1Archive


TRANSLATIONS = {
    "K": "King James Version",
    "N": "New International Version",
    "R": "Revised Standard Version",
    "T": "The Living Bible",
}
BANKS = tuple("ABCDEFG") + ("R",)
TAG_LABELS = {
    "*": "CONVERSATION WITH VICTIM",
    "C": "CORRECT GUESS",
    "E": "EXPLANATION OF CORRECT GUESS",
    "L": "CYBER LIE",
    "M": "METADATA",
    "P": "PARAPHRASE",
    "W": "WRONG GUESS",
}


class TextFormatError(ValueError):
    """Raised when a verse index or DDL text stream is malformed."""


@dataclass(frozen=True)
class VerseRecord:
    selector: int
    data_offset: int
    citation: str
    verse: str


@dataclass(frozen=True)
class VerseIndex:
    records: tuple[VerseRecord, ...]
    terminal_offset: int


@dataclass(frozen=True)
class TaggedText:
    tag: str
    offset: int
    text: str


@dataclass(frozen=True)
class StudyRecord:
    selector: int
    data_offset: int
    data_end: int
    citation: str
    verse: str
    tagged_text: tuple[TaggedText, ...]


@dataclass(frozen=True)
class TextBank:
    translation: str
    bank: str
    archive_index: int
    records: tuple[StudyRecord, ...]


def _decode_cp437(raw: bytes, context: str) -> str:
    try:
        return raw.decode("cp437")
    except UnicodeDecodeError as error:
        raise TextFormatError(f"invalid CP437 in {context}") from error


def parse_verse_index(data: bytes) -> VerseIndex:
    """Parse an extensionless DD1 verse-index resource."""

    records = []
    position = 0
    while True:
        if position + 3 > len(data):
            raise TextFormatError(f"truncated index header at {position:#x}")
        selector = data[position]
        data_offset = int.from_bytes(data[position + 1 : position + 3], "little")
        if selector == 0:
            if position + 3 != len(data):
                raise TextFormatError("bytes follow the terminal index record")
            terminal_offset = data_offset
            break

        end = data.find(b"\0", position + 3)
        if end < 0:
            raise TextFormatError(f"unterminated verse text at {position:#x}")
        raw_text = data[position + 3 : end]
        if raw_text.count(b"|") != 1:
            raise TextFormatError(
                f"verse text at {position:#x} does not have one pipe delimiter"
            )
        raw_citation, raw_verse = raw_text.split(b"|", 1)
        if not raw_citation or not raw_verse:
            raise TextFormatError(f"empty citation or verse at {position:#x}")
        records.append(
            VerseRecord(
                selector=selector,
                data_offset=data_offset,
                citation=_decode_cp437(raw_citation, "citation"),
                verse=_decode_cp437(raw_verse, "verse"),
            )
        )
        position = end + 1

    offsets = [record.data_offset for record in records] + [terminal_offset]
    if offsets != sorted(offsets):
        raise TextFormatError("companion data offsets are not nondecreasing")
    return VerseIndex(tuple(records), terminal_offset)


def parse_tagged_text(data: bytes, start: int, limit: int) -> tuple[TaggedText, ...]:
    """Parse tag-plus-NUL-string records in one indexed DDL byte range."""

    if not 0 <= start <= limit <= len(data):
        raise TextFormatError(
            f"invalid companion range {start:#x}..{limit:#x} for {len(data):#x} bytes"
        )
    records = []
    position = start
    while position < limit:
        tag_byte = data[position]
        tag = chr(tag_byte)
        if tag not in TAG_LABELS:
            value = chr(tag_byte) if 0x20 <= tag_byte < 0x7F else f"{tag_byte:#04x}"
            raise TextFormatError(f"unknown companion tag {value!r} at {position:#x}")
        end = data.find(b"\0", position + 1, limit)
        if end < 0:
            raise TextFormatError(f"unterminated companion text at {position:#x}")
        records.append(
            TaggedText(
                tag=tag,
                offset=position,
                text=_decode_cp437(data[position + 1 : end], "companion text"),
            )
        )
        position = end + 1
    return tuple(records)


def combine_text_bank(
    index: VerseIndex,
    companion: bytes,
    translation: str,
    bank: str,
    archive_index: int,
) -> TextBank:
    """Join an index resource to its DDL companion byte ranges."""

    if index.terminal_offset != len(companion):
        raise TextFormatError(
            f"terminal offset {index.terminal_offset:#x} does not match "
            f"companion size {len(companion):#x}"
        )
    records = []
    for record_index, record in enumerate(index.records):
        if record_index + 1 < len(index.records):
            data_end = index.records[record_index + 1].data_offset
        else:
            data_end = index.terminal_offset
        records.append(
            StudyRecord(
                selector=record.selector,
                data_offset=record.data_offset,
                data_end=data_end,
                citation=record.citation,
                verse=record.verse,
                tagged_text=parse_tagged_text(
                    companion, record.data_offset, data_end
                ),
            )
        )
    return TextBank(translation, bank, archive_index, tuple(records))


def load_text_bank(
    archive: DD1Archive,
    data_directory: Path,
    translation: str,
    bank: str,
) -> TextBank:
    """Load and combine one translation/bank pair from DD1 and DDL files."""

    translation = translation.upper()
    bank = bank.upper()
    if translation not in TRANSLATIONS:
        raise TextFormatError(f"unknown translation {translation!r}")
    if bank not in BANKS:
        raise TextFormatError(f"unknown text bank {bank!r}")

    resource_name = translation + bank
    matches = [
        entry
        for entry in archive.entries
        if not entry.extension and entry.name == resource_name
    ]
    if not matches:
        raise TextFormatError(f"resource {resource_name} is absent from the archive")
    payloads = {archive.extract(entry) for entry in matches}
    if len(payloads) != 1:
        raise TextFormatError(f"duplicate resource {resource_name} has different data")
    entry = matches[0]

    companion_path = data_directory / f"DDL{bank}"
    try:
        companion = companion_path.read_bytes()
    except OSError as error:
        raise TextFormatError(f"cannot read {companion_path}: {error}") from error
    parse_tagged_text(companion, 0, len(companion))
    index = parse_verse_index(archive.extract(entry))
    return combine_text_bank(index, companion, translation, bank, entry.index)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="path to DD1.DAT")
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="directory containing DDLA through DDLR",
    )
    parser.add_argument(
        "--translation", choices=TRANSLATIONS, default="T", help="Bible translation"
    )
    parser.add_argument("--bank", choices=BANKS, default="A", help="text bank")
    parser.add_argument(
        "--record", type=int, help="show only this zero-based record index"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        archive = DD1Archive.from_path(args.archive)
        bank = load_text_bank(
            archive, args.data_dir, args.translation, args.bank
        )
        if args.record is None:
            selected = tuple(enumerate(bank.records))
        elif 0 <= args.record < len(bank.records):
            selected = ((args.record, bank.records[args.record]),)
        else:
            raise TextFormatError(
                f"record {args.record} is outside 0..{len(bank.records) - 1}"
            )
    except (OSError, TextFormatError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"{TRANSLATIONS[bank.translation]}, bank {bank.bank}: "
        f"archive entry {bank.archive_index:03d}, {len(bank.records)} records"
    )
    for record_index, record in selected:
        print(
            f"\n[{record_index:02d}] selector={record.selector:#04x} "
            f"data={record.data_offset:#06x}..{record.data_end:#06x}"
        )
        print(f"VERSE: {record.citation} - {record.verse}")
        for tagged in record.tagged_text:
            print(f"{tagged.tag} {TAG_LABELS[tagged.tag]}: {tagged.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
