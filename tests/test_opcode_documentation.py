import re
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from inspect_bin import OPCODE_NAMES, OPCODE_SCHEMAS  # noqa: E402


OPCODE_RANGE = re.compile(
    r"`0x([0-9A-Fa-f]{2})`(?:\s*[–-]\s*`0x([0-9A-Fa-f]{2})`)?"
)
COMPACT_SCHEMA = re.compile(r"^(?:none|[BHzp9s]+)(?:/[BHzp9s]+)*$")


def documented_catalog() -> dict[int, tuple[str, str, bool]]:
    catalog: dict[int, tuple[str, str, bool]] = {}
    for line in (ROOT / "docs/src/scene-bytecode.md").read_text().splitlines():
        if not line.startswith("| `0x"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        opcodes = []
        for match in OPCODE_RANGE.finditer(cells[0]):
            first = int(match.group(1), 16)
            last = int(match.group(2), 16) if match.group(2) else first
            opcodes.extend(range(first, last + 1))
        encoded = cells[1].replace("`", "").replace(" ", "")
        encoded = "" if encoded == "none" else encoded
        alternatives = encoded.split("/")
        if len(alternatives) == len(opcodes):
            assignments = zip(opcodes, alternatives)
        else:
            assignments = ((opcode, encoded) for opcode in opcodes)
        for opcode, schema in assignments:
            if opcode in catalog:
                raise AssertionError(f"opcode {opcode:#04x} is documented twice")
            name = cells[2].replace("`", "")
            catalog[opcode] = (schema, name, "**Unused.**" in cells[3])
    return catalog


class OpcodeDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = documented_catalog()

    def test_complete_book_catalog_matches_machine_readable_schemas(self):
        schemas = {
            opcode: row[0] for opcode, row in self.catalog.items()
        }
        self.assertEqual(schemas, OPCODE_SCHEMAS)

    def test_complete_book_catalog_matches_machine_readable_names(self):
        names = {opcode: row[1] for opcode, row in self.catalog.items()}
        self.assertEqual(names, OPCODE_NAMES)

    def test_every_unshipped_opcode_is_marked_unused(self):
        report_rows = (
            ROOT / "analysis/opcode-audit.tsv"
        ).read_text().splitlines()[1:]
        unused = {
            int(fields[0], 16)
            for row in report_rows
            if (fields := row.split("\t"))[8] == "0"
        }
        documented_unused = {
            opcode for opcode, row in self.catalog.items() if row[2]
        }
        self.assertEqual(documented_unused, unused)

    def test_compact_schemas_in_every_book_chapter_match_the_catalog(self):
        mismatches = []
        for path in sorted((ROOT / "docs/src").glob("*.md")):
            if path.name == "progress-log.md":
                continue
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                if not line.startswith("|") or "`0x" not in line:
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) < 2:
                    continue
                encoded = cells[1].replace("`", "").replace(" ", "")
                if COMPACT_SCHEMA.fullmatch(encoded) is None:
                    continue
                opcodes = []
                for match in OPCODE_RANGE.finditer(cells[0]):
                    first = int(match.group(1), 16)
                    last = int(match.group(2), 16) if match.group(2) else first
                    if 1 <= first <= 0x91 and 1 <= last <= 0x91:
                        opcodes.extend(range(first, last + 1))
                if not opcodes:
                    continue
                alternatives = encoded.split("/")
                if len(alternatives) != len(opcodes):
                    alternatives = [encoded] * len(opcodes)
                for opcode, schema in zip(opcodes, alternatives):
                    schema = "" if schema == "none" else schema
                    if schema != OPCODE_SCHEMAS[opcode]:
                        mismatches.append(
                            f"{path.name}:{line_number}: opcode {opcode:#04x} "
                            f"uses {schema!r}, expected {OPCODE_SCHEMAS[opcode]!r}"
                        )
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
