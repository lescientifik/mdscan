"""Tests for directory scanning behavior."""

from pathlib import Path

from mdscan.scanner import scan


class TestScan:
    def test_finds_nested_files(self, md_tree: Path) -> None:
        results = scan(md_tree)
        paths = [f.path for f in results]
        assert "sub/nested.md" in paths

    def test_max_depth_limits_recursion(self, md_tree: Path) -> None:
        results = scan(md_tree, max_depth=0)
        paths = [f.path for f in results]
        assert "valid.md" in paths
        assert "sub/nested.md" not in paths

    def test_hardcoded_dirs_excluded(self, md_tree: Path) -> None:
        results = scan(md_tree)
        paths = [f.path for f in results]
        assert not any("node_modules" in p for p in paths)
        assert not any(".git" in p for p in paths)

    def test_custom_ignore_pattern(self, md_tree: Path) -> None:
        results = scan(md_tree, ignore_patterns=["no_*"])
        paths = [f.path for f in results]
        assert "no_fm.md" not in paths
        assert "no_desc.md" not in paths
        assert "valid.md" in paths
