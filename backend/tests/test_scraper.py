from unittest.mock import Mock

import pytest

from app.services import scraper


@pytest.mark.parametrize("url", ["not-a-url", "https://example.com/wiki/Test", "https://en.wikipedia.org/"])
def test_validate_wikipedia_url_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        scraper.validate_wikipedia_url(url)


def test_extracts_article_content(monkeypatch):
    response = Mock()
    response.text = """<h1>Test Article</h1><div id='mw-content-text'>
      <p>First paragraph.</p><h2>History</h2><p>Second paragraph.</p>
      <ol class='references'><li><a href='/source'>source</a></li></ol></div>"""
    response.raise_for_status.return_value = None
    monkeypatch.setattr(scraper.requests, "get", Mock(return_value=response))

    article = scraper.extract_wikipedia_article("https://en.wikipedia.org/wiki/Test")

    assert article["title"] == "Test Article"
    assert article["content"] == "First paragraph.\nSecond paragraph."
    assert article["sections"] == ["History"]
    assert article["references"] == ["/source"]


def test_extract_reports_empty_and_network_errors(monkeypatch):
    empty = Mock(text="<h1>Empty</h1>")
    empty.raise_for_status.return_value = None
    monkeypatch.setattr(scraper.requests, "get", Mock(return_value=empty))
    assert "error" in scraper.extract_wikipedia_article("https://en.wikipedia.org/wiki/Empty")

    monkeypatch.setattr(scraper.requests, "get", Mock(side_effect=RuntimeError("offline")))
    assert scraper.extract_wikipedia_article("https://en.wikipedia.org/wiki/Test") == {"error": "offline"}
