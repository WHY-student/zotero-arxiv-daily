"""Tests for ArxivRetriever."""

import time
from types import SimpleNamespace

from zotero_arxiv_daily.retriever.arxiv_retriever import ArxivRetriever, _run_with_hard_timeout
import zotero_arxiv_daily.retriever.arxiv_retriever as arxiv_retriever


class AttrDict(dict):
    def __getattr__(self, name):
        return self[name]


def _sleep_and_return(value: str, delay_seconds: float) -> str:
    time.sleep(delay_seconds)
    return value


def _raise_runtime_error() -> None:
    raise RuntimeError("boom")


def test_arxiv_retriever(config, mock_feedparser, monkeypatch):
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    new_entries = [
        e for e in mock_feedparser.entries
        if e.get("arxiv_announce_type", "new") == "new"
    ]

    retriever = ArxivRetriever(config)
    papers = retriever.retrieve_papers()

    assert len(papers) == len(new_entries)
    assert set(p.title for p in papers) == set(e.title for e in new_entries)
    assert all(p.full_text is None for p in papers)
    assert all(p.url.startswith("https://arxiv.org/abs/") for p in papers)


def test_arxiv_retriever_retries_empty_rss(config, monkeypatch):
    entries = [
        AttrDict(
            id="oai:arXiv.org:2606.00001v1",
            title="Recovered RSS paper",
            summary="arXiv:2606.00001v1 Announce Type: new \nAbstract: Recovered abstract",
            authors=[{"name": "Test Author"}],
            links=[{"href": "https://arxiv.org/abs/2606.00001", "rel": "alternate"}],
            arxiv_announce_type="new",
        )
    ]
    feeds = [
        SimpleNamespace(feed=SimpleNamespace(title="ok"), entries=[]),
        SimpleNamespace(feed=SimpleNamespace(title="ok"), entries=[]),
        SimpleNamespace(feed=SimpleNamespace(title="ok"), entries=entries),
    ]
    sleeps: list[int] = []
    monkeypatch.setattr(arxiv_retriever.feedparser, "parse", lambda url: feeds.pop(0))
    monkeypatch.setattr(arxiv_retriever, "sleep", sleeps.append)

    retriever = ArxivRetriever(config)
    papers = retriever._retrieve_raw_papers()

    assert papers == entries
    assert sleeps == [
        arxiv_retriever.ARXIV_RSS_EMPTY_RETRY_DELAY_SECONDS,
        arxiv_retriever.ARXIV_RSS_EMPTY_RETRY_DELAY_SECONDS,
    ]


def test_arxiv_retriever_returns_empty_after_empty_rss_retries(config, monkeypatch):
    feeds = [
        SimpleNamespace(feed=SimpleNamespace(title="ok"), entries=[])
        for _ in range(arxiv_retriever.ARXIV_RSS_EMPTY_RETRY_ATTEMPTS)
    ]
    monkeypatch.setattr(arxiv_retriever.feedparser, "parse", lambda url: feeds.pop(0))
    monkeypatch.setattr(arxiv_retriever, "sleep", lambda _: None)

    retriever = ArxivRetriever(config)
    papers = retriever._retrieve_raw_papers()

    assert papers == []


def test_arxiv_convert_to_paper_does_not_extract_full_text(config, monkeypatch):
    def fail_if_called(paper):
        raise AssertionError("full text extraction should not run")

    monkeypatch.setattr(arxiv_retriever, "extract_text_from_tar", fail_if_called)
    monkeypatch.setattr(arxiv_retriever, "extract_text_from_html", fail_if_called)
    monkeypatch.setattr(arxiv_retriever, "extract_text_from_pdf", fail_if_called)

    raw_paper = AttrDict(
        title="Paper title",
        authors=[{"name": "Test Author"}],
        summary="arXiv:2606.00000v1 Announce Type: new \nAbstract: Abstract text",
        links=[{"href": "https://arxiv.org/abs/2606.00000", "rel": "alternate"}],
    )

    paper = ArxivRetriever(config).convert_to_paper(raw_paper)

    assert paper.title == "Paper title"
    assert paper.abstract == "Abstract text"
    assert paper.url == "https://arxiv.org/abs/2606.00000"
    assert paper.pdf_url == "https://arxiv.org/pdf/2606.00000"
    assert paper.full_text is None


def test_run_with_hard_timeout_returns_value():
    result = _run_with_hard_timeout(
        _sleep_and_return, ("done", 0.01), timeout=10, operation="test op", paper_title="paper"
    )
    assert result == "done"


def test_run_with_hard_timeout_returns_none_on_timeout(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(arxiv_retriever, "logger", SimpleNamespace(warning=warnings.append))
    result = _run_with_hard_timeout(
        _sleep_and_return, ("done", 1.0), timeout=0.01, operation="test op", paper_title="paper"
    )
    assert result is None
    assert "timed out" in warnings[0]


def test_run_with_hard_timeout_returns_none_on_failure(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(arxiv_retriever, "logger", SimpleNamespace(warning=warnings.append))
    result = _run_with_hard_timeout(
        _raise_runtime_error, (), timeout=10, operation="test op", paper_title="paper"
    )
    assert result is None
    assert "boom" in warnings[0]
