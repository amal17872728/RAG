import pytest

from app.services.chunker import chunk_text


def test_chunk_text_uses_overlap():
    assert chunk_text("abcdefghij", chunk_size=6, overlap=2) == ["abcdef", "efghij", "ij"]


def test_chunk_text_returns_empty_for_blank_text():
    assert chunk_text("   ") == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, -1), (10, 10), (10, 11)])
def test_chunk_text_rejects_invalid_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("text", size, overlap)
