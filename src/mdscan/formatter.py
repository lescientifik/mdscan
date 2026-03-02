"""Format scan results for stdout output."""

import json

from mdscan._types import MdFile
from mdscan.frontmatter import MAX_DESCRIPTION_WORDS


def _truncate(description: str) -> str:
    """Truncate a description to the word limit, appending '...' if needed."""
    words = description.split()
    if len(words) <= MAX_DESCRIPTION_WORDS:
        return description
    return " ".join(words[:MAX_DESCRIPTION_WORDS]) + " ..."


def format_text(files: list[MdFile]) -> str:
    """Format files with valid descriptions as aligned columns.

    Files without a description are excluded from the output.
    Descriptions exceeding the word limit are truncated.
    """
    valid = [(f.path, _truncate(f.description)) for f in files if f.description is not None]
    if not valid:
        return ""
    width = max(len(p) for p, _ in valid)
    lines = [f"{p:<{width}}  {d}" for p, d in valid]
    return "\n".join(lines)


def format_json(files: list[MdFile]) -> str:
    """Format all files as a JSON array, including those with ``description: null``.

    Descriptions exceeding the word limit are truncated.
    """
    data = [
        {"path": f.path, "description": _truncate(f.description) if f.description else None}
        for f in files
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)
