"""Tests for zotero_arxiv_daily.protocol."""

from tests.canned_responses import make_sample_paper


def test_tldr_uses_abstract():
    paper = make_sample_paper()
    result = paper.generate_tldr()

    assert result == paper.abstract
    assert paper.tldr == paper.abstract


def test_tldr_allows_empty_abstract():
    paper = make_sample_paper(abstract="")
    result = paper.generate_tldr()

    assert result == ""
    assert paper.tldr == ""
