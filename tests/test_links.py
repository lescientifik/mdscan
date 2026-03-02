"""Tests for markdown link extraction."""

from mdscan.links import extract_md_links


class TestExtractMdLinks:
    def test_extracts_relative_md_links(self) -> None:
        text = (
            "See [setup guide](setup.md) and [API reference](api.md) for details.\n"
            "Also check [nested](sub/deep.md).\n"
        )
        assert extract_md_links(text) == ["setup.md", "api.md", "sub/deep.md"]

    def test_ignores_absolute_and_http_links(self) -> None:
        text = (
            "Visit [docs](https://example.com/docs.md) or "
            "[local](http://localhost/file.md) or "
            "[abs](/root/file.md).\n"
            "But [relative](other.md) is kept.\n"
        )
        assert extract_md_links(text) == ["other.md"]
