"""Tests for mdscan config loading from pyproject.toml."""

from pathlib import Path

from mdscan.config import MdscanConfig, has_config, load_config


class TestLoadConfig:
    def test_parse_all_keys(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mdscan]\nignore = ["drafts/*", "archive/*"]\n'
            'max-depth = 3\nentrypoint = "docs/index.md"\n',
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.ignore == ["drafts/*", "archive/*"]
        assert cfg.max_depth == 3
        assert cfg.entrypoint == "docs/index.md"

    def test_missing_section_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 99\n", encoding="utf-8"
        )
        cfg = load_config(tmp_path)
        assert cfg == MdscanConfig()

    def test_no_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg == MdscanConfig()

    def test_walks_up_parents(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mdscan]\nignore = ["vendor/*"]\n', encoding="utf-8"
        )
        child = tmp_path / "a" / "b"
        child.mkdir(parents=True)
        cfg = load_config(child)
        assert cfg.ignore == ["vendor/*"]

    def test_partial_keys(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mdscan]\nmax-depth = 2\n', encoding="utf-8"
        )
        cfg = load_config(tmp_path)
        assert cfg.max_depth == 2
        assert cfg.ignore == []
        assert cfg.entrypoint is None


class TestHasConfig:
    def test_true_when_section_exists(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mdscan]\nignore = []\n", encoding="utf-8"
        )
        assert has_config(tmp_path) is True

    def test_false_when_no_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\n", encoding="utf-8"
        )
        assert has_config(tmp_path) is False

    def test_false_when_no_pyproject(self, tmp_path: Path) -> None:
        assert has_config(tmp_path) is False
