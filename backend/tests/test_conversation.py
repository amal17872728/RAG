from app.services import conversation


def setup_function():
    conversation._store.clear()


def test_follow_up_resolution_uses_previous_question():
    turns = [{"question": "Who founded Python?", "answer": "Guido van Rossum founded Python [1]."}]

    resolved = conversation.resolve_question("When?", turns)

    assert resolved == "When? (referring to the previous question: Who founded Python?)"


def test_standalone_question_is_not_rewritten():
    turns = [{"question": "Who founded Python?", "answer": "Guido van Rossum founded Python [1]."}]

    assert conversation.resolve_question("What is the capital of France?", turns) == "What is the capital of France?"


def test_trim_history_keeps_sliding_window_and_token_budget():
    for index in range(6):
        conversation.add_turn("conv-1", f"Question {index}?", "short answer")

    recent = conversation.get_recent_turns("conv-1")

    assert [turn["question"] for turn in recent] == [
        "Question 2?",
        "Question 3?",
        "Question 4?",
        "Question 5?",
    ]

    long_answer = "x" * ((conversation.MAX_HISTORY_TOKENS + 20) * 4)
    conversation.add_turn("conv-2", "Old question?", "short answer")
    conversation.add_turn("conv-2", "Huge question?", long_answer)

    assert conversation.get_recent_turns("conv-2") == []


def test_conversation_isolation():
    conversation.add_turn("conv-a", "Who founded Python?", "Guido van Rossum founded Python [1].")
    conversation.add_turn("conv-b", "Who created Linux?", "Linus Torvalds created Linux [1].")

    assert conversation.resolve_question("When?", conversation.get_recent_turns("conv-a")) == (
        "When? (referring to the previous question: Who founded Python?)"
    )
    assert conversation.resolve_question("When?", conversation.get_recent_turns("conv-b")) == (
        "When? (referring to the previous question: Who created Linux?)"
    )
