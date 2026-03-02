"""Walk directories and collect markdown file descriptions."""

from fnmatch import fnmatch
from pathlib import Path

from mdscan._types import MdFile
from mdscan.frontmatter import extract_description
from mdscan.links import extract_md_links

EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "site-packages",
})

EXCLUDED_FILES: frozenset[str] = frozenset({
    "CLAUDE.md",
})


def scan(
    directory: Path,
    *,
    max_depth: int | None = None,
    ignore_patterns: list[str] | None = None,
    include_excluded_files: bool = False,
) -> list[MdFile]:
    """Recursively scan *directory* for ``.md`` files and extract descriptions.

    Args:
        directory: Root directory to scan.
        max_depth: Maximum recursion depth (0 = root only). ``None`` = unlimited.
        ignore_patterns: Additional glob patterns to exclude.
        include_excluded_files: If ``True``, include files normally in
            :data:`EXCLUDED_FILES` (e.g. ``CLAUDE.md``).

    Returns:
        Sorted list of :class:`MdFile` results.
    """
    results: list[MdFile] = []
    _walk(directory, directory, results, max_depth, ignore_patterns or [],
          include_excluded_files)
    results.sort(key=lambda f: f.path)
    return results


def _walk(
    root: Path,
    current: Path,
    results: list[MdFile],
    max_depth: int | None,
    ignore_patterns: list[str],
    include_excluded_files: bool,
) -> None:
    """Recursively collect ``.md`` files starting from *current*."""
    depth = len(current.relative_to(root).parts)
    if max_depth is not None and depth > max_depth:
        return

    try:
        entries = sorted(current.iterdir())
    except PermissionError:
        return

    for entry in entries:
        if entry.is_dir():
            if entry.name in EXCLUDED_DIRS:
                continue
            if any(fnmatch(entry.name, pat) for pat in ignore_patterns):
                continue
            _walk(root, entry, results, max_depth, ignore_patterns,
                  include_excluded_files)
        elif entry.is_file() and entry.suffix == ".md":
            if not include_excluded_files and entry.name in EXCLUDED_FILES:
                continue
            if any(fnmatch(entry.name, pat) for pat in ignore_patterns):
                continue
            text = entry.read_text(encoding="utf-8")
            desc = extract_description(text)
            rel = str(entry.relative_to(root))
            word_count = len(desc.split()) if desc else None
            links = extract_md_links(text)
            results.append(
                MdFile(path=rel, description=desc, word_count=word_count, links=links)
            )
