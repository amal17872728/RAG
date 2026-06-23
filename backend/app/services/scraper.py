import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def validate_wikipedia_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"en.wikipedia.org", "www.en.wikipedia.org"}
        or not parsed.path.startswith("/wiki/")
    ):
        raise ValueError("Enter a valid English Wikipedia article URL")


def extract_wikipedia_article(url: str) -> dict:
    try:
        validate_wikipedia_url(url)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("h1")

        content = soup.select_one("#mw-content-text") or soup
        paragraphs = content.find_all("p")

        article_text = "\n".join(
            p.get_text(strip=True)
            for p in paragraphs
            if p.get_text(strip=True)
        )

        if not article_text:
            return {"error": "Wikipedia article contained no readable text"}

        sections = [h.get_text(" ", strip=True) for h in content.select("h2, h3")]
        references = [a.get("href") for a in content.select("ol.references a[href]")]

        return {
            "title": title.get_text(strip=True) if title else "Unknown",
            "content": article_text[:50000],
            "sections": sections,
            "references": references,
        }

    except Exception as e:
        return {
            "error": str(e)
        }
