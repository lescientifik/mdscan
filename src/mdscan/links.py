"""Extract markdown links pointing to other files."""

import re

_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+\.md)\)")
_ALL_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


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


def extract_all_links(text: str) -> list[str]:
    """Return all relative file paths referenced in markdown links.

    Unlike :func:`extract_md_links`, includes non-``.md`` targets
    (images, code files, etc.). Filters out ``http(s)://`` URLs and
    absolute paths.
    """
    links: list[str] = []
    for match in _ALL_LINK.finditer(text):
        target = match.group(2)
        if target.startswith(("http://", "https://", "/")):
            continue
        # Strip optional anchor fragments.
        target = target.split("#")[0]
        if target:
            links.append(target)
    return links
