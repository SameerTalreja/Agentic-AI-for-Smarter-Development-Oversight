"""
core/document_tools.py

Local RAG layer: embeds document chunks with a small local sentence-
transformers model (no API key, no cost), stores embeddings in SQLite as
serialized numpy arrays, and exposes search_document() as an agent tool
using plain numpy cosine similarity (fine at this scale -- a handful of
uploaded documents, not a large corpus needing a dedicated vector DB).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from db.database import session_scope
from db.models import Dataset, DocumentChunk
from core.document_loader import load_document

_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model once per process (first call downloads
    and caches ~80MB locally; subsequent calls are instant)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _embed(texts: list[str]) -> np.ndarray:
    model = _get_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def ingest_document(dataset_id: str, filepath: str) -> dict[str, Any]:
    """
    Loads, chunks, embeds, and stores a document's chunks in the DB.
    Called once at upload time (see backend/routes/datasets.py).
    """
    result = load_document(filepath)

    if not result.chunks:
        return {"dataset_id": dataset_id, "chunks_stored": 0, "warning": "No extractable text found."}

    texts = [c.text for c in result.chunks]
    embeddings = _embed(texts)

    with session_scope() as db:
        for chunk, emb in zip(result.chunks, embeddings):
            db.add(DocumentChunk(
                dataset_id=dataset_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                chunk_text=chunk.text,
                embedding=emb.astype(np.float32).tobytes(),
            ))

    return {
        "dataset_id": dataset_id,
        "chunks_stored": len(result.chunks),
        "total_pages": result.total_pages,
        "char_count": result.char_count,
    }


def search_document(dataset_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """
    Agent tool: embeds the query, computes cosine similarity against all
    stored chunks for this dataset, returns the top_k most relevant
    passages with their similarity scores and page numbers.

    This is the document-track equivalent of filter_rows/aggregate for
    tabular data -- the tool an agent calls to ground its answer in real
    document content instead of guessing.
    """
    with session_scope() as db:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            return {"error": f"No dataset found with id '{dataset_id}'"}
        if dataset.type != "document":
            return {"error": f"Dataset '{dataset_id}' is not a document dataset (type={dataset.type})."}

        chunks = db.query(DocumentChunk).filter(DocumentChunk.dataset_id == dataset_id).all()
        if not chunks:
            return {"dataset_id": dataset_id, "query": query, "results": [],
                     "note": "No indexed content for this document."}

        chunk_data = [
            {"chunk_index": c.chunk_index, "page_number": c.page_number, "text": c.chunk_text,
             "embedding": np.frombuffer(c.embedding, dtype=np.float32)}
            for c in chunks
        ]

    query_embedding = _embed([query])[0]

    matrix = np.stack([c["embedding"] for c in chunk_data])
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
    similarities = matrix_norm @ query_norm

    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = [
        {
            "chunk_index": int(chunk_data[i]["chunk_index"]),
            "page_number": chunk_data[i]["page_number"],
            "text": chunk_data[i]["text"],
            "similarity": round(float(similarities[i]), 4),
        }
        for i in top_indices
    ]

    return {
        "dataset_id": dataset_id,
        "query": query,
        "results_returned": len(results),
        "results": results,
    }


def list_documents(dataset_id: Optional[str] = None) -> dict[str, Any]:
    """List available document datasets (or chunk count for one specific dataset)."""
    with session_scope() as db:
        query = db.query(Dataset).filter(Dataset.type == "document")
        if dataset_id:
            query = query.filter(Dataset.id == dataset_id)
        datasets = query.all()

        return {
            "documents": [
                {
                    "dataset_id": d.id,
                    "name": d.name,
                    "filename": d.filename,
                    "chunk_count": db.query(DocumentChunk).filter(DocumentChunk.dataset_id == d.id).count(),
                }
                for d in datasets
            ]
        }


DOCUMENT_TOOL_SCHEMAS = [
    {
        "name": "search_document",
        "description": "Search an uploaded document (PDF/Word) for passages relevant to a query, using semantic similarity. Use this instead of filter_rows/aggregate when the active dataset is a document, not a spreadsheet. Returns the most relevant passages with page numbers, ranked by similarity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "query": {"type": "string", "description": "What to search for, e.g. 'procurement tender requirements'"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_documents",
        "description": "List available uploaded document datasets and how many indexed chunks each has.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
            },
        },
    },
]

DOCUMENT_TOOL_FUNCTIONS = {
    "search_document": search_document,
    "list_documents": list_documents,
}


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python -m core.document_tools <dataset_id> <query>")
        sys.exit(1)

    dataset_id, query = sys.argv[1], sys.argv[2]
    result = search_document(dataset_id, query)
    print(json.dumps(result, indent=2))