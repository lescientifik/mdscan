"""Shared fixtures for mdscan tests."""

from pathlib import Path

import pytest


@pytest.fixture()
def md_tree(tmp_path: Path) -> Path:
    """Create a directory tree with various .md files for testing.

    Layout::

        root/
            valid.md          — has description
            no_fm.md          — no frontmatter at all
            no_desc.md        — frontmatter but no description key
            verbose.md        — description > 150 words
            sub/
                nested.md     — has description
            node_modules/
                hidden.md     — should be excluded
            .git/
                hidden2.md    — should be excluded
    """
    (tmp_path / "valid.md").write_text(
        "---\ndescription: A valid description.\n---\n# Valid\n",
        encoding="utf-8",
    )
    (tmp_path / "no_fm.md").write_text(
        "# No frontmatter\nJust content.\n",
        encoding="utf-8",
    )
    (tmp_path / "no_desc.md").write_text(
        "---\ntitle: Something\n---\n# No desc\n",
        encoding="utf-8",
    )
    long_desc = " ".join(["word"] * 160)
    (tmp_path / "verbose.md").write_text(
        f"---\ndescription: {long_desc}\n---\n# Verbose\n",
        encoding="utf-8",
    )

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.md").write_text(
        "---\ndescription: Nested file description.\n---\n# Nested\n",
        encoding="utf-8",
    )

    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "hidden.md").write_text(
        "---\ndescription: Should not appear.\n---\n",
        encoding="utf-8",
    )

    git = tmp_path / ".git"
    git.mkdir()
    (git / "hidden2.md").write_text(
        "---\ndescription: Should not appear.\n---\n",
        encoding="utf-8",
    )

    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "hidden3.md").write_text(
        "---\ndescription: Should not appear.\n---\n",
        encoding="utf-8",
    )

    return tmp_path
