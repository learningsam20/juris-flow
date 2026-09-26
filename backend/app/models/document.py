"""Legal document models (PRD §5.2, §5.3, §9.1)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.org import utcnow

if TYPE_CHECKING:
    from app.models.review import DocumentReview


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(64), default="contract"
    )  # statute|regulation|case_law|template|contract|notice|policy
    jurisdiction: Mapped[str] = mapped_column(String(128), default="")
    domain: Mapped[str] = mapped_column(String(128), default="")
    effective_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    source_status: Mapped[str] = mapped_column(
        String(32), default="verified"
    )  # verified|secondary|unverified|expired
    text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONType, default=dict
    )
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vector_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="ingested"
    )  # ingested|indexed|failed|draft
    uploaded_by: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    @property
    def document_category(self) -> str:
        meta = self.metadata_json or {}
        cat = meta.get("document_category") or meta.get("doc_category")
        if cat in ("knowledge_artefact", "contract_review"):
            return cat
        # Uploader historically defaulted doc_type=contract for KM uploads.
        # Only treat as contract_review when explicitly categorized; otherwise
        # prefer knowledge artefact (statutes, regulations, policies, etc.).
        dtype = (self.doc_type or "").lower()
        if dtype in ("statute", "regulation", "policy", "brief", "pleading"):
            return "knowledge_artefact"
        return "knowledge_artefact"

    @document_category.setter
    def document_category(self, value: str) -> None:
        meta = dict(self.metadata_json or {})
        meta["document_category"] = value
        meta["doc_category"] = value
        self.metadata_json = meta

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )
    reviews: Mapped[list[DocumentReview]] = relationship(back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("legal_documents.id"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    vector_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    document: Mapped[LegalDocument] = relationship(back_populates="chunks")
