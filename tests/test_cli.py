"""End-to-end CLI integration tests."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_mdscan(*args: str) -> subprocess.CompletedProcess[str]:
    """Run mdscan as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "mdscan", *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def all_valid(tmp_path: Path) -> Path:
    """Directory where every .md file has a valid description."""
    (tmp_path / "a.md").write_text(
        "---\ndescription: First file.\n---\n# A\n", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text(
        "---\ndescription: Second file.\n---\n# B\n", encoding="utf-8"
    )
    return tmp_path


class TestScanExitCodes:
    def test_exit_0_all_valid(self, all_valid: Path) -> None:
        result = run_mdscan(str(all_valid))
        assert result.returncode == 0
        assert result.stderr == ""

    def test_exit_1_missing_frontmatter(self, tmp_path: Path) -> None:
        (tmp_path / "good.md").write_text(
            "---\ndescription: OK.\n---\n", encoding="utf-8"
        )
        (tmp_path / "bad.md").write_text("# No frontmatter\n", encoding="utf-8")

        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1
        assert "warn:" in result.stderr
        assert "missing YAML frontmatter description" in result.stderr
        assert "  - bad.md" in result.stderr
        assert "fix:" in result.stderr
        assert "mdscan set-description" in result.stderr

    def test_exit_1_description_too_long(self, tmp_path: Path) -> None:
        long_desc = " ".join(["word"] * 160)
        (tmp_path / "long.md").write_text(
            f"---\ndescription: {long_desc}\n---\n", encoding="utf-8"
        )

        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1
        # stderr diagnostics — grouped format
        assert "hint:" in result.stderr
        assert "description too long" in result.stderr
        assert "truncated" in result.stderr
        assert "  - long.md (160 words)" in result.stderr
        assert "fix:" in result.stderr
        assert "mdscan set-description" in result.stderr
        # stdout: description truncated to 150 words + "..."
        assert "long.md" in result.stdout
        stdout_words = result.stdout.split("long.md", 1)[1].split()
        assert stdout_words[-1] == "..."
        assert len(stdout_words) == 151  # 150 words + "..."


class TestScanOutput:
    def test_stdout_excludes_files_without_description(self, tmp_path: Path) -> None:
        (tmp_path / "has.md").write_text(
            "---\ndescription: Present.\n---\n", encoding="utf-8"
        )
        (tmp_path / "missing.md").write_text("# Nothing\n", encoding="utf-8")

        result = run_mdscan(str(tmp_path))
        assert "has.md" in result.stdout
        assert "missing.md" not in result.stdout

    def test_json_includes_all_files(self, tmp_path: Path) -> None:
        (tmp_path / "has.md").write_text(
            "---\ndescription: Present.\n---\n", encoding="utf-8"
        )
        (tmp_path / "missing.md").write_text("# Nothing\n", encoding="utf-8")

        result = run_mdscan("--json", str(tmp_path))
        data = json.loads(result.stdout)
        paths = [entry["path"] for entry in data]
        assert "has.md" in paths
        assert "missing.md" in paths

        missing = next(e for e in data if e["path"] == "missing.md")
        assert missing["description"] is None


class TestScanLinks:
    def test_scan_text_shows_links(self, tmp_path: Path) -> None:
        (tmp_path / "index.md").write_text(
            "---\ndescription: Index page.\n---\nSee [guide](guide.md) and [faq](faq.md).\n",
            encoding="utf-8",
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide page.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan(str(tmp_path))
        assert "→ links: guide.md, faq.md" in result.stdout
        # guide.md has no links, so no arrow line for it
        lines = result.stdout.strip().split("\n")
        guide_lines = [line for line in lines if "guide.md" in line and "→" not in line]
        assert len(guide_lines) == 1

    def test_scan_json_includes_links(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\nSee [b](b.md).\n", encoding="utf-8"
        )
        (tmp_path / "b.md").write_text(
            "---\ndescription: B.\n---\n# B\n", encoding="utf-8"
        )
        result = run_mdscan("--json", str(tmp_path))
        data = json.loads(result.stdout)
        a_entry = next(e for e in data if e["path"] == "a.md")
        assert a_entry["links"] == ["b.md"]
        b_entry = next(e for e in data if e["path"] == "b.md")
        assert b_entry["links"] == []


class TestCheckLinks:
    def test_check_links_all_reachable(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 0
        assert "2/2 files reachable from README.md" in result.stdout
        assert "warn:" not in result.stderr

    def test_check_links_unreachable_file(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 1
        assert "warn:" in result.stderr
        assert "unreachable from README.md" in result.stderr
        assert "  - orphan.md" in result.stderr
        assert "fix:" in result.stderr

    def test_check_links_broken_link(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [missing](ghost.md).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 1
        assert "broken link" in result.stderr
        assert "  - README.md → ghost.md" in result.stderr
        assert "fix:" in result.stderr

    def test_check_links_entrypoint_auto_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "---\ndescription: Instructions.\n---\nSee [readme](README.md).\n", encoding="utf-8"
        )
        (tmp_path / "README.md").write_text(
            "---\ndescription: Readme.\n---\n# Readme\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 0
        assert "entrypoint: CLAUDE.md" in result.stderr
        assert "2/2 files reachable from CLAUDE.md" in result.stdout

    def test_check_links_entrypoint_auto_readme(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Readme.\n---\n# Readme\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert "entrypoint: README.md" in result.stderr

    def test_check_links_entrypoint_missing(self, tmp_path: Path) -> None:
        (tmp_path / "random.md").write_text(
            "---\ndescription: Random.\n---\n# Random\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 2
        assert "no entrypoint found" in result.stderr

    def test_check_links_entrypoint_explicit(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "---\ndescription: Instructions.\n---\n# Claude\n", encoding="utf-8"
        )
        (tmp_path / "custom.md").write_text(
            "---\ndescription: Custom entry.\n---\nSee [claude](CLAUDE.md).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", "--entrypoint", "custom.md", str(tmp_path))
        assert "entrypoint: custom.md" in result.stderr
        assert "2/2 files reachable from custom.md" in result.stdout

    def test_check_links_fix_messages_model_agnostic(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [ghost](ghost.md).\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        # Fix messages use "have a dedicated agent" pattern with model examples.
        assert "e.g. fast model like Haiku" in result.stderr
        assert "e.g. smart model like Opus" in result.stderr
        # No hardcoded "spawn ONE haiku agent".
        assert "spawn ONE haiku" not in result.stderr

    def test_check_links_ignore_excludes_file(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        # Without --ignore: orphan is unreachable
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 1

        # With --ignore: orphan excluded from scan, no warning
        result = run_mdscan("check-links", "--ignore", "orphan.md", str(tmp_path))
        assert result.returncode == 0
        assert "warn:" not in result.stderr


class TestCoverage:
    def test_coverage_all_perfect(self, tmp_path: Path) -> None:
        """Exit 0 when all files described and reachable, no broken links."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 0
        assert "files:         2" in result.stdout
        assert "described:     2 (100%)" in result.stdout
        assert "reachable:     2/2 (100%)" in result.stdout
        assert "broken links:  0" in result.stdout

    def test_coverage_missing_descriptions(self, tmp_path: Path) -> None:
        """Exit 1 when some files lack descriptions."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [other](other.md).\n", encoding="utf-8"
        )
        (tmp_path / "other.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 1
        assert "described:     1 (50%)" in result.stdout

    def test_coverage_unreachable_files(self, tmp_path: Path) -> None:
        """Exit 1 when some files are unreachable."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 1
        assert "reachable:     1/2 (50%)" in result.stdout

    def test_coverage_json(self, tmp_path: Path) -> None:
        """JSON output contains all expected keys."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root file.\n---\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide file.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan("coverage", "--json", str(tmp_path))
        data = json.loads(result.stdout)
        assert data["files"] == 2
        assert data["described"] == 2
        assert data["described_pct"] == 100
        assert data["reachable"] == 2
        assert data["reachable_pct"] == 100
        assert data["broken_links"] == 0
        assert "avg_words" in data
        assert "longest" in data


class TestCheckLinksAllLinks:
    def test_all_links_valid_asset(self, tmp_path: Path) -> None:
        """Valid non-.md link with --all-links should not produce warnings."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [config](config.py).\n", encoding="utf-8"
        )
        (tmp_path / "config.py").write_text("# config\n", encoding="utf-8")
        result = run_mdscan("check-links", "--all-links", str(tmp_path))
        assert result.returncode == 0
        assert "broken asset link" not in result.stderr

    def test_all_links_broken_asset(self, tmp_path: Path) -> None:
        """Broken non-.md link with --all-links should produce a warning."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [old](old_config.py).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", "--all-links", str(tmp_path))
        assert result.returncode == 1
        assert "broken asset link" in result.stderr
        assert "README.md → old_config.py" in result.stderr

    def test_without_flag_ignores_assets(self, tmp_path: Path) -> None:
        """Without --all-links, broken non-.md links are not reported."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [old](old_config.py).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 0
        assert "broken asset link" not in result.stderr


class TestConfig:
    def test_config_ignore_merged_with_flag(self, tmp_path: Path) -> None:
        """Config ignore patterns are cumulative with --ignore CLI flag."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mdscan]\nignore = ["b.md"]\n', encoding="utf-8"
        )
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\n", encoding="utf-8"
        )
        (tmp_path / "b.md").write_text(
            "---\ndescription: B.\n---\n", encoding="utf-8"
        )
        (tmp_path / "c.md").write_text(
            "---\ndescription: C.\n---\n", encoding="utf-8"
        )
        # Config ignores b.md, CLI ignores c.md -> only a.md
        result = run_mdscan("--ignore", "c.md", str(tmp_path))
        assert result.returncode == 0
        assert "a.md" in result.stdout
        assert "b.md" not in result.stdout
        assert "c.md" not in result.stdout

    def test_cli_flag_overrides_config_max_depth(self, tmp_path: Path) -> None:
        """CLI --max-depth takes precedence over config max-depth."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mdscan]\nmax-depth = 5\n", encoding="utf-8"
        )
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.md").write_text(
            "---\ndescription: Root.\n---\n", encoding="utf-8"
        )
        (sub / "nested.md").write_text(
            "---\ndescription: Nested.\n---\n", encoding="utf-8"
        )
        # CLI --max-depth=0 should override config max-depth=5
        result = run_mdscan("--max-depth", "0", str(tmp_path))
        assert "root.md" in result.stdout
        assert "nested.md" not in result.stdout

    def test_config_hint_shown_when_no_config(self, tmp_path: Path) -> None:
        """Config hint appears when warnings exist and no [tool.mdscan] found."""
        (tmp_path / "bad.md").write_text("# No frontmatter\n", encoding="utf-8")
        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1
        assert "hint: to persist settings" in result.stderr
        assert "[tool.mdscan]" in result.stderr

    def test_config_hint_hidden_when_config_exists(self, tmp_path: Path) -> None:
        """Config hint is suppressed when [tool.mdscan] section exists."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mdscan]\nignore = []\n", encoding="utf-8"
        )
        (tmp_path / "bad.md").write_text("# No frontmatter\n", encoding="utf-8")
        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1
        assert "hint: to persist settings" not in result.stderr


class TestSetDescription:
    def test_writes_and_validates(self, tmp_path: Path) -> None:
        f = tmp_path / "target.md"
        f.write_text("# Content\n", encoding="utf-8")

        result = run_mdscan("set-description", str(f), "A short description")
        assert result.returncode == 0
        assert "wrote:" in result.stdout

        content = f.read_text(encoding="utf-8")
        assert "description: A short description" in content

    def test_too_long_exits_1(self, tmp_path: Path) -> None:
        f = tmp_path / "target.md"
        f.write_text("# Content\n", encoding="utf-8")

        long_desc = " ".join(["word"] * 160)
        result = run_mdscan("set-description", str(f), long_desc)
        assert result.returncode == 1
        assert "hint:" in result.stderr
        assert "fix:" in result.stderr
        assert "mdscan set-description" in result.stderr
        # Still writes the file
        content = f.read_text(encoding="utf-8")
        assert "description:" in content
