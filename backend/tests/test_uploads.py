"""Unit tests for upload helpers: safe_filename, extract_text, chunking."""

from app.indexer import chunk_text
from app.uploads import extract_text, safe_filename, UnsupportedFileTypeError

import pytest


def test_safe_filename_strips_path():
    assert safe_filename("../etc/passwd") == "passwd"
    assert safe_filename("/etc/passwd") == "passwd"


def test_safe_filename_replaces_unsafe_chars():
    assert safe_filename("my cool file.pdf") == "my_cool_file.pdf"
    assert safe_filename("contract #42.docx") == "contract_42.docx"


def test_safe_filename_caps_length():
    long = "a" * 200 + ".pdf"
    out = safe_filename(long)
    assert len(out) <= 120
    assert out.endswith(".pdf")


def test_safe_filename_falls_back_for_empty():
    assert safe_filename(".....") == "file"
    assert safe_filename("") == "file"


def test_extract_text_plain_text():
    out = extract_text("notes.txt", "text/plain", b"hello world")
    assert "hello" in out


def test_extract_text_markdown():
    out = extract_text("notes.md", "text/markdown", b"# Hello\n\nWorld")
    assert "Hello" in out


def test_extract_text_unsupported():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("photo.jpg", "image/jpeg", b"\xff\xd8\xff\xe0")


def test_chunk_text_small_stays_whole():
    assert chunk_text("one paragraph only") == ["one paragraph only"]


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []


def test_chunk_text_splits_long_by_paragraphs():
    # Several paragraphs, each ~600 chars, total ~3000 → multiple chunks.
    paragraphs = ["x" * 600 for _ in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=1500)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 1600  # slack for newlines
    joined = "\n\n".join(chunks)
    # Every character accounted for.
    assert joined.count("x") == text.count("x")


def test_chunk_text_oversized_paragraph_stays_single_chunk():
    huge_paragraph = "x" * 3000
    chunks = chunk_text(huge_paragraph, max_chars=1500)
    # One oversized chunk rather than mid-word splitting.
    assert len(chunks) == 1
    assert len(chunks[0]) == 3000
