"""Minimal ANSI color support for stderr output."""

from __future__ import annotations

import os
import sys
from typing import IO


def use_color(stream: IO[str], *, no_color_flag: bool = False) -> bool:
    """Return ``True`` if color should be used on *stream*."""
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(stream, "isatty") and stream.isatty()


# ANSI escape codes.
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"
_CYAN = "\x1b[36m"
_DIM = "\x1b[2m"
_RESET = "\x1b[0m"

_PREFIX_COLORS: dict[str, str] = {
    "error:": _RED,
    "warn:": _YELLOW,
    "hint:": _CYAN,
    "fix:": _DIM,
}


def colorize_stderr(line: str, *, enabled: bool) -> str:
    """Apply ANSI color to known stderr prefixes if *enabled*."""
    if not enabled:
        return line
    stripped = line.lstrip()
    for prefix, code in _PREFIX_COLORS.items():
        if stripped.startswith(prefix):
            return line.replace(prefix, f"{code}{prefix}{_RESET}", 1)
    return line


def stderr_print(msg: str, *, color: bool) -> None:
    """Print *msg* to stderr, colorizing known prefixes."""
    print(colorize_stderr(msg, enabled=color), file=sys.stderr)
