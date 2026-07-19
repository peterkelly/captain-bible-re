from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_documentation import (  # noqa: E402
    check_documentation,
    heading_slug,
)


class DocumentationChecks(unittest.TestCase):
    def test_repository_documentation_is_consistent(self):
        self.assertEqual(check_documentation(ROOT), [])

    def test_heading_slug_matches_used_markdown_forms(self):
        self.assertEqual(heading_slug("`DD1.DAT` Resource Container"), "dd1dat-resource-container")
        self.assertEqual(heading_slug("QEMU tracing workflow"), "qemu-tracing-workflow")

    def test_reports_unlisted_chapter_broken_link_and_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "src"
            source.mkdir(parents=True)
            (root / "README.md").write_text(
                "[missing](missing.md)\n\n```sh\n./missing.sh\n```\n",
                encoding="utf-8",
            )
            (source / "SUMMARY.md").write_text(
                "# Summary\n\n- [One](one.md)\n",
                encoding="utf-8",
            )
            (source / "one.md").write_text("# One\n", encoding="utf-8")
            (source / "two.md").write_text("# Two\n", encoding="utf-8")
            errors = check_documentation(root)
            self.assertTrue(any("unlisted chapters" in error for error in errors))
            self.assertTrue(any("missing link target" in error for error in errors))
            self.assertTrue(any("missing command" in error for error in errors))

    def test_checks_optional_spec_book(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs" / "src"
            spec = root / "spec" / "src"
            docs.mkdir(parents=True)
            spec.mkdir(parents=True)
            (root / "README.md").write_text("# Test\n", encoding="utf-8")
            (docs / "SUMMARY.md").write_text(
                "# Summary\n\n- [Research](research.md)\n", encoding="utf-8"
            )
            (docs / "research.md").write_text("# Research\n", encoding="utf-8")
            (spec / "SUMMARY.md").write_text(
                "# Summary\n\n- [Spec](spec.md)\n", encoding="utf-8"
            )
            (spec / "spec.md").write_text(
                "# Spec\n\n[missing](missing.md)\n", encoding="utf-8"
            )
            errors = check_documentation(root)
            self.assertTrue(any("spec.md" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
