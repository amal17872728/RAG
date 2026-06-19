from fastapi import APIRouter
from app.services.scraper import extract_wikipedia_article

router = APIRouter()


@router.get("/article")
def get_article(url: str):
    return extract_wikipedia_article(url)