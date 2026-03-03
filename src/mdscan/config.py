"""Load mdscan configuration from ``pyproject.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MdscanConfig:
    """Parsed ``[tool.mdscan]`` configuration."""

    ignore: list[str] = field(default_factory=list)
    max_depth: int | None = None
    entrypoint: str | None = None


def load_config(start_dir: Path) -> MdscanConfig:
    """Walk up from *start_dir* to find ``pyproject.toml`` and parse ``[tool.mdscan]``.

    Returns a :class:`MdscanConfig` with defaults for any missing keys.
    If no ``pyproject.toml`` is found or it has no ``[tool.mdscan]`` section,
    returns a default config.
    """
    raw = _find_and_read(start_dir)
    if raw is None:
        return MdscanConfig()
    return MdscanConfig(
        ignore=raw.get("ignore", []),
        max_depth=raw.get("max-depth"),
        entrypoint=raw.get("entrypoint"),
    )


def has_config(start_dir: Path) -> bool:
    """Return ``True`` if a ``[tool.mdscan]`` section exists in a reachable ``pyproject.toml``."""
    return _find_and_read(start_dir) is not None


def _find_and_read(start_dir: Path) -> dict | None:
    """Locate ``pyproject.toml`` and return the ``[tool.mdscan]`` dict, or ``None``."""
    current = start_dir.resolve()
    while True:
        candidate = current / "pyproject.toml"
        if candidate.is_file():
            try:
                data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                return None
            return data.get("tool", {}).get("mdscan")
        parent = current.parent
        if parent == current:
            return None
        current = parent
