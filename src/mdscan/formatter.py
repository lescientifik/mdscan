"""Format scan results for stdout output."""

import json

from mdscan._types import MdFile


def format_text(files: list[MdFile]) -> str:
    """Format files with valid descriptions as aligned columns.

    Files without a description are excluded from the output.
    """
    valid = [(f.path, f.description) for f in files if f.description is not None]
    if not valid:
        return ""
    width = max(len(p) for p, _ in valid)
    lines = [f"{p:<{width}}  {d}" for p, d in valid]
    return "\n".join(lines)


def format_json(files: list[MdFile]) -> str:
    """Format all files as a JSON array, including those with ``description: null``."""
    data = [{"path": f.path, "description": f.description} for f in files]
    return json.dumps(data, indent=2, ensure_ascii=False)
