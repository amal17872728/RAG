from fastapi import APIRouter

from app.services.embedder import generate_embedding
from app.services.vector_store import search_chunks
from app.services.llm import answer_question

router = APIRouter()


@router.get("/ask")
def ask(question: str):

    query_embedding = generate_embedding(
        question
    )

    chunks = search_chunks(
        query_embedding
    )

    context = "\n".join(chunks)

    answer = answer_question(
        question,
        context
    )

    return {
        "question": question,
        "answer": answer,
        "context": chunks
    }