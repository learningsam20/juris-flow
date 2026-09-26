"""Rebuild the vector index from stored document text.

Re-embeds every existing document from its extracted ``text`` so the vector
store is guaranteed consistent with the relational database. Run after a
vector store reset or restore. Requires a resolved vector store (e.g. local
Ollama embeddings + embedded Qdrant) and should be run while the API server is
stopped so the embedded Qdrant lock is released.

Usage:  python -m app.db.reindex
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.constants import DOCS_COLLECTION
from app.db.session import SessionLocal
from app.embeddings.factory import get_embeddings
from app.ingestion.chunker import chunk_text
from app.models import DocumentChunk, LegalDocument
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger("app.db.reindex")


def reindex_all(db: Session | None = None) -> dict:
    """Re-chunk and re-embed every document, replacing DocumentChunk rows."""
    own = db is None
    db = db or SessionLocal()
    store = get_vectorstore()
    embedder = get_embeddings()
    store.ensure_collection(DOCS_COLLECTION)

    docs = db.query(LegalDocument).order_by(LegalDocument.created_at.asc()).all()
    documents_indexed = 0
    chunks_indexed = 0
    failed: list[str] = []

    for doc in docs:
        text = (doc.text or "").strip()
        if not text:
            doc.status = "ingested"
            db.add(doc)
            db.commit()
            continue

        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
        chunks = chunk_text(text)
        try:
            vectors = embedder.embed(chunks) if chunks else []
        except Exception as exc:  # local provider may be down mid-run
            failed.append(f"{doc.title or doc.id}: {exc}")
            doc.vector_id = None
            doc.status = "ingested"
            db.add(doc)
            db.commit()
            continue

        if len(vectors) != len(chunks):
            failed.append(f"{doc.title or doc.id}: embedding count mismatch")
            doc.status = "ingested"
            db.add(doc)
            db.commit()
            continue

        ids: list[str] = []
        payloads: list[dict] = []
        for i, (chunk, _vec) in enumerate(zip(chunks, vectors)):
            cid = f"{doc.id}:{i}"
            ids.append(cid)
            payloads.append(
                {
                    "document_id": doc.id,
                    "chunk_index": i,
                    "text": chunk,
                    "organization_id": doc.organization_id,
                    "jurisdiction": doc.jurisdiction or "",
                    "domain": doc.domain or "",
                    "doc_type": doc.doc_type or "",
                    "source_status": doc.source_status or "",
                    "effective_date": doc.effective_date or "",
                }
            )
            db.add(
                DocumentChunk(
                    id=cid,
                    document_id=doc.id,
                    chunk_index=i,
                    text=chunk,
                    vector_id=cid,
                )
            )
        if ids:
            store.upsert(DOCS_COLLECTION, ids, vectors, payloads)
            doc.vector_id = ids[0]
        doc.status = "indexed"
        db.add(doc)
        db.commit()
        documents_indexed += 1
        chunks_indexed += len(ids)

    if own:
        db.close()

    return {
        "documents_indexed": documents_indexed,
        "chunks_indexed": chunks_indexed,
        "failed": failed,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = reindex_all()
    logger.info("Reindex complete: %s", result)
    if result["failed"]:
        raise SystemExit(
            f"{len(result['failed'])} document(s) failed: {result['failed']}"
        )
