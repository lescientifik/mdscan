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
        assert "bad.md" in result.stderr
        assert "mdscan set-description bad.md" in result.stderr

    def test_exit_1_description_too_long(self, tmp_path: Path) -> None:
        long_desc = " ".join(["word"] * 160)
        (tmp_path / "long.md").write_text(
            f"---\ndescription: {long_desc}\n---\n", encoding="utf-8"
        )

        result = run_mdscan(str(tmp_path))
        assert result.returncode == 1
        assert "hint:" in result.stderr
        assert "160 words" in result.stderr
        assert "mdscan set-description long.md" in result.stderr


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
        assert "mdscan set-description" in result.stderr
        # Still writes the file
        content = f.read_text(encoding="utf-8")
        assert "description:" in content
