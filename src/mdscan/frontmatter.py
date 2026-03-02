"""Read, write, and validate YAML frontmatter in markdown files."""

from pathlib import Path

import yaml

MAX_DESCRIPTION_WORDS = 150


def extract_description(text: str) -> str | None:
    """Extract the ``description`` field from YAML frontmatter.

    Returns the description string, or ``None`` if frontmatter is absent
    or has no ``description`` key.
    """
    fm = _parse_frontmatter(text)
    if fm is None:
        return None
    desc = fm.get("description")
    return str(desc) if desc is not None else None


def write_description(path: Path, description: str) -> None:
    """Write or update the ``description`` field in *path*'s frontmatter.

    - No frontmatter → creates ``---\\ndescription: ...\\n---\\n`` at the top.
    - Frontmatter without ``description`` → adds the field.
    - Frontmatter with ``description`` → replaces it.
    """
    text = path.read_text(encoding="utf-8")
    fm_block = _parse_frontmatter(text)

    if fm_block is None:
        # No frontmatter at all — prepend a new block.
        header = yaml.dump({"description": description}, default_flow_style=False).rstrip("\n")
        path.write_text(f"---\n{header}\n---\n{text}", encoding="utf-8")
        return

    # Frontmatter exists — update or add the description field.
    fm_block["description"] = description
    new_header = yaml.dump(fm_block, default_flow_style=False, sort_keys=False).rstrip("\n")

    # Replace old frontmatter block.
    body = _strip_frontmatter(text)
    path.write_text(f"---\n{new_header}\n---\n{body}", encoding="utf-8")


def is_too_long(description: str) -> bool:
    """Return ``True`` if *description* exceeds the word-count limit."""
    return len(description.split()) > MAX_DESCRIPTION_WORDS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict | None:  # type: ignore[type-arg]
    """Return the frontmatter as a dict, or ``None`` if absent."""
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    raw = text[3:end].strip()
    if not raw:
        return None
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else None


def _strip_frontmatter(text: str) -> str:
    """Return *text* with the frontmatter block removed."""
    end = text.find("---", 3)
    if end == -1:
        return text
    # Skip past the closing "---" and the newline that follows it.
    rest = text[end + 3 :]
    return rest.lstrip("\n")
