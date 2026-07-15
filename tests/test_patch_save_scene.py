from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_save_scene", ROOT / "tools" / "patch_save_scene.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PatchSaveSceneTests(unittest.TestCase):
    def test_patch_scene_replaces_both_fields_only(self) -> None:
        original = bytes(
            (index * 37) & 0xFF for index in range(MODULE.STATE_SIZE)
        )

        patched = MODULE.patch_scene(original, "COMBAT1")

        expected_field = b"COMBAT1" + bytes(MODULE.SCENE_FIELD_SIZE - 7)
        for offset in MODULE.SCENE_FIELD_OFFSETS:
            self.assertEqual(
                patched[offset : offset + MODULE.SCENE_FIELD_SIZE],
                expected_field,
            )
        changed = set()
        for offset in MODULE.SCENE_FIELD_OFFSETS:
            changed.update(range(offset, offset + MODULE.SCENE_FIELD_SIZE))
        self.assertTrue(
            all(
                before == after or index in changed
                for index, (before, after) in enumerate(zip(original, patched))
            )
        )

    def test_patch_scene_rejects_invalid_names(self) -> None:
        for name in ("", "x" * 20, "COMBATé"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                MODULE.patch_scene(bytes(MODULE.STATE_SIZE), name)

    def test_patch_scene_rejects_non_state_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 2752"):
            MODULE.patch_scene(bytes(243), "COMBAT1")


if __name__ == "__main__":
    unittest.main()
