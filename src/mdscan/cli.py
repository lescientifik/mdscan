"""Command-line interface for mdscan."""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
from collections import deque
from pathlib import Path, PurePosixPath

from mdscan import __version__
from mdscan._types import MdFile
from mdscan.formatter import format_json, format_text
from mdscan.frontmatter import MAX_DESCRIPTION_WORDS, is_too_long, write_description
from mdscan.scanner import scan


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``mdscan`` CLI."""
    parser = argparse.ArgumentParser(
        prog="mdscan",
        description="Scan .md files and display YAML frontmatter descriptions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # -- scan (default) -----------------------------------------------------
    scan_parser = subparsers.add_parser(
        "scan", help="Scan .md files and display descriptions (default)."
    )
    scan_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory).",
    )
    scan_parser.add_argument("--json", action="store_true", help="Output as JSON array.")
    scan_parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Limit directory recursion depth.",
    )
    scan_parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )

    # -- check-links --------------------------------------------------------
    cl_parser = subparsers.add_parser(
        "check-links", help="Check reachability of .md files from an entrypoint."
    )
    cl_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory).",
    )
    cl_parser.add_argument(
        "--entrypoint",
        default=None,
        help="Entrypoint file (relative to directory). Default: CLAUDE.md or README.md.",
    )
    cl_parser.add_argument("--json", action="store_true", help="Output as JSON object.")
    cl_parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )

    # -- set-description ----------------------------------------------------
    sd_parser = subparsers.add_parser(
        "set-description", help="Write or update the frontmatter description of a file."
    )
    sd_parser.add_argument("file", help="Markdown file to update.")
    sd_parser.add_argument("description", help="Description text to write.")

    # -- parse --------------------------------------------------------------
    # Default to "scan" when no subcommand is given, so that bare
    # `mdscan docs/` and `mdscan --json docs/` keep working.
    # Let --help and --version through to the top-level parser.
    raw = argv if argv is not None else sys.argv[1:]
    known_commands = {"scan", "check-links", "set-description"}
    top_level_flags = {"-h", "--help", "--version"}
    if not raw or (raw[0] not in known_commands and raw[0] not in top_level_flags):
        raw = ["scan", *raw]

    args = parser.parse_args(raw)

    if args.command == "scan":
        _run_scan(args)
    elif args.command == "check-links":
        _run_check_links(args)
    elif args.command == "set-description":
        _run_set_description(args)


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

    output = format_json(files) if args.json else format_text(files)

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
        print(
            f"  fix: have ONE agent (e.g. fast model like Haiku) read {path} and run"
            f" `mdscan set-description {path} \"...\"`"
            f" with a shorter description",
            file=sys.stderr,
        )
        print(f"wrote: {path}")
        sys.exit(1)

    print(f"wrote: {path}")
    sys.exit(0)


def _run_check_links(args: argparse.Namespace) -> None:
    """Execute the ``check-links`` subcommand."""
    directory = Path(args.directory)

    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        sys.exit(2)

    # Resolve entrypoint.
    entrypoint: str | None = args.entrypoint
    if entrypoint is None:
        if (directory / "CLAUDE.md").is_file():
            entrypoint = "CLAUDE.md"
        elif (directory / "README.md").is_file():
            entrypoint = "README.md"
        else:
            print(
                "error: no entrypoint found (no CLAUDE.md or README.md in directory)",
                file=sys.stderr,
            )
            sys.exit(2)

    # Scan all .md files (check-links includes CLAUDE.md).
    files = scan(directory, include_excluded_files=True,
                 ignore_patterns=args.ignore or [])

    # Build lookup of all scanned paths.
    scanned_paths: set[str] = {f.path for f in files}

    if entrypoint not in scanned_paths:
        print(f"error: entrypoint not found: {entrypoint}", file=sys.stderr)
        sys.exit(2)

    # Build adjacency: path -> resolved link targets.
    file_by_path: dict[str, MdFile] = {f.path: f for f in files}

    # BFS from entrypoint.
    reachable: set[str] = set()
    broken_links: list[tuple[str, str]] = []
    queue: deque[str] = deque([entrypoint])
    reachable.add(entrypoint)

    while queue:
        current = queue.popleft()
        current_file = file_by_path[current]
        current_dir = str(PurePosixPath(current).parent)

        for raw_link in current_file.links:
            # Resolve link relative to the file's directory.
            if current_dir == ".":
                resolved = posixpath.normpath(raw_link)
            else:
                resolved = posixpath.normpath(posixpath.join(current_dir, raw_link))

            if resolved not in scanned_paths:
                broken_links.append((current, raw_link))
                continue
            if resolved not in reachable:
                reachable.add(resolved)
                queue.append(resolved)

    unreachable = sorted(scanned_paths - reachable)
    has_issues = bool(unreachable) or bool(broken_links)

    # Diagnostics to stderr.
    print(f"entrypoint: {entrypoint}", file=sys.stderr)

    if unreachable:
        n = len(unreachable)
        label = "file" if n == 1 else "files"
        print(
            f"warn: {n} {label} unreachable from {entrypoint}"
            f" (no link chain connects them):",
            file=sys.stderr,
        )
        for path in unreachable:
            print(f"  - {path}", file=sys.stderr)
        print(
            "  fix: for EACH file, have a dedicated agent (e.g. smart model like"
            " Opus) review the file and either link it from a reachable doc, or"
            " confirm with the user that it can be removed",
            file=sys.stderr,
        )

    if broken_links:
        n = len(broken_links)
        label = "broken link" if n == 1 else "broken links"
        print(
            f"warn: {n} {label} (target file not found):",
            file=sys.stderr,
        )
        for source, target in broken_links:
            print(f"  - {source} → {target}", file=sys.stderr)
        print(
            "  fix: for EACH source file, have a dedicated agent (e.g. fast model"
            " like Haiku) fix or remove its broken links",
            file=sys.stderr,
        )

    # stdout summary.
    total = len(scanned_paths)
    reachable_count = len(reachable)

    if args.json:
        data = {
            "entrypoint": entrypoint,
            "reachable": sorted(reachable),
            "unreachable": unreachable,
            "broken_links": [
                {"source": src, "target": tgt} for src, tgt in broken_links
            ],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"{reachable_count}/{total} files reachable from {entrypoint}")

    sys.exit(1 if has_issues else 0)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _print_diagnostics(files: list[MdFile]) -> bool:
    """Print warnings and hints to stderr. Return ``True`` if any were emitted."""
    missing = [f for f in files if f.description is None]
    too_long = [
        f for f in files
        if f.word_count is not None and f.word_count > MAX_DESCRIPTION_WORDS
    ]

    if missing:
        n = len(missing)
        label = "file" if n == 1 else "files"
        print(
            f"warn: {n} {label} missing YAML frontmatter description:",
            file=sys.stderr,
        )
        for f in missing:
            print(f"  - {f.path}", file=sys.stderr)
        print(
            "  fix: for EACH file, have a dedicated agent (e.g. fast model like"
            " Haiku) read the file and run"
            ' `mdscan set-description <file> "..."`',
            file=sys.stderr,
        )

    if too_long:
        n = len(too_long)
        label = "file" if n == 1 else "files"
        print(
            f"hint: {n} {label} with description too long"
            f" (max {MAX_DESCRIPTION_WORDS} words), truncated in output:",
            file=sys.stderr,
        )
        for f in too_long:
            print(f"  - {f.path} ({f.word_count} words)", file=sys.stderr)
        print(
            "  fix: for EACH file, have a dedicated agent (e.g. fast model like"
            " Haiku) read the file and run"
            ' `mdscan set-description <file> "..."` with a shorter description',
            file=sys.stderr,
        )

    return bool(missing) or bool(too_long)
