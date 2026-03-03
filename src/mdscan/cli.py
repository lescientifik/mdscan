"""Command-line interface for mdscan."""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import posixpath
import sys
from collections import deque
from pathlib import Path, PurePosixPath

from mdscan import __version__
from mdscan._types import EXIT_OK, EXIT_STRUCTURE, EXIT_USAGE, EXIT_WARN, MdFile
from mdscan.config import has_config, load_config
from mdscan.formatter import format_json, format_plain, format_text
from mdscan.frontmatter import MAX_DESCRIPTION_WORDS, is_too_long, write_description
from mdscan.links import extract_all_links
from mdscan.scanner import scan
from mdscan.tree import TreeNode, build_tree, format_tree, tree_to_dict


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``mdscan`` CLI."""
    try:
        _main_inner(argv)
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # Silently handle broken pipe (e.g. piping to `head`).
        with contextlib.suppress(BrokenPipeError):
            sys.stdout.close()
        with contextlib.suppress(BrokenPipeError):
            sys.stderr.close()
        sys.exit(EXIT_OK)


def _add_common_flags(sub: argparse.ArgumentParser) -> None:
    """Add flags shared by all subcommands."""
    sub.add_argument("-q", "--quiet", action="store_true", help="Suppress non-data output.")
    sub.add_argument("-v", "--verbose", action="store_true", help="Show extra diagnostic info.")
    sub.add_argument("--no-color", action="store_true", help="Disable colored output.")


def _main_inner(argv: list[str] | None = None) -> None:
    """Inner main logic, separated for signal handling."""
    parser = argparse.ArgumentParser(
        prog="mdscan",
        description="Scan .md files and display YAML frontmatter descriptions.",
        epilog="https://github.com/lescientifik/mdscan",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # -- scan (default) -----------------------------------------------------
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan .md files and display descriptions (default).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n  mdscan scan docs/\n  mdscan scan --json --max-depth 2 .",
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
    scan_parser.add_argument(
        "--plain",
        action="store_true",
        help="Tab-separated output (path\\tdescription).",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of results shown.",
    )
    _add_common_flags(scan_parser)

    # -- check-links --------------------------------------------------------
    cl_parser = subparsers.add_parser(
        "check-links",
        help="Check reachability of .md files from an entrypoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  mdscan check-links docs/\n"
            "  mdscan check-links --entrypoint README.md --all-links ."
        ),
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
        "--all-links",
        action="store_true",
        help="Also check non-.md links (images, code files, etc.).",
    )
    cl_parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )
    _add_common_flags(cl_parser)

    # -- tree ---------------------------------------------------------------
    tree_parser = subparsers.add_parser(
        "tree",
        help="Display the document link tree from an entrypoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n  mdscan tree docs/\n  mdscan tree --json .",
    )
    tree_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory).",
    )
    tree_parser.add_argument(
        "--entrypoint",
        default=None,
        help="Entrypoint file (relative to directory). Default: CLAUDE.md or README.md.",
    )
    tree_parser.add_argument("--json", action="store_true", help="Output as JSON object.")
    tree_parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )
    _add_common_flags(tree_parser)

    # -- coverage -----------------------------------------------------------
    cov_parser = subparsers.add_parser(
        "coverage",
        help="Show documentation coverage statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n  mdscan coverage docs/\n  mdscan coverage --json .",
    )
    cov_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory).",
    )
    cov_parser.add_argument(
        "--entrypoint",
        default=None,
        help="Entrypoint file (relative to directory). Default: CLAUDE.md or README.md.",
    )
    cov_parser.add_argument("--json", action="store_true", help="Output as JSON object.")
    cov_parser.add_argument(
        "--ignore",
        action="append",
        help="Additional glob patterns to exclude (repeatable).",
    )
    _add_common_flags(cov_parser)

    # -- set-description ----------------------------------------------------
    sd_parser = subparsers.add_parser(
        "set-description",
        help="Write or update the frontmatter description of a file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n  mdscan set-description docs/guide.md "Step-by-step setup guide."',
    )
    sd_parser.add_argument("file", help="Markdown file to update.")
    sd_parser.add_argument("description", help="Description text to write.")
    _add_common_flags(sd_parser)

    # -- help ---------------------------------------------------------------
    help_parser = subparsers.add_parser("help", help="Show help for a command.")
    help_parser.add_argument(
        "target", nargs="?", default=None, help="Command to show help for."
    )

    # -- parse --------------------------------------------------------------
    # Default to "scan" when no subcommand is given, so that bare
    # `mdscan docs/` and `mdscan --json docs/` keep working.
    # Let --help and --version through to the top-level parser.
    raw = argv if argv is not None else sys.argv[1:]
    known_commands = {
        "scan", "check-links", "tree", "coverage", "set-description", "help",
    }
    top_level_flags = {"-h", "--help", "--version"}

    if raw and raw[0] not in known_commands and raw[0] not in top_level_flags:
        # Detect typo before falling through to scan.
        arg = raw[0]
        looks_like_command = arg[0:1].isalpha() and "/" not in arg and "." not in arg
        if looks_like_command:
            matches = difflib.get_close_matches(arg, known_commands, n=1, cutoff=0.6)
            if matches:
                print(f"error: unknown command '{arg}'", file=sys.stderr)
                print(f"Did you mean: {matches[0]}", file=sys.stderr)
                sys.exit(EXIT_USAGE)

    if not raw or (raw[0] not in known_commands and raw[0] not in top_level_flags):
        raw = ["scan", *raw]

    args = parser.parse_args(raw)

    # Apply environment variable defaults (CLI flags override).
    if hasattr(args, "quiet") and not args.quiet:
        args.quiet = os.environ.get("MDSCAN_QUIET") == "1"
    if hasattr(args, "verbose") and args.verbose:
        # -v explicitly set: override quiet even if MDSCAN_QUIET=1
        args.quiet = False
    if hasattr(args, "verbose") and not args.verbose:
        args.verbose = os.environ.get("MDSCAN_VERBOSE") == "1"

    sub_parsers_map = {
        "scan": scan_parser,
        "check-links": cl_parser,
        "tree": tree_parser,
        "coverage": cov_parser,
        "set-description": sd_parser,
    }

    if args.command == "help":
        if args.target and args.target in sub_parsers_map:
            sub_parsers_map[args.target].print_help()
        else:
            parser.print_help()
        sys.exit(EXIT_OK)
    elif args.command == "scan":
        _run_scan(args)
    elif args.command == "check-links":
        _run_check_links(args)
    elif args.command == "tree":
        _run_tree(args)
    elif args.command == "coverage":
        _run_coverage(args)
    elif args.command == "set-description":
        _run_set_description(args)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _run_scan(args: argparse.Namespace) -> None:
    """Execute the default scan subcommand."""
    directory = Path(args.directory)
    quiet = args.quiet
    verbose = args.verbose

    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    cfg = load_config(directory)
    ignore = (args.ignore or []) + cfg.ignore
    max_depth = args.max_depth if args.max_depth is not None else cfg.max_depth

    if verbose:
        _print_verbose_config(cfg, directory)

    files = scan(
        directory,
        max_depth=max_depth,
        ignore_patterns=ignore,
    )

    if verbose:
        _print_verbose_scan_stats(files, directory)

    has_warnings = _print_diagnostics(files, directory, quiet=quiet)

    # Apply --limit (after sorting, which scan() already does).
    limit = args.limit
    if limit is not None and limit > 0:
        files = files[:limit]

    if args.json:
        print(format_json(files))
    elif not quiet:
        output = format_plain(files) if args.plain else format_text(files)
        if output:
            print(output)

    if not quiet and not args.json:
        print(
            "hint: run 'mdscan check-links' to verify link reachability",
            file=sys.stderr,
        )

    sys.exit(EXIT_WARN if has_warnings else EXIT_OK)


def _run_set_description(args: argparse.Namespace) -> None:
    """Execute the ``set-description`` subcommand."""
    path = Path(args.file)

    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    description: str = args.description
    if description == "-":
        description = sys.stdin.read().strip()
        if not description:
            print("error: empty input from stdin", file=sys.stderr)
            sys.exit(EXIT_USAGE)
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
        sys.exit(EXIT_WARN)

    print(f"wrote: {path}")
    sys.exit(EXIT_OK)


def _run_check_links(args: argparse.Namespace) -> None:
    """Execute the ``check-links`` subcommand."""
    quiet = args.quiet
    files, entrypoint, file_by_path = _resolve_and_scan(args)
    scanned_paths = {f.path for f in files}
    directory = Path(args.directory)

    reachable, broken_links = _compute_reachability(entrypoint, file_by_path, scanned_paths)
    unreachable = sorted(scanned_paths - reachable)
    has_issues = bool(unreachable) or bool(broken_links)

    # Check non-md asset links when --all-links is set.
    broken_asset_links: list[tuple[str, str]] = []
    if args.all_links:
        broken_asset_links = _check_asset_links(files, directory, scanned_paths)
        if broken_asset_links:
            has_issues = True

    # Diagnostics to stderr.
    if not quiet:
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

        if broken_asset_links:
            n = len(broken_asset_links)
            label = "broken asset link" if n == 1 else "broken asset links"
            print(
                f"warn: {n} {label} (target file not found):",
                file=sys.stderr,
            )
            for source, target in broken_asset_links:
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
        data: dict = {
            "entrypoint": entrypoint,
            "reachable": sorted(reachable),
            "unreachable": unreachable,
            "broken_links": [
                {"source": src, "target": tgt} for src, tgt in broken_links
            ],
        }
        if args.all_links:
            data["broken_asset_links"] = [
                {"source": src, "target": tgt} for src, tgt in broken_asset_links
            ]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif not quiet:
        print(f"{reachable_count}/{total} files reachable from {entrypoint}")

    sys.exit(EXIT_STRUCTURE if has_issues else EXIT_OK)


def _run_tree(args: argparse.Namespace) -> None:
    """Execute the ``tree`` subcommand."""
    files, entrypoint, file_by_path = _resolve_and_scan(args)
    scanned_paths = {f.path for f in files}

    tree = build_tree(entrypoint, file_by_path)

    # Collect orphans: files not visited during DFS.
    visited: set[str] = set()
    _collect_visited(tree, visited)
    orphans = sorted(scanned_paths - visited)

    if args.json:
        data: dict = tree_to_dict(tree)
        if orphans:
            data["orphans"] = orphans
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_tree(tree, orphans=orphans or None))

    sys.exit(EXIT_OK)


def _run_coverage(args: argparse.Namespace) -> None:
    """Execute the ``coverage`` subcommand."""
    files, entrypoint, file_by_path = _resolve_and_scan(args)
    scanned_paths = {f.path for f in files}

    total = len(files)
    described = [f for f in files if f.description is not None]
    described_count = len(described)

    reachable, broken_links = _compute_reachability(entrypoint, file_by_path, scanned_paths)
    reachable_count = len(reachable)
    broken_count = len(broken_links)

    # Word count stats (only files with descriptions).
    word_counts = [f.word_count for f in files if f.word_count is not None]
    avg_words = round(sum(word_counts) / len(word_counts)) if word_counts else 0
    longest = max(files, key=lambda f: f.word_count or 0) if files else None

    has_structural = reachable_count < total or broken_count > 0
    has_soft = described_count < total

    if args.json:
        data = {
            "files": total,
            "described": described_count,
            "described_pct": round(described_count / total * 100) if total else 100,
            "reachable": reachable_count,
            "reachable_pct": round(reachable_count / total * 100) if total else 100,
            "broken_links": broken_count,
            "avg_words": avg_words,
            "longest": longest.path if longest and longest.word_count else None,
            "longest_words": longest.word_count if longest and longest.word_count else None,
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        desc_pct = round(described_count / total * 100) if total else 100
        reach_pct = round(reachable_count / total * 100) if total else 100
        print(f"files:         {total}")
        print(f"described:     {described_count} ({desc_pct}%)")
        print(f"reachable:     {reachable_count}/{total} ({reach_pct}%)")
        print(f"broken links:  {broken_count}")
        print(f"avg words:     {avg_words}")
        if longest and longest.word_count:
            print(f"longest:       {longest.path} ({longest.word_count} words)")

    if has_structural:
        sys.exit(EXIT_STRUCTURE)
    elif has_soft:
        sys.exit(EXIT_WARN)
    else:
        sys.exit(EXIT_OK)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_and_scan(
    args: argparse.Namespace,
) -> tuple[list[MdFile], str, dict[str, MdFile]]:
    """Scan directory, resolve entrypoint, build lookup.

    Shared by ``check-links``, ``tree``, and ``coverage``.
    """
    directory = Path(args.directory)

    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    cfg = load_config(directory)
    ignore = (args.ignore or []) + cfg.ignore
    entrypoint: str | None = args.entrypoint or cfg.entrypoint

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
            sys.exit(EXIT_USAGE)

    files = scan(directory, include_excluded_files=True, ignore_patterns=ignore)
    scanned_paths = {f.path for f in files}

    if entrypoint not in scanned_paths:
        print(f"error: entrypoint not found: {entrypoint}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    file_by_path = {f.path: f for f in files}
    return files, entrypoint, file_by_path


def _compute_reachability(
    entrypoint: str,
    file_by_path: dict[str, MdFile],
    scanned_paths: set[str],
) -> tuple[set[str], list[tuple[str, str]]]:
    """BFS from *entrypoint*. Return ``(reachable, broken_links)``."""
    reachable: set[str] = set()
    broken_links: list[tuple[str, str]] = []
    queue: deque[str] = deque([entrypoint])
    reachable.add(entrypoint)

    while queue:
        current = queue.popleft()
        current_file = file_by_path[current]
        current_dir = str(PurePosixPath(current).parent)

        for raw_link in current_file.links:
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

    return reachable, broken_links


def _check_asset_links(
    files: list[MdFile],
    directory: Path,
    scanned_md_paths: set[str],
) -> list[tuple[str, str]]:
    """Check non-.md links for existence on disk. Return broken ``(source, target)`` pairs."""
    broken: list[tuple[str, str]] = []
    for f in files:
        text = (directory / f.path).read_text(encoding="utf-8")
        all_links = extract_all_links(text)
        current_dir = str(PurePosixPath(f.path).parent)
        for raw_link in all_links:
            # Skip .md links — those are handled by the BFS reachability check.
            if raw_link.endswith(".md"):
                continue
            if current_dir == ".":
                resolved = posixpath.normpath(raw_link)
            else:
                resolved = posixpath.normpath(posixpath.join(current_dir, raw_link))
            if not (directory / resolved).is_file():
                broken.append((f.path, raw_link))
    return broken


def _collect_visited(node: TreeNode, visited: set[str]) -> None:
    """Collect all paths visited in a tree (excluding cycle-only refs)."""
    if node.is_cycle:
        return
    visited.add(node.path)
    for child in node.children:
        _collect_visited(child, visited)


# ---------------------------------------------------------------------------
# Verbose output
# ---------------------------------------------------------------------------


def _print_verbose_config(cfg: object, directory: Path) -> None:
    """Print config source info to stderr."""
    config_path = directory / "pyproject.toml"
    if config_path.is_file() and has_config(directory):
        print(f"config: {config_path}", file=sys.stderr)
    else:
        print("config: none", file=sys.stderr)


def _print_verbose_scan_stats(files: list[MdFile], directory: Path) -> None:
    """Print scan statistics to stderr."""
    dirs = {str(Path(f.path).parent) for f in files}
    print(f"scanned: {len(files)} files in {len(dirs)} directories", file=sys.stderr)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _print_diagnostics(
    files: list[MdFile],
    directory: Path | None = None,
    *,
    quiet: bool = False,
) -> bool:
    """Print warnings and hints to stderr. Return ``True`` if any issues exist."""
    missing = [f for f in files if f.description is None]
    too_long = [
        f for f in files
        if f.word_count is not None and f.word_count > MAX_DESCRIPTION_WORDS
    ]

    has_warnings = bool(missing) or bool(too_long)
    if quiet:
        return has_warnings

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

    has_warnings = bool(missing) or bool(too_long)
    if has_warnings and directory is not None and not has_config(directory):
        print(
            "hint: to persist settings, add a [tool.mdscan] section"
            " in pyproject.toml (see mdscan --help)",
            file=sys.stderr,
        )

    return has_warnings
