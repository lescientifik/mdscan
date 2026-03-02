"""Tests for frontmatter reading, writing, and validation."""

from pathlib import Path

from mdscan.frontmatter import extract_description, is_too_long, write_description


class TestExtractDescription:
    def test_returns_description(self) -> None:
        text = "---\ndescription: Some description.\n---\n# Title\n"
        assert extract_description(text) == "Some description."

    def test_returns_none_without_frontmatter(self) -> None:
        text = "# Just a heading\nNo frontmatter here.\n"
        assert extract_description(text) is None

    def test_returns_none_without_description_key(self) -> None:
        text = "---\ntitle: Something\nauthor: Someone\n---\n"
        assert extract_description(text) is None


class TestWriteDescription:
    def test_creates_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare.md"
        f.write_text("# Existing content\nParagraph.\n", encoding="utf-8")

        write_description(f, "New description")

        content = f.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "description: New description" in content
        assert "# Existing content" in content
        assert "Paragraph." in content

    def test_updates_existing_description(self, tmp_path: Path) -> None:
        f = tmp_path / "existing.md"
        f.write_text(
            "---\ntitle: Keep me\ndescription: Old text\n---\n# Body\n",
            encoding="utf-8",
        )

        write_description(f, "Updated text")

        content = f.read_text(encoding="utf-8")
        assert "description: Updated text" in content
        assert "title: Keep me" in content
        assert "Old text" not in content


class TestValidation:
    def test_too_long(self) -> None:
        desc = " ".join(["word"] * 151)
        assert is_too_long(desc) is True

    def test_within_limit(self) -> None:
        desc = " ".join(["word"] * 150)
        assert is_too_long(desc) is False
