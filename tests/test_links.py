"""Tests for markdown link extraction."""

from mdscan.links import extract_all_links, extract_md_links


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


class TestExtractAllLinks:
    def test_captures_all_file_types(self) -> None:
        text = (
            "See [config](src/config.py) and [diagram](images/flow.png)"
            " and [guide](guide.md).\n"
        )
        links = extract_all_links(text)
        assert "src/config.py" in links
        assert "images/flow.png" in links
        assert "guide.md" in links

    def test_ignores_urls_and_absolute(self) -> None:
        text = (
            "Visit [docs](https://example.com/page) or "
            "[local](http://localhost/api) or "
            "[abs](/root/file.py).\n"
            "But [relative](other.py) is kept.\n"
        )
        assert extract_all_links(text) == ["other.py"]

    def test_strips_anchor_fragments(self) -> None:
        text = "See [section](guide.md#installation).\n"
        assert extract_all_links(text) == ["guide.md"]

    def test_ignores_bare_anchors(self) -> None:
        text = "See [section](#overview).\n"
        assert extract_all_links(text) == []
