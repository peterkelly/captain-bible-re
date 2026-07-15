#!/usr/bin/env python3
"""Check mdBook structure, local links, anchors, and repository commands."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import shlex
import sys


LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```(\S*)\s*$")
SUMMARY_LINK_RE = re.compile(r"^\s*-\s+\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)\s*$")


def heading_slug(heading: str) -> str:
    """Approximate mdBook's GitHub-style heading identifier."""

    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"[`*_~]", "", heading).strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return re.sub(r"[ -]+", "-", heading).strip("-")


def markdown_anchors(path: Path) -> set[str]:
    anchors = set()
    counts: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = heading_slug(match.group(1))
        if not base:
            continue
        suffix = counts[base]
        counts[base] += 1
        anchors.add(base if suffix == 0 else f"{base}-{suffix}")
    return anchors


def _link_target(raw_target: str) -> tuple[str, str]:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(maxsplit=1)[0]
    path, separator, anchor = target.partition("#")
    return path, anchor if separator else ""


def check_links(markdown: Path) -> list[str]:
    errors = []
    text = markdown.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        raw_target = match.group(1)
        path_text, anchor = _link_target(raw_target)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", path_text):
            continue
        target = markdown if not path_text else (markdown.parent / path_text)
        if not target.exists():
            errors.append(f"{markdown}: missing link target {path_text!r}")
            continue
        if anchor and target.suffix.lower() == ".md":
            if anchor not in markdown_anchors(target):
                errors.append(
                    f"{markdown}: missing anchor {anchor!r} in {target}"
                )
    return errors


def shell_blocks(markdown: Path) -> tuple[tuple[int, str], ...]:
    """Return logical command lines from fenced sh/bash blocks."""

    commands = []
    language = ""
    logical = ""
    logical_start = 0
    for line_number, line in enumerate(
        markdown.read_text(encoding="utf-8").splitlines(), 1
    ):
        if match := FENCE_RE.match(line):
            if language:
                language = ""
                logical = ""
            else:
                language = match.group(1).lower()
            continue
        if language not in {"sh", "bash", "shell"}:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not logical:
            logical_start = line_number
        logical += stripped[:-1] + " " if stripped.endswith("\\") else stripped
        if not stripped.endswith("\\"):
            commands.append((logical_start, logical))
            logical = ""
    return tuple(commands)


def check_repository_commands(markdown: Path, repository: Path) -> list[str]:
    errors = []
    for line_number, command in shell_blocks(markdown):
        try:
            words = shlex.split(command)
        except ValueError as error:
            errors.append(f"{markdown}:{line_number}: invalid shell example: {error}")
            continue
        if not words:
            continue
        executable = words[0]
        if executable.startswith("tools/") or executable.startswith("./"):
            target = repository / executable.removeprefix("./")
            if not target.is_file():
                errors.append(
                    f"{markdown}:{line_number}: missing command {executable!r}"
                )
            elif not target.stat().st_mode & 0o111:
                errors.append(
                    f"{markdown}:{line_number}: command is not executable "
                    f"{executable!r}"
                )
    return errors


def check_summary(source: Path) -> list[str]:
    errors = []
    summary = source / "SUMMARY.md"
    entries = [
        match.group(1)
        for line in summary.read_text(encoding="utf-8").splitlines()
        if (match := SUMMARY_LINK_RE.match(line))
    ]
    duplicates = sorted(name for name, count in Counter(entries).items() if count > 1)
    if duplicates:
        errors.append(f"{summary}: duplicate entries {duplicates}")
    expected = {path.name for path in source.glob("*.md")} - {"SUMMARY.md"}
    actual = {Path(entry).name for entry in entries}
    if missing := sorted(expected - actual):
        errors.append(f"{summary}: unlisted chapters {missing}")
    if extra := sorted(actual - expected):
        errors.append(f"{summary}: nonexistent chapters {extra}")
    return errors


def check_documentation(repository: Path) -> list[str]:
    repository = repository.resolve()
    source = repository / "docs" / "src"
    markdown_files = [repository / "README.md", *sorted(source.glob("*.md"))]
    errors = check_summary(source)
    for markdown in markdown_files:
        errors.extend(check_links(markdown))
        errors.extend(check_repository_commands(markdown, repository))
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path.cwd(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = check_documentation(args.repository)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    source = args.repository.resolve() / "docs" / "src"
    chapter_count = len(list(source.glob("*.md"))) - 1
    print(f"documentation OK: {chapter_count} chapters plus README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
