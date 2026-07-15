from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from inspect_runtime_tables import (  # noqa: E402
    ACTION_COUNT_OFFSET,
    ACTION_TABLE_OFFSET,
    ANIMATION_COUNT_OFFSET,
    ANIMATION_TABLE_OFFSET,
    RuntimeTableError,
    THREAD_CURRENT_OFFSET,
    THREAD_TABLE_OFFSET,
    parse_runtime_tables,
)


class RuntimeTableTests(unittest.TestCase):
    def test_parse_runtime_tables(self) -> None:
        segment = 0x100
        base = segment * 16
        memory = bytearray(0x10000)
        struct.pack_into("<H", memory, base + ACTION_COUNT_OFFSET, 1)
        struct.pack_into(
            "<HHHHBB",
            memory,
            base + ACTION_TABLE_OFFSET,
            0x1234,
            151,
            61,
            0x4567,
            1,
            0,
        )
        struct.pack_into("<H", memory, base + ANIMATION_COUNT_OFFSET, 1)
        struct.pack_into(
            "<HHHhBBH",
            memory,
            base + ANIMATION_TABLE_OFFSET,
            0x0100,
            0x010A,
            100,
            -24,
            5,
            2,
            0x0304,
        )
        struct.pack_into("<H", memory, base + THREAD_CURRENT_OFFSET, 2)
        struct.pack_into("<H", memory, base + THREAD_TABLE_OFFSET, 0x2222)
        memory[base + THREAD_TABLE_OFFSET + 2 : base + THREAD_TABLE_OFFSET + 12] = (
            bytes(range(10))
        )
        struct.pack_into("<hBB", memory, base + THREAD_TABLE_OFFSET + 12, -7, 1, 3)

        tables = parse_runtime_tables(bytes(memory), segment, thread_slots=1)

        self.assertEqual(tables.action_records[0].target, 0x1234)
        self.assertEqual(tables.action_records[0].selector_offset, 0x4567)
        self.assertEqual(tables.animation_records[0].link, -24)
        self.assertEqual(tables.animation_records[0].timing, 0x0304)
        self.assertEqual(tables.current_thread, 2)
        self.assertEqual(tables.thread_records[0].cursor, 0x2222)
        self.assertEqual(tables.thread_records[0].delay, -7)
        self.assertEqual(tables.thread_records[0].active, 1)
        self.assertEqual(tables.thread_records[0].status, 3)

    def test_rejects_short_dump(self) -> None:
        with self.assertRaises(RuntimeTableError):
            parse_runtime_tables(bytes(128), 0x100)

    def test_rejects_implausible_count(self) -> None:
        segment = 0x100
        memory = bytearray(0x10000)
        struct.pack_into(
            "<H", memory, segment * 16 + ACTION_COUNT_OFFSET, 0x101
        )
        with self.assertRaisesRegex(RuntimeTableError, "implausible action"):
            parse_runtime_tables(bytes(memory), segment)


if __name__ == "__main__":
    unittest.main()
