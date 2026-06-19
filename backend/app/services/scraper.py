import requests
from bs4 import BeautifulSoup


def extract_wikipedia_article(url: str) -> dict:
    try:
        print(f"Fetching: {url}")

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

        print(f"Status Code: {response.status_code}")

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("h1")

        paragraphs = soup.find_all("p")

        article_text = "\n".join(
            p.get_text(strip=True)
            for p in paragraphs
            if p.get_text(strip=True)
        )

        return {
            "title": title.get_text(strip=True) if title else "Unknown",
            "content": article_text[:50000]
        }

    except Exception as e:
        return {
            "error": str(e)
        }