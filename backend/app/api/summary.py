from fastapi import APIRouter
from app.services.scraper import extract_wikipedia_article
from app.services.llm import summarize_article

router = APIRouter()


@router.get("/summary")
def get_summary(url: str):

    article = extract_wikipedia_article(url)

    summary = summarize_article(
        article["content"]
    )

    return {
        "title": article["title"],
        "summary": summary
    }
