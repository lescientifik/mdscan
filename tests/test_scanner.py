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
        assert not any(".claude" in p for p in paths)

    def test_custom_ignore_pattern(self, md_tree: Path) -> None:
        results = scan(md_tree, ignore_patterns=["no_*"])
        paths = [f.path for f in results]
        assert "no_fm.md" not in paths
        assert "no_desc.md" not in paths
        assert "valid.md" in paths

    def test_claude_md_excluded_from_scan(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "---\ndescription: Instructions.\n---\n# Claude\n", encoding="utf-8"
        )
        (tmp_path / "README.md").write_text(
            "---\ndescription: Readme.\n---\n# Readme\n", encoding="utf-8"
        )
        results = scan(tmp_path)
        paths = [f.path for f in results]
        assert "CLAUDE.md" not in paths
        assert "README.md" in paths

    def test_claude_dir_excluded_by_default(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.md").write_text(
            "---\ndescription: Settings.\n---\n# Settings\n", encoding="utf-8"
        )
        (tmp_path / "readme.md").write_text(
            "---\ndescription: Readme.\n---\n# Readme\n", encoding="utf-8"
        )
        results = scan(tmp_path)
        paths = [f.path for f in results]
        assert ".claude/settings.md" not in paths
        assert "readme.md" in paths

    def test_ignore_pattern_matches_relative_path(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text(
            "---\ndescription: Nested.\n---\n# Nested\n", encoding="utf-8"
        )
        (tmp_path / "top.md").write_text(
            "---\ndescription: Top.\n---\n# Top\n", encoding="utf-8"
        )
        results = scan(tmp_path, ignore_patterns=["sub/*"])
        paths = [f.path for f in results]
        assert "sub/nested.md" not in paths
        assert "top.md" in paths

    def test_ignore_trailing_slash_excludes_directory(self, tmp_path: Path) -> None:
        """A pattern like 'target/' should exclude the directory and its contents."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "deep.md").write_text(
            "---\ndescription: Deep.\n---\n# Deep\n", encoding="utf-8"
        )
        (tmp_path / "top.md").write_text(
            "---\ndescription: Top.\n---\n# Top\n", encoding="utf-8"
        )
        results = scan(tmp_path, ignore_patterns=["target/"])
        paths = [f.path for f in results]
        assert "target/deep.md" not in paths
        assert "top.md" in paths

    def test_scan_populates_links(self, tmp_path: Path) -> None:
        (tmp_path / "index.md").write_text(
            "---\ndescription: Index.\n---\nSee [guide](guide.md) and [faq](faq.md).\n",
            encoding="utf-8",
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide.\n---\n# Guide\n", encoding="utf-8"
        )
        results = scan(tmp_path)
        index = next(f for f in results if f.path == "index.md")
        assert index.links == ["guide.md", "faq.md"]
        guide = next(f for f in results if f.path == "guide.md")
        assert guide.links == []
