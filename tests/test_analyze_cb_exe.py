import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "analyze_cb_exe.py"
SPEC = importlib.util.spec_from_file_location("analyze_cb_exe", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AnalyzeCaptainBibleExecutableTests(unittest.TestCase):
    def test_size_field_round_trip(self):
        for length in (1, 511, 512, 513, 75_776):
            encoded = MODULE.encode_mz_size(length)
            self.assertEqual(MODULE.decode_mz_size(*encoded), length)

    def test_captain_bible_unpack_regression(self):
        source = ROOT / "CB" / "CB.EXE"
        if not source.exists():
            self.skipTest("the ignored, user-supplied CB.EXE is not present")
        packed = MODULE.parse_mz(source.read_bytes())
        result = MODULE.unpack_exepack(packed)
        output = MODULE.serialize_mz(result.executable)

        self.assertEqual(len(result.executable.body), 75_264)
        self.assertEqual(len(result.executable.relocations), 43)
        self.assertEqual((result.executable.cs, result.executable.ip), (0, 0xCB5C))
        self.assertEqual(len(output), 75_776)
        self.assertEqual(
            hashlib.sha256(output).hexdigest(),
            "4875f83d6d2ba9c1cc4f058e351e453010c6a5976e1b15976b676689f9747643",
        )

    def test_qemu_title_dump_matches_unpacked_prefix(self):
        source = ROOT / "CB" / "CB.EXE"
        dump = ROOT / "build" / "dumps" / "title-physical-1m.bin"
        if not source.exists() or not dump.exists():
            self.skipTest("the game executable or generated QEMU dump is absent")
        result = MODULE.unpack_exepack(MODULE.parse_mz(source.read_bytes()))
        compared, prefix, different = MODULE.compare_memory(
            result.executable, dump.read_bytes(), 0x627
        )

        self.assertEqual(compared, 75_264)
        self.assertEqual(prefix, 0x905A)
        self.assertEqual(different, 5_612)


if __name__ == "__main__":
    unittest.main()
