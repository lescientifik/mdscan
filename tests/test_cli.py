"""End-to-end CLI integration tests."""

import json
import os
import signal
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


class TestSignals:
    def test_ctrl_c_no_traceback(self, tmp_path: Path) -> None:
        """SIGINT produces no traceback, exits with code 130."""
        # Create many files to give us time to send the signal.
        for i in range(50):
            (tmp_path / f"f{i:03d}.md").write_text(
                f"---\ndescription: File {i}.\n---\n", encoding="utf-8"
            )
        proc = subprocess.Popen(
            [sys.executable, "-m", "mdscan", "scan", str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        os.kill(proc.pid, signal.SIGINT)
        _, stderr = proc.communicate(timeout=5)
        assert b"Traceback" not in stderr
        # 130 = 128 + SIGINT(2), or process may exit before signal arrives (0).
        assert proc.returncode in (130, -2, 0)

    def test_broken_pipe_no_traceback(self, tmp_path: Path) -> None:
        """Piping to a process that closes early produces no traceback."""
        for i in range(20):
            (tmp_path / f"f{i:03d}.md").write_text(
                f"---\ndescription: File {i}.\n---\n", encoding="utf-8"
            )
        result = subprocess.run(
            f"{sys.executable} -m mdscan scan {tmp_path} | head -1",
            shell=True,
            capture_output=True,
            text=True,
        )
        assert "Traceback" not in result.stderr


class TestScanExitCodes:
    def test_exit_0_all_valid(self, all_valid: Path) -> None:
        result = run_mdscan(str(all_valid))
        assert result.returncode == 0
        assert "warn:" not in result.stderr

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
    def test_scan_text_does_not_show_links(self, tmp_path: Path) -> None:
        (tmp_path / "index.md").write_text(
            "---\ndescription: Index page.\n---\nSee [guide](guide.md) and [faq](faq.md).\n",
            encoding="utf-8",
        )
        (tmp_path / "guide.md").write_text(
            "---\ndescription: Guide page.\n---\n# Guide\n", encoding="utf-8"
        )
        result = run_mdscan(str(tmp_path))
        assert "→ links:" not in result.stdout
        assert "index.md" in result.stdout
        assert "guide.md" in result.stdout

    def test_scan_json_does_not_include_links(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\nSee [b](b.md).\n", encoding="utf-8"
        )
        (tmp_path / "b.md").write_text(
            "---\ndescription: B.\n---\n# B\n", encoding="utf-8"
        )
        result = run_mdscan("--json", str(tmp_path))
        data = json.loads(result.stdout)
        a_entry = next(e for e in data if e["path"] == "a.md")
        assert "links" not in a_entry


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
        assert result.returncode == 3
        assert "warn:" in result.stderr
        assert "unreachable from README.md" in result.stderr
        assert "  - orphan.md" in result.stderr
        assert "fix:" in result.stderr

    def test_check_links_broken_link(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [missing](ghost.md).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 3
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
        # Without --ignore: orphan is unreachable (structural issue)
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 3

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
        """Exit 3 when some files are unreachable (structural issue)."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 3
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


class TestExitCodes:
    """Graduated exit codes: 0=ok, 1=warn, 2=usage, 3=structural."""

    def test_exit_3_broken_links(self, tmp_path: Path) -> None:
        """check-links with a broken link exits 3."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [ghost](ghost.md).\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 3

    def test_exit_3_unreachable_files(self, tmp_path: Path) -> None:
        """check-links with unreachable files exits 3."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", str(tmp_path))
        assert result.returncode == 3

    def test_exit_1_remains_for_soft_warnings(self, tmp_path: Path) -> None:
        """scan with missing descriptions still exits 1."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1

    def test_exit_3_coverage_structural(self, tmp_path: Path) -> None:
        """coverage with unreachable files exits 3 (structural)."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [ghost](ghost.md).\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 3

    def test_exit_1_coverage_soft(self, tmp_path: Path) -> None:
        """coverage where all reachable but some missing descriptions exits 1."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\nSee [other](other.md).\n", encoding="utf-8"
        )
        (tmp_path / "other.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan("coverage", str(tmp_path))
        assert result.returncode == 1


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
        assert result.returncode == 3
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


class TestHelp:
    def test_scan_help_has_examples(self) -> None:
        result = run_mdscan("scan", "-h")
        assert result.returncode == 0
        assert "example" in result.stdout.lower()
        assert "mdscan scan" in result.stdout

    def test_check_links_help_has_examples(self) -> None:
        result = run_mdscan("check-links", "-h")
        assert result.returncode == 0
        assert "example" in result.stdout.lower()
        assert "mdscan check-links" in result.stdout

    def test_tree_help_has_examples(self) -> None:
        result = run_mdscan("tree", "-h")
        assert result.returncode == 0
        assert "example" in result.stdout.lower()
        assert "mdscan tree" in result.stdout

    def test_coverage_help_has_examples(self) -> None:
        result = run_mdscan("coverage", "-h")
        assert result.returncode == 0
        assert "example" in result.stdout.lower()
        assert "mdscan coverage" in result.stdout

    def test_set_description_help_has_examples(self) -> None:
        result = run_mdscan("set-description", "-h")
        assert result.returncode == 0
        assert "example" in result.stdout.lower()
        assert "mdscan set-description" in result.stdout

    def test_top_level_help_has_url(self) -> None:
        result = run_mdscan("--help")
        assert result.returncode == 0
        assert "github.com" in result.stdout

    def test_typo_suggestion(self) -> None:
        result = run_mdscan("scna")
        assert result.returncode == 2
        assert "did you mean" in result.stderr.lower()
        assert "scan" in result.stderr

    def test_unknown_command_no_match(self) -> None:
        result = run_mdscan("xyzzy")
        # No close match — falls through to scan which treats it as a path.
        # "xyzzy" is not a directory, so scan will error.
        assert result.returncode == 2

    def test_help_subcommand(self) -> None:
        result = run_mdscan("help")
        assert result.returncode == 0
        top = run_mdscan("--help")
        assert result.stdout == top.stdout

    def test_help_subcommand_with_target(self) -> None:
        result = run_mdscan("help", "scan")
        assert result.returncode == 0
        direct = run_mdscan("scan", "--help")
        assert result.stdout == direct.stdout


class TestNextSteps:
    def test_scan_suggests_check_links(self, all_valid: Path) -> None:
        result = run_mdscan(str(all_valid))
        assert "check-links" in result.stderr

    def test_no_suggestion_in_json_mode(self, all_valid: Path) -> None:
        result = run_mdscan("--json", str(all_valid))
        assert "check-links" not in result.stderr

    def test_no_suggestion_in_quiet_mode(self, all_valid: Path) -> None:
        result = run_mdscan("-q", str(all_valid))
        assert "check-links" not in result.stderr


class TestQuiet:
    def test_quiet_suppresses_diagnostics(self, tmp_path: Path) -> None:
        """--quiet suppresses warnings on stderr, exit code unchanged."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan("-q", str(tmp_path))
        assert result.returncode == 1
        assert result.stderr == ""

    def test_quiet_suppresses_stdout_text(self, all_valid: Path) -> None:
        """--quiet suppresses text output on stdout."""
        result = run_mdscan("-q", str(all_valid))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_quiet_preserves_json(self, all_valid: Path) -> None:
        """--quiet still outputs JSON (data must flow for piping)."""
        result = run_mdscan("-q", "--json", str(all_valid))
        data = json.loads(result.stdout)
        assert len(data) == 2

    def test_quiet_on_check_links(self, tmp_path: Path) -> None:
        """--quiet suppresses stderr on check-links."""
        (tmp_path / "README.md").write_text(
            "---\ndescription: Root.\n---\n# Root\n", encoding="utf-8"
        )
        (tmp_path / "orphan.md").write_text(
            "---\ndescription: Orphan.\n---\n# Orphan\n", encoding="utf-8"
        )
        result = run_mdscan("check-links", "-q", str(tmp_path))
        assert result.returncode == 3
        assert result.stderr == ""


class TestEnvVars:
    def test_mdscan_quiet_env(self, tmp_path: Path) -> None:
        """MDSCAN_QUIET=1 behaves like -q."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        env = {**os.environ, "MDSCAN_QUIET": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "mdscan", str(tmp_path)],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 1
        assert result.stderr == ""

    def test_flag_overrides_env(self, tmp_path: Path) -> None:
        """CLI -v flag overrides MDSCAN_QUIET env var."""
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\n", encoding="utf-8"
        )
        env = {**os.environ, "MDSCAN_QUIET": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "mdscan", "-v", str(tmp_path)],
            capture_output=True, text=True, env=env,
        )
        # -v wins over MDSCAN_QUIET: verbose info appears
        assert "scanned:" in result.stderr


class TestColor:
    def test_no_color_env_disables_color(self, tmp_path: Path) -> None:
        """NO_COLOR=1 disables ANSI escape codes in stderr."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        env = {**os.environ, "NO_COLOR": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "mdscan", str(tmp_path)],
            capture_output=True, text=True, env=env,
        )
        assert "\x1b[" not in result.stderr

    def test_no_color_flag_disables_color(self, tmp_path: Path) -> None:
        """--no-color flag disables ANSI escape codes in stderr."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan("--no-color", str(tmp_path))
        assert "\x1b[" not in result.stderr

    def test_color_off_when_not_tty(self, tmp_path: Path) -> None:
        """No ANSI escapes when stderr is not a TTY (subprocess capture)."""
        (tmp_path / "bad.md").write_text("# No desc\n", encoding="utf-8")
        result = run_mdscan(str(tmp_path))
        assert "\x1b[" not in result.stderr


class TestVerbose:
    def test_verbose_shows_config_source(self, tmp_path: Path) -> None:
        """--verbose shows config file path on stderr."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mdscan]\nignore = []\n", encoding="utf-8"
        )
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\n", encoding="utf-8"
        )
        result = run_mdscan("-v", str(tmp_path))
        assert "config:" in result.stderr
        assert "pyproject.toml" in result.stderr

    def test_verbose_shows_scan_stats(self, tmp_path: Path) -> None:
        """--verbose shows scan stats on stderr."""
        (tmp_path / "a.md").write_text(
            "---\ndescription: A.\n---\n", encoding="utf-8"
        )
        result = run_mdscan("-v", str(tmp_path))
        assert "scanned:" in result.stderr


class TestPlain:
    def test_plain_output_tab_separated(self, all_valid: Path) -> None:
        result = run_mdscan("scan", "--plain", str(all_valid))
        assert result.returncode == 0
        for line in result.stdout.strip().splitlines():
            assert line.count("\t") == 1

    def test_plain_pipeable_to_cut(self, all_valid: Path) -> None:
        """Tab-separated output: field 1 is path only."""
        result = run_mdscan("scan", "--plain", str(all_valid))
        for line in result.stdout.strip().splitlines():
            path = line.split("\t")[0]
            assert path.endswith(".md")


class TestLimit:
    def test_limit_truncates_output(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"f{i:02d}.md").write_text(
                f"---\ndescription: File {i}.\n---\n", encoding="utf-8"
            )
        result = run_mdscan("scan", "--limit", "3", str(tmp_path))
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 3

    def test_limit_with_json(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"f{i:02d}.md").write_text(
                f"---\ndescription: File {i}.\n---\n", encoding="utf-8"
            )
        result = run_mdscan("scan", "--json", "--limit", "3", str(tmp_path))
        data = json.loads(result.stdout)
        assert len(data) == 3

    def test_limit_zero_means_no_limit(self, tmp_path: Path) -> None:
        for i in range(5):
            (tmp_path / f"f{i}.md").write_text(
                f"---\ndescription: File {i}.\n---\n", encoding="utf-8"
            )
        result = run_mdscan("scan", "--limit", "0", str(tmp_path))
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 5


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

    def test_stdin_dash(self, tmp_path: Path) -> None:
        """Reading description from stdin with '-'."""
        f = tmp_path / "target.md"
        f.write_text("# Content\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "mdscan", "set-description", str(f), "-"],
            input="My stdin description\n",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        content = f.read_text(encoding="utf-8")
        assert "description: My stdin description" in content

    def test_stdin_dash_strips_whitespace(self, tmp_path: Path) -> None:
        """stdin description is stripped of leading/trailing whitespace."""
        f = tmp_path / "target.md"
        f.write_text("# Content\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "mdscan", "set-description", str(f), "-"],
            input="  padded description  \n\n",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        content = f.read_text(encoding="utf-8")
        assert "description: padded description" in content


