"""Build and format a document tree from an entrypoint."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from mdscan._types import MdFile


@dataclass
class TreeNode:
    """A node in the document link tree."""

    path: str
    children: list[TreeNode] = field(default_factory=list)
    is_cycle: bool = False


def build_tree(
    entrypoint: str,
    file_by_path: dict[str, MdFile],
) -> TreeNode:
    """DFS from *entrypoint*, returning a :class:`TreeNode` tree structure.

    Already-visited nodes are represented with ``is_cycle=True`` and no children.
    """
    visited: set[str] = set()
    return _dfs(entrypoint, file_by_path, visited)


def _dfs(
    path: str,
    file_by_path: dict[str, MdFile],
    visited: set[str],
) -> TreeNode:
    """Recursive DFS helper."""
    if path in visited:
        return TreeNode(path=path, is_cycle=True)
    visited.add(path)

    md_file = file_by_path.get(path)
    if md_file is None:
        return TreeNode(path=path)

    children: list[TreeNode] = []
    current_dir = str(PurePosixPath(path).parent)
    for raw_link in md_file.links:
        if current_dir == ".":
            resolved = posixpath.normpath(raw_link)
        else:
            resolved = posixpath.normpath(posixpath.join(current_dir, raw_link))
        if resolved in file_by_path:
            children.append(_dfs(resolved, file_by_path, visited))

    return TreeNode(path=path, children=children)


def format_tree(node: TreeNode, orphans: list[str] | None = None) -> str:
    """Render a :class:`TreeNode` as a box-drawing characters string."""
    lines: list[str] = []
    _render(node, lines, prefix="", is_last=True, is_root=True)
    if orphans:
        lines.append("")
        lines.append("orphans:")
        for path in orphans:
            lines.append(f"  {path}")
    return "\n".join(lines)


def _render(
    node: TreeNode,
    lines: list[str],
    prefix: str,
    is_last: bool,
    is_root: bool,
) -> None:
    """Recursively render tree nodes with box-drawing characters."""
    if is_root:
        label = node.path
    else:
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        label = connector + node.path

    if node.is_cycle:
        label += " (*)"

    lines.append(prefix + label)

    child_prefix = "" if is_root else prefix + ("    " if is_last else "\u2502   ")

    for i, child in enumerate(node.children):
        _render(child, lines, child_prefix, is_last=(i == len(node.children) - 1), is_root=False)


def tree_to_dict(node: TreeNode) -> dict:
    """Convert a :class:`TreeNode` to a nested dict for JSON output."""
    result: dict = {"path": node.path}
    if node.is_cycle:
        result["cycle"] = True
    if node.children:
        result["children"] = [tree_to_dict(c) for c in node.children]
    return result
