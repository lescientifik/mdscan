"""Tests for mdscan tree subcommand and tree module."""

import json
import subprocess
import sys
from pathlib import Path

from mdscan._types import MdFile
from mdscan.tree import TreeNode, build_tree, format_tree, tree_to_dict


def run_mdscan(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mdscan", *args],
        capture_output=True,
        text=True,
    )


class TestBuildTree:
    def test_simple_hierarchy(self) -> None:
        files = {
            "README.md": MdFile("README.md", "Root", 1, links=["guide.md"]),
            "guide.md": MdFile("guide.md", "Guide", 1, links=["api.md"]),
            "api.md": MdFile("api.md", "API", 1, links=[]),
        }
        tree = build_tree("README.md", files)
        assert tree.path == "README.md"
        assert len(tree.children) == 1
        assert tree.children[0].path == "guide.md"
        assert tree.children[0].children[0].path == "api.md"

    def test_cycle_detection(self) -> None:
        files = {
            "a.md": MdFile("a.md", "A", 1, links=["b.md"]),
            "b.md": MdFile("b.md", "B", 1, links=["a.md"]),
        }
        tree = build_tree("a.md", files)
        assert tree.path == "a.md"
        assert tree.children[0].path == "b.md"
        # b.md links back to a.md -> cycle
        cycle_node = tree.children[0].children[0]
        assert cycle_node.path == "a.md"
        assert cycle_node.is_cycle is True
        assert cycle_node.children == []


class TestFormatTree:
    def test_renders_box_drawing(self) -> None:
        tree = TreeNode(
            "README.md",
            children=[
                TreeNode("guide.md", children=[TreeNode("api.md")]),
                TreeNode("faq.md"),
            ],
        )
        output = format_tree(tree)
        assert "README.md" in output
        assert "├── guide.md" in output
        assert "│   └── api.md" in output
        assert "└── faq.md" in output

    def test_cycle_suffix(self) -> None:
        tree = TreeNode(
            "a.md",
            children=[TreeNode("b.md", children=[TreeNode("a.md", is_cycle=True)])],
        )
        output = format_tree(tree)
        assert "a.md (*)" in output

    def test_orphan_section(self) -> None:
        tree = TreeNode("README.md")
        output = format_tree(tree, orphans=["orphan.md", "lost.md"])
        assert "orphans:" in output
        assert "  orphan.md" in output
        assert "  lost.md" in output


class TestTreeToDict:
    def test_nested_structure(self) -> None:
        tree = TreeNode(
            "a.md",
            children=[TreeNode("b.md", children=[TreeNode("a.md", is_cycle=True)])],
        )
        d = tree_to_dict(tree)
        assert d["path"] == "a.md"
        assert "cycle" not in d
        child = d["children"][0]
        assert child["path"] == "b.md"
        cycle = child["children"][0]
        assert cycle["cycle"] is True


class TestTreeCLI:
    def test_tree_simple(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan("tree", str(tmp_path))
        assert result.returncode == 0
        assert "README.md" in result.stdout
        assert "guide.md" in result.stdout

    def test_tree_orphan_listed(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("tree", str(tmp_path))
        assert "orphans:" in result.stdout
        assert "orphan.md" in result.stdout

    def test_tree_json(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan("tree", "--json", str(tmp_path))
        data = json.loads(result.stdout)
        assert data["path"] == "README.md"
        assert data["children"][0]["path"] == "guide.md"

    def test_tree_entrypoint_auto_detection(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "---\ndescription: Claude.\n---\nSee [readme](README.md).\n", encoding="utf-8"
        )
        (tmp_path / "README.md").write_text(
            "---\ndescription: Readme.\n---\n# Readme\n", encoding="utf-8"
        )
        result = run_mdscan("tree", str(tmp_path))
        assert result.returncode == 0
        # CLAUDE.md is root of tree
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "CLAUDE.md"

    def test_tree_respects_ignore(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "secret.md").write_text(
            "---\ndescription: Secret.\n---\n# Secret\n", encoding="utf-8"
        )
        result = run_mdscan("tree", "--ignore", "secret.md", str(tmp_path))
        assert "secret.md" not in result.stdout
