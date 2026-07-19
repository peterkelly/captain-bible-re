from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from inspect_bin import OPCODE_NAMES, OPCODE_SCHEMAS  # noqa: E402


OPCODE_ROW = re.compile(
    r"^\| `([0-9A-F]{2})` \| (`[^`]*`|none) \| `([^`]+)`:"
)


class CleanRoomSpecificationTests(unittest.TestCase):
    def test_opcode_catalog_is_complete_and_matches_decoder(self):
        schemas = {}
        names = {}
        path = ROOT / "spec" / "src" / "bytecode.md"
        for line in path.read_text(encoding="utf-8").splitlines():
            if match := OPCODE_ROW.match(line):
                opcode = int(match.group(1), 16)
                schema = match.group(2).strip("`")
                schemas[opcode] = "" if schema == "none" else schema
                names[opcode] = match.group(3)
        self.assertEqual(schemas, OPCODE_SCHEMAS)
        self.assertEqual(names, OPCODE_NAMES)

    def test_spec_has_no_research_method_dependencies(self):
        forbidden = re.compile(
            r"\b(?:QEMU|Rizin|disassembl(?:y|er|ing)|decompil(?:e|er|ing))\b",
            re.IGNORECASE,
        )
        findings = []
        for path in sorted((ROOT / "spec" / "src").glob("*.md")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if forbidden.search(line):
                    findings.append(f"{path.name}:{line_number}: {line}")
        self.assertEqual(findings, [])

    def test_spec_contains_expected_chapter_set(self):
        expected = {
            "introduction.md",
            "game-overview.md",
            "compatibility.md",
            "lifecycle.md",
            "input-ui.md",
            "resources.md",
            "graphics.md",
            "audio.md",
            "text.md",
            "bytecode.md",
            "scene-runtime.md",
            "world.md",
            "dialogue-study.md",
            "combat.md",
            "state-progression.md",
            "saves.md",
            "configuration.md",
            "conformance.md",
            "boundaries.md",
        }
        actual = {
            path.name
            for path in (ROOT / "spec" / "src").glob("*.md")
            if path.name != "SUMMARY.md"
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
