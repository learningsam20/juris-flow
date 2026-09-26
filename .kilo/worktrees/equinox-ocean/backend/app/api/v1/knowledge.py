"""Knowledge hub endpoints (PRD §5.3, §6.7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.services import hub

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class CollectionItemAdd(BaseModel):
    item_type: str = Field(pattern="^(document|scenario|simulation|review)$")
    item_id: str
    note: str = ""


class SearchParams(BaseModel):
    query: str = ""
    jurisdiction: str = ""
    domain: str = ""
    doc_type: str = ""
    source_status: str = ""
    limit: int = 20
    top_k: int | None = None


@router.post("/search")
def search(
    body: SearchParams,
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    effective_limit = body.top_k if body.top_k is not None else body.limit
    return hub.search_documents(
        query=body.query,
        organization_id=user.organization_id,
        db=db,
        jurisdiction=body.jurisdiction,
        domain=body.domain,
        doc_type=body.doc_type,
        source_status=body.source_status,
        limit=min(effective_limit or 20, 100),
        user_id=user.id,
    )


@router.post("/ask")
def ask(
    body: SearchParams,
    _: None = Depends(rate_limit("knowledge.ask")),
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    """LLM-grounded Q&A over the indexed library (Ask AI)."""
    return hub.ask_question(
        query=body.query,
        organization_id=user.organization_id,
        db=db,
        jurisdiction=body.jurisdiction,
        domain=body.domain,
        doc_type=body.doc_type,
        source_status=body.source_status,
        top_k=min(body.top_k or body.limit or 8, 12),
        user_id=user.id,
    )


@router.get("/insights")
def insights(
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    return hub.insights(organization_id=user.organization_id, db=db)


@router.post("/teaching_pack")
def teaching_pack(
    body: SearchParams,
    user: CurrentUser = Depends(require_module("hub", "collection.manage")),
    db: Session = Depends(get_db),
) -> dict:
    if not (body.query or "").strip():
        raise HTTPException(status_code=422, detail="topic is required")
    pack = hub.teaching_pack(
        topic=body.query.strip(), organization_id=user.organization_id, db=db
    )
    if body.query.strip():
        audit(
            db,
            action="teaching_pack_assembled",
            actor=user.id,
            organization_id=user.organization_id,
            resource_type="collection",
            detail={"topic": body.query.strip()},
        )
    return pack


@router.get("/collections")
def list_collections(
    user: CurrentUser = Depends(require_module("hub", "knowledge.search")),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "collections": hub.list_collections(organization_id=user.organization_id, db=db)
    }


@router.post("/collections", status_code=201)
def create_collection(
    body: CollectionCreate,
    user: CurrentUser = Depends(require_module("hub", "collection.manage")),
    db: Session = Depends(get_db),
) -> dict:
    coll = hub.create_collection(
        name=body.name,
        description=body.description,
        organization_id=user.organization_id,
        owner_id=user.id,
        db=db,
    )
    audit(
        db,
        action="collection_created",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="collection",
        resource_id=coll["id"],
    )
    return coll


@router.post("/collections/{collection_id}/items", status_code=201)
def add_to_collection(
    collection_id: str,
    body: CollectionItemAdd,
    user: CurrentUser = Depends(require_module("hub", "collection.manage")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        coll = hub.add_to_collection(
            collection_id=collection_id,
            organization_id=user.organization_id,
            item_type=body.item_type,
            item_id=body.item_id,
            note=body.note,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return coll
