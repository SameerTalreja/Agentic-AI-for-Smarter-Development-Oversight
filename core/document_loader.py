"""
core/document_loader.py

Extracts text from uploaded PDF/Word documents and splits it into
overlapping chunks suitable for embedding + retrieval. This is the
unstructured-data counterpart to core/data_loader.py (tabular).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import pdfplumber
from docx import Document as DocxDocument


@dataclass
class DocumentChunkData:
    chunk_index: int
    text: str
    page_number: int | None = None


@dataclass
class DocumentLoadResult:
    chunks: list[DocumentChunkData] = field(default_factory=list)
    total_pages: int | None = None
    char_count: int = 0


CHUNK_WORD_SIZE = 220
CHUNK_OVERLAP_WORDS = 40


def _chunk_text(text: str, page_number: int | None, start_index: int) -> list[DocumentChunkData]:
    words = text.split()
    if not words:
        return []

    chunks = []
    i = 0
    idx = start_index
    while i < len(words):
        chunk_words = words[i : i + CHUNK_WORD_SIZE]
        chunk_text = " ".join(chunk_words)
        chunks.append(DocumentChunkData(chunk_index=idx, text=chunk_text, page_number=page_number))
        idx += 1
        if i + CHUNK_WORD_SIZE >= len(words):
            break
        i += CHUNK_WORD_SIZE - CHUNK_OVERLAP_WORDS

    return chunks


def load_pdf(path: str) -> DocumentLoadResult:
    chunks: list[DocumentChunkData] = []
    char_count = 0
    idx = 0

    with pdfplumber.open(path) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            char_count += len(text)
            if not text.strip():
                continue
            page_chunks = _chunk_text(text, page_number=page_num, start_index=idx)
            chunks.extend(page_chunks)
            idx += len(page_chunks)

    return DocumentLoadResult(chunks=chunks, total_pages=total_pages, char_count=char_count)


def load_docx(path: str) -> DocumentLoadResult:
    doc = DocxDocument(path)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    char_count = len(full_text)

    chunks = _chunk_text(full_text, page_number=None, start_index=0)

    return DocumentLoadResult(chunks=chunks, total_pages=None, char_count=char_count)


def load_document(path: str) -> DocumentLoadResult:
    """Dispatch to the right loader based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return load_pdf(path)
    elif ext in (".docx", ".doc"):
        return load_docx(path)
    else:
        raise ValueError(f"Unsupported document type '{ext}'. Supported: .pdf, .docx")


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    result = load_document(path)
    print(f"Total pages: {result.total_pages}")
    print(f"Char count: {result.char_count}")
    print(f"Chunks: {len(result.chunks)}")
    if result.chunks:
        print("\n--- First chunk ---")
        print(f"page={result.chunks[0].page_number}")
        print(result.chunks[0].text[:300])