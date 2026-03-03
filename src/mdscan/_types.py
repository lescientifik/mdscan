"""Shared data types for mdscan."""

from dataclasses import dataclass, field

# Exit codes following UNIX conventions.
EXIT_OK = 0  # Success, no issues
EXIT_WARN = 1  # Soft warnings (missing descriptions, too-long descriptions)
EXIT_USAGE = 2  # Usage error (bad args, missing directory, missing entrypoint)
EXIT_STRUCTURE = 3  # Structural issues (broken links, unreachable files)


@dataclass
class MdFile:
    """Result of scanning a single markdown file."""

    path: str
    description: str | None
    word_count: int | None
    links: list[str] = field(default_factory=list)
