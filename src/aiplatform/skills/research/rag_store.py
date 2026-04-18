"""
RAG document store skill.

Ingests uploaded files (PDF, TXT, MD) into a Qdrant collection keyed by
research session ID. Returns stored point IDs so the pipeline can retrieve
context for each LLM's research prompt.

Dependencies: qdrant-client, openai (embeddings), pypdf
"""

import io
import logging
import os
import uuid
from typing import BinaryIO

logger = logging.getLogger(__name__)

_COLLECTION = "market_research_rag"
_EMBED_MODEL = "text-embedding-3-small"
_CHUNK_SIZE   = 800   # characters per chunk
_CHUNK_OVERLAP = 100

# ── Qdrant client (lazy) ───────────────────────────────────────────────────────

_qdrant_client = None

def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ.get("QDRANT_API_KEY"),
        )
        _ensure_collection(_qdrant_client)
    return _qdrant_client


def _ensure_collection(client) -> None:
    from qdrant_client.models import Distance, VectorParams
    existing = {c.name for c in client.get_collections().collections}
    if _COLLECTION not in existing:
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        logger.info("rag_store: created Qdrant collection '%s'", _COLLECTION)


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_text(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def _chunk(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


# ── Embedding ──────────────────────────────────────────────────────────────────

def _embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [item.embedding for item in resp.data]


# ── Public API ─────────────────────────────────────────────────────────────────

def ingest_document(filename: str, data: bytes, session_id: str) -> list[str]:
    """
    Parse, chunk, embed, and upsert a document into Qdrant.

    Returns list of point ID strings stored for this document.
    """
    text = _extract_text(filename, data)
    if not text.strip():
        logger.warning("rag_store: %s produced no text", filename)
        return []

    chunks = _chunk(text)
    logger.info("rag_store: %s → %d chunks", filename, len(chunks))

    embeddings = _embed(chunks)
    client = _get_qdrant()

    from qdrant_client.models import PointStruct
    point_ids = [str(uuid.uuid4()) for _ in chunks]
    points = [
        PointStruct(
            id=pid,
            vector=emb,
            payload={
                "session_id": session_id,
                "filename":   filename,
                "chunk_idx":  i,
                "text":       chunk,
            },
        )
        for i, (pid, emb, chunk) in enumerate(zip(point_ids, embeddings, chunks))
    ]
    client.upsert(collection_name=_COLLECTION, points=points)
    logger.info("rag_store: upserted %d points for session %s", len(points), session_id)
    return point_ids


def retrieve_context(query: str, session_id: str, top_k: int = 5) -> str:
    """
    Retrieve the most relevant chunks for a query within a session.

    Returns a single string to be appended to LLM prompts.
    """
    try:
        query_vec = _embed([query])[0]
        client = _get_qdrant()
        hits = client.search(
            collection_name=_COLLECTION,
            query_vector=query_vec,
            limit=top_k,
            query_filter={
                "must": [{"key": "session_id", "match": {"value": session_id}}]
            },
        )
        if not hits:
            return ""
        snippets = [h.payload["text"] for h in hits]
        return "\n\n---\n\n".join(snippets)
    except Exception as exc:
        logger.error("rag_store: retrieval failed — %s", exc)
        return ""


def delete_session_docs(session_id: str) -> None:
    """Remove all vectors for a completed research session."""
    try:
        client = _get_qdrant()
        client.delete(
            collection_name=_COLLECTION,
            points_selector={"filter": {
                "must": [{"key": "session_id", "match": {"value": session_id}}]
            }},
        )
    except Exception as exc:
        logger.error("rag_store: delete failed for session %s — %s", session_id, exc)
