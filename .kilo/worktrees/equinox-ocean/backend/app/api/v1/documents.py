"""Document upload, listing and detail endpoints (PRD §5.2)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module
from app.core.errors import ConflictError, JurisLabError
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.services import document as document_service

MAX_FILE_BYTES = 25 * 1024 * 1024

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentMetadataUpdate(BaseModel):
    title: str = Field(default="", max_length=255)
    doc_type: str = Field(default="", max_length=64)
    doc_category: str | None = Field(default=None, max_length=64)
    jurisdiction: str = Field(default="", max_length=128)
    domain: str = Field(default="", max_length=128)
    effective_date: str | None = Field(default=None, max_length=64)
    source_status: str = Field(default="", max_length=32)


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form("contract"),
    doc_category: str = Form("knowledge_artefact"),
    jurisdiction: str = Form(""),
    domain: str = Form(""),
    effective_date: str | None = Form(None),
    version: str = Form("1.0"),
    source_status: str = Form("verified"),
    overwrite: bool = Form(False),
    _: None = Depends(rate_limit("documents.upload")),
    user: CurrentUser = Depends(require_module("review", "document.upload")),
    db: Session = Depends(get_db),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="empty file upload")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds 25MB limit")
    try:
        doc = document_service.upload_document(
            organization_id=user.organization_id,
            user_id=user.id,
            filename=file.filename or "document.bin",
            content=content,
            title=title,
            doc_type=doc_type,
            doc_category=doc_category,
            jurisdiction=jurisdiction,
            domain=domain,
            effective_date=effective_date,
            version=version,
            source_status=source_status,
            overwrite=overwrite,
            db=db,
        )
    except JurisLabError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit(
        db,
        action="document_uploaded",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="document",
        resource_id=doc["id"],
    )
    return doc


def _safe_filename(filename: str | None) -> str:
    name = (filename or "document.bin").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name or "document.bin"


@router.post("/upload-folder", status_code=201)
async def upload_folder(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("contract"),
    doc_category: str = Form("knowledge_artefact"),
    jurisdiction: str = Form(""),
    domain: str = Form(""),
    title_prefix: str = Form(""),
    overwrite: bool = Form(False),
    _: None = Depends(rate_limit("documents.upload")),
    user: CurrentUser = Depends(require_module("review", "document.upload")),
    db: Session = Depends(get_db),
) -> dict:
    """Index every file inside an uploaded folder.

    Each file is processed independently so one failure never aborts the
    batch. Deduplication is by basename; a title_prefix makes titles unique
    without renaming files. Returns per-file status: uploaded | conflict | error.
    """
    if not files:
        raise HTTPException(status_code=422, detail="no files selected")
    if len(files) > 500:
        raise HTTPException(status_code=422, detail="folder exceeds 500 files")

    results: list[dict] = []
    uploaded = 0
    for file in files:
        filename = _safe_filename(file.filename)
        content = await file.read()
        if not content:
            results.append(
                {
                    "filename": filename,
                    "status": "error",
                    "detail": "empty file skipped",
                }
            )
            continue
        if len(content) > MAX_FILE_BYTES:
            results.append(
                {
                    "filename": filename,
                    "status": "error",
                    "detail": "file exceeds 25MB limit",
                }
            )
            continue
        try:
            doc = document_service.upload_document(
                organization_id=user.organization_id,
                user_id=user.id,
                filename=filename,
                content=content,
                title=f"{title_prefix} {Path(filename).stem}".strip()
                if title_prefix
                else filename,
                doc_type=doc_type,
                doc_category=doc_category,
                jurisdiction=jurisdiction,
                domain=domain,
                overwrite=overwrite,
                db=db,
            )
            uploaded += 1
            results.append(
                {"filename": filename, "status": "uploaded", "document": doc}
            )
        except ConflictError:
            results.append(
                {
                    "filename": filename,
                    "status": "conflict",
                    "detail": f"'{filename}' already exists",
                }
            )
        except JurisLabError as exc:
            results.append(
                {"filename": filename, "status": "error", "detail": exc.message}
            )
        except Exception as exc:  # per-file isolation; never abort the batch
            results.append(
                {"filename": filename, "status": "error", "detail": str(exc)}
            )

    if uploaded:
        audit(
            db,
            action="document_uploaded",
            actor=user.id,
            organization_id=user.organization_id,
            resource_type="document",
            resource_id=_safe_filename(files[0].filename),
        )
    return {
        "results": results,
        "uploaded": uploaded,
        "total": len(files),
        "failed": len(files) - uploaded,
    }


@router.get("")
def list_documents(
    category: str | None = None,
    limit: int = 100,
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    docs = document_service.list_documents(
        organization_id=user.organization_id,
        category=category,
        db=db,
        limit=min(limit, 500),
    )
    return {"documents": docs, "count": len(docs)}


@router.patch("/{document_id}")
def update_document_metadata(
    document_id: str,
    body: DocumentMetadataUpdate,
    user: CurrentUser = Depends(require_module("hub", "knowledge.edit")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        doc = document_service.update_document_metadata(
            document_id=document_id,
            organization_id=user.organization_id,
            title=body.title,
            doc_type=body.doc_type,
            doc_category=body.doc_category,
            jurisdiction=body.jurisdiction,
            domain=body.domain,
            effective_date=body.effective_date,
            source_status=body.source_status,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit(
        db,
        action="document_metadata_updated",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="document",
        resource_id=document_id,
    )
    return doc


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return document_service.get_document(
            document_id=document_id,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{document_id}/detail")
def document_detail(
    document_id: str,
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.hub import document_detail as hub_detail

    try:
        return hub_detail(
            document_id=document_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    user: CurrentUser = Depends(require_module("hub", "knowledge.edit")),
    db: Session = Depends(get_db),
) -> None:
    try:
        document_service.delete_document(
            document_id=document_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit(
        db,
        action="document_deleted",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="document",
        resource_id=document_id,
    )
