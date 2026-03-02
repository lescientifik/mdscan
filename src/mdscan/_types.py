"""Shared data types for mdscan."""

from dataclasses import dataclass, field


@dataclass
class MdFile:
    """Result of scanning a single markdown file."""

    path: str
    description: str | None
    word_count: int | None
    links: list[str] = field(default_factory=list)
