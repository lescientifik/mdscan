"""Extract markdown links pointing to other .md files."""

import re

_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+\.md)\)")


def extract_md_links(text: str) -> list[str]:
    """Return relative ``.md`` paths referenced in markdown links.

    Filters out absolute paths and URLs (``http://``, ``https://``).
    """
    links: list[str] = []
    for match in _MD_LINK.finditer(text):
        target = match.group(2)
        if target.startswith(("http://", "https://", "/")):
            continue
        links.append(target)
    return links
