"""Document upload, ingestion, indexing and retrieval service (PRD §5.2, §5.3)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.core.constants import DOCS_COLLECTION
from app.core.errors import ConflictError, ValidationError
from app.core.telemetry import incr
from app.embeddings.factory import get_embeddings
from app.ingestion.chunker import chunk_text
from app.ingestion.parser import parse_document
from app.ingestion.scanner import scan_text
from app.ingestion.storage import get_storage
from app.models import DocumentChunk, LegalDocument
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger(__name__)


def upload_document(
    *,
    organization_id: str,
    user_id: str,
    filename: str,
    content: bytes,
    title: str = "",
    doc_type: str = "contract",
    doc_category: str | None = None,
    jurisdiction: str = "",
    domain: str = "",
    effective_date: str | None = None,
    version: str = "1.0",
    source_status: str = "verified",
    overwrite: bool = False,
    db: Session,
) -> dict:
    target_title = (title or filename).strip()
    existing_doc = (
        db.query(LegalDocument)
        .filter(
            LegalDocument.organization_id == organization_id,
            or_(
                func.lower(LegalDocument.title) == target_title.lower(),
                func.lower(LegalDocument.title) == filename.strip().lower(),
            ),
        )
        .first()
    )
    if existing_doc:
        if not overwrite:
            raise ConflictError(
                f"A document named '{existing_doc.title}' already exists. Please confirm replacement."
            )
        delete_document(
            document_id=existing_doc.id,
            organization_id=organization_id,
            db=db,
        )

    storage = get_storage()
    store = get_vectorstore()
    embedder = get_embeddings()

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    parse_result = parse_document(filename, content)
    text = parse_result.text
    if not text.strip():
        raise ValidationError("no extractable text in uploaded document")

    scan = scan_text(text)
    if scan.has_injection:
        logger.warning(
            "prompt-injection content detected in upload; flagged and isolated",
            extra={"file_name": filename},
        )
        # Injections are isolated: the stored text still avoids instructing agents
    store_text = scan.redacted_text if scan.has_pii else text

    storage_key = f"{organization_id}/{uuid.uuid4().hex}.{ext}"
    storage.store(storage_key, content)

    resolved_category = (doc_category or "").strip()
    if not resolved_category:
        if (doc_type or "").lower() in (
            "contract",
            "agreement",
            "nda",
            "lease",
            "contract_review",
        ):
            resolved_category = "contract_review"
        else:
            resolved_category = "knowledge_artefact"

    document = LegalDocument(
        id=uuid.uuid4().hex,
        organization_id=organization_id,
        title=title or filename,
        doc_type=doc_type,
        jurisdiction=jurisdiction,
        domain=domain,
        effective_date=effective_date,
        version=version,
        source_status=source_status,
        text=store_text,
        metadata_json={
            "filename": filename,
            "ext": ext,
            "document_category": resolved_category,
            "doc_category": resolved_category,
            "pii_detected": scan.has_pii,
            "pii_types": list(scan.pii.keys()),
            "prompt_injection_detected": scan.has_injection,
            "injection_isolated": scan.injection_isolated,
            "size_bytes": len(content),
        },
        storage_path=storage_key,
        status="ingested",
        uploaded_by=user_id,
    )
    db.add(document)
    db.flush()

    chunks = chunk_text(store_text)
    vectors = embedder.embed(chunks) if chunks else []
    if len(vectors) != len(chunks):
        raise ValidationError(
            "embedding provider returned mismatched count; indexing aborted"
        )
    collection = DOCS_COLLECTION
    store.ensure_collection(collection, dimensions=len(vectors[0]) if vectors else 0)

    ids: list[str] = []
    payloads: list[dict] = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        cid = f"{document.id}:{i}"
        ids.append(cid)
        payloads.append(
            {
                "document_id": document.id,
                "chunk_index": i,
                "text": chunk,
                "organization_id": organization_id,
                "jurisdiction": jurisdiction,
                "domain": domain,
                "doc_type": doc_type,
                "document_category": resolved_category,
                "doc_category": resolved_category,
                "source_status": source_status,
                "effective_date": effective_date or "",
            }
        )
        db.add(
            DocumentChunk(
                id=cid,
                document_id=document.id,
                chunk_index=i,
                text=chunk,
                vector_id=cid,
            )
        )
    if ids:
        store.upsert(collection, ids, vectors, payloads)
        document.vector_id = ids[0]
    document.status = "indexed"
    db.commit()
    incr("documents.ingested")
    emit(
        db,
        "document.uploaded",
        organization_id=organization_id,
        user_id=user_id,
        module="review",
        document_id=document.id,
        payload={
            "filename": filename,
            "doc_type": doc_type,
            "chunks": len(chunks),
            "injection": scan.has_injection,
        },
    )
    return document_to_dict(document)


def list_documents(
    *, organization_id: str, db: Session, category: str | None = None, limit: int = 100
) -> list[dict]:
    docs = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == organization_id)
        .order_by(LegalDocument.created_at.desc())
        .limit(limit)
        .all()
    )
    results = [document_to_dict(d) for d in docs]
    if category:
        norm_cat = category.strip().lower()
        results = [
            d
            for d in results
            if d.get("document_category") == norm_cat
            or d.get("doc_category") == norm_cat
        ]
    return results


def get_document(
    *, document_id: str, organization_id: str, db: Session, with_text: bool = False
) -> dict:
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).one_or_none()
    if doc is None or doc.organization_id != organization_id:
        from app.core.errors import NotFoundError

        raise NotFoundError("document not found")
    data = document_to_dict(doc)
    if with_text:
        data["text"] = doc.text
    data["metadata"] = {
        "filename": (doc.metadata_json or {}).get("filename", ""),
        "prompt_injection_detected": (doc.metadata_json or {}).get(
            "prompt_injection_detected", False
        ),
        "pii_types": (doc.metadata_json or {}).get("pii_types", []),
    }
    return data


def update_document_metadata(
    *,
    document_id: str,
    organization_id: str,
    title: str = "",
    doc_type: str = "",
    doc_category: str | None = None,
    jurisdiction: str = "",
    domain: str = "",
    effective_date: str | None = None,
    source_status: str = "",
    db: Session,
) -> dict:
    from app.core.errors import NotFoundError

    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).one_or_none()
    if doc is None or doc.organization_id != organization_id:
        raise NotFoundError("document not found")

    if title.strip():
        doc.title = title.strip()
    if doc_type.strip():
        doc.doc_type = doc_type.strip()
    if doc_category and doc_category.strip():
        clean_cat = doc_category.strip().lower()
        if clean_cat in ("knowledge_artefact", "contract_review"):
            meta = dict(doc.metadata_json or {})
            meta["doc_category"] = clean_cat
            meta["document_category"] = clean_cat
            doc.metadata_json = meta
    if jurisdiction.strip():
        doc.jurisdiction = jurisdiction.strip()
    if domain.strip():
        doc.domain = domain.strip()
    if effective_date is not None:
        doc.effective_date = effective_date.strip() or None
    if source_status.strip():
        doc.source_status = source_status.strip()

    chunks = sorted(doc.chunks, key=lambda c: c.chunk_index)
    if chunks:
        # Keep vector payloads (used for jurisdiction/domain filtering) in sync
        # without losing the point vectors: re-embed the stored chunk text and
        # upsert under the same ids.
        store = get_vectorstore()
        embedder = get_embeddings()
        vectors = embedder.embed([c.text for c in chunks])
        if len(vectors) == len(chunks):
            ids = [f"{document_id}:{c.chunk_index}" for c in chunks]
            store.ensure_collection(
                DOCS_COLLECTION, dimensions=len(vectors[0]) if vectors else 0
            )
            payloads = [
                {
                    "document_id": document_id,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "organization_id": organization_id,
                    "jurisdiction": doc.jurisdiction,
                    "domain": doc.domain,
                    "doc_type": doc.doc_type,
                    "doc_category": doc.document_category,
                    "document_category": doc.document_category,
                    "source_status": doc.source_status,
                    "effective_date": doc.effective_date or "",
                }
                for c in chunks
            ]
            store.upsert(DOCS_COLLECTION, ids, vectors, payloads)
        else:
            logger.warning(
                "embedding count mismatch while updating metadata for %s",
                document_id,
            )
    db.commit()
    return document_to_dict(doc)


def delete_document(*, document_id: str, organization_id: str, db: Session) -> None:
    from app.core.errors import NotFoundError
    from app.models.review import DocumentReview, ReviewFinding

    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).one_or_none()
    if doc is None or doc.organization_id != organization_id:
        raise NotFoundError("document not found")

    # Clean up associated reviews and their findings
    reviews = (
        db.query(DocumentReview).filter(DocumentReview.document_id == document_id).all()
    )
    for rev in reviews:
        db.query(ReviewFinding).filter(ReviewFinding.review_id == rev.id).delete()
        db.delete(rev)

    store = get_vectorstore()
    ids = [c.id for c in doc.chunks]
    # Delete by point ids first, then by document payload filter as a safety net
    # so replaced/deleted documents never leave orphaned vectors behind.
    try:
        if ids:
            store.delete(DOCS_COLLECTION, ids=ids)
        store.delete(DOCS_COLLECTION, filters={"document_id": document_id})
    except Exception:
        logger.exception("vector deletion failed")
    storage = get_storage()
    if doc.storage_path:
        try:
            storage.delete(doc.storage_path)
        except Exception:
            logger.exception("object deletion failed")
    db.delete(doc)
    db.commit()


def document_to_dict(doc: LegalDocument) -> dict:
    meta = doc.metadata_json or {}
    filename = meta.get("filename") or doc.title or "Untitled Document"
    cat = doc.document_category
    return {
        "id": doc.id,
        "title": doc.title or filename,
        "filename": filename,
        "doc_type": doc.doc_type,
        "document_category": cat,
        "doc_category": cat,
        "jurisdiction": doc.jurisdiction,
        "domain": doc.domain,
        "effective_date": doc.effective_date,
        "version": doc.version,
        "source_status": doc.source_status,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "uploaded_by": doc.uploaded_by,
        "metadata": meta,
    }
