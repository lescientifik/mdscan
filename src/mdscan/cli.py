"""Command-line interface for mdscan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mdscan import __version__
from mdscan._types import MdFile
from mdscan.formatter import format_json, format_text
from mdscan.frontmatter import MAX_DESCRIPTION_WORDS, is_too_long, write_description
from mdscan.scanner import scan


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``mdscan`` CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "set-description":
        _run_set_description(args)
    else:
        _run_scan(args)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _run_scan(args: argparse.Namespace) -> None:
    """Execute the default scan subcommand."""
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        sys.exit(2)

    files = scan(
        directory,
        max_depth=args.max_depth,
        ignore_patterns=args.ignore or [],
    )

    has_warnings = _print_diagnostics(files)

    if args.json:
        output = format_json(files)
    else:
        output = format_text(files)

    if output:
        print(output)

    sys.exit(1 if has_warnings else 0)


def _run_set_description(args: argparse.Namespace) -> None:
    """Execute the ``set-description`` subcommand."""
    path = Path(args.file)
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        sys.exit(2)

    description: str = args.description
    write_description(path, description)

    if is_too_long(description):
        word_count = len(description.split())
        print(
            f"hint: description too long ({word_count} words, max {MAX_DESCRIPTION_WORDS})",
            file=sys.stderr,
        )
        print(f"  fix: use a haiku agent to rewrite a shorter description", file=sys.stderr)
        print(f"wrote: {path}", file=sys.stdout)
        sys.exit(1)

    print(f"wrote: {path}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _print_diagnostics(files: list[MdFile]) -> bool:
    """Print warnings and hints to stderr. Return ``True`` if any were emitted."""
    has_warnings = False
    for f in files:
        if f.description is None:
            print(
                f"warn: {f.path} — missing YAML frontmatter description, no summary available",
                file=sys.stderr,
            )
            print(
                f"  fix: use a haiku agent to read the file and write the frontmatter",
                file=sys.stderr,
            )
            has_warnings = True
        elif f.word_count is not None and f.word_count > MAX_DESCRIPTION_WORDS:
            print(
                f"hint: {f.path} — description too long"
                f" ({f.word_count} words, max {MAX_DESCRIPTION_WORDS})",
                file=sys.stderr,
            )
            print(
                f"  fix: use a haiku agent to rewrite a shorter description",
                file=sys.stderr,
            )
            has_warnings = True
    return has_warnings


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with scan (default) and set-description subcommands."""
    parser = argparse.ArgumentParser(
        prog="mdscan",
        description="Scan .md files and display YAML frontmatter descriptions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="subcommand")

    # --- set-description subcommand ---
    sp_set = subparsers.add_parser(
        "set-description",
        help="Write or update the frontmatter description of a file.",
    )
    sp_set.add_argument("file", help="Markdown file to update.")
    sp_set.add_argument("description", help="Description text to write.")

    # --- scan (default) ---
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory).",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON array.")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Limit directory recursion depth.",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )

    return parser
